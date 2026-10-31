--!strict
-- Fight: numbered stages in the five zones. Step on a zone's StartPad -> the next uncleared stage of that zone
-- starts (or the zone's last stage again, for farming). Enemies are server-owned anchored dummies that walk to
-- the player and hit back; enemy HP grows 1.6x per stage, so players hit a wall and go back to train.
-- Clients only send "attack", "skill", "ultimate"; target, damage, cooldowns and rewards are all server-side.
local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Net = require(ReplicatedStorage:WaitForChild("LihFolk"):WaitForChild("Net"))
local GameConfig = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("GameConfig"))
local Stats = require(script.Parent.Stats)
local Stands = require(script.Parent.Stands)
local Training = require(script.Parent.Training)

local Fight = {}

type Enemy = {
	model: Model,
	body: BasePart,
	hp: number,
	maxHp: number,
	nextAttack: number,
	bar: Frame,
	height: number,
}
type FightState = {
	player: Player,
	stage: number,
	zone: number,
	boss: boolean,
	enemies: { Enemy },
	total: number,
	hp: number,
	maxHp: number,
	startedAt: number,
	nextAttackAt: number,
	skillReadyAt: number,
	ultReadyAt: number,
	center: Vector3,
	folder: Folder,
	lastStatePush: number,
	ending: boolean,
}

local C = GameConfig.Combat
local fights: { [Player]: FightState } = {}
local padCooldown: { [Player]: number } = {} -- no new fight from a pad until this os.clock()
local AFTER_FIGHT_COOLDOWN = 6 -- standing on the pad after a fight must not chain the next stage instantly
local rng = Random.new()
local fightsFolder: Folder
local statePush: Net.Push, hitPush: Net.Push, endPush: Net.Push, cdPush: Net.Push, notify: Net.Push

local ZONE_COLORS = {
	Color3.fromHex("7BC86C"), Color3.fromHex("D9A85B"), Color3.fromHex("8FD3F5"), Color3.fromHex("C2461E"), Color3.fromHex("8E46BD"),
}

local function zoneFolder(zone: number): Instance?
	local stages = workspace:FindFirstChild("Map") and workspace.Map:FindFirstChild("Stages")
	if not stages then
		return nil
	end
	for _, f in stages:GetChildren() do
		if f:GetAttribute("ZoneIndex") == zone then
			return f
		end
	end
	return nil
end

local function hrpOf(player: Player): BasePart?
	local char = player.Character
	local hrp = char and char:FindFirstChild("HumanoidRootPart")
	return if hrp and hrp:IsA("BasePart") then hrp else nil
end

local function makeEnemy(parent: Folder, at: Vector3, zone: number, boss: boolean, hp: number): Enemy
	local s = if boss then 2.2 else 1
	local color = ZONE_COLORS[zone] or Color3.new(1, 1, 1)
	local m = Instance.new("Model")
	m.Name = if boss then "Boss" else "Enemy"
	local function part(name: string, size: Vector3, offset: Vector3, c: Color3, mat: Enum.Material?): Part
		local p = Instance.new("Part")
		p.Name = name
		p.Size = size * s
		p.CFrame = CFrame.new(at + offset * s)
		p.Color = c
		p.Material = mat or Enum.Material.SmoothPlastic
		p.Anchored = true
		p.CanCollide = false
		p.CanQuery = false
		p.CanTouch = false
		p.Parent = m
		return p
	end
	local body = part("Body", Vector3.new(3, 3, 2.4), Vector3.new(0, 2.2, 0), color)
	part("Head", Vector3.new(2.2, 1.8, 2), Vector3.new(0, 4.6, 0), color:Lerp(Color3.new(1, 1, 1), 0.2))
	for _, x in { -0.5, 0.5 } do
		part("Eye", Vector3.new(0.45, 0.3, 0.1), Vector3.new(x, 4.8, -1.02), Color3.fromHex("FF3B3B"), Enum.Material.Neon)
		part("Leg", Vector3.new(0.9, 0.9, 0.9), Vector3.new(x * 2, 0.45, 0), color:Lerp(Color3.new(0, 0, 0), 0.35))
	end
	if boss then
		for _, x in { -0.8, 0.8 } do
			part("Horn", Vector3.new(0.35, 1.1, 0.35), Vector3.new(x, 5.9, 0), Color3.fromHex("F5E6A8"))
		end
	end
	m.PrimaryPart = body
	local bb = Instance.new("BillboardGui")
	bb.Name = "HP"
	bb.Size = UDim2.new(4 * s, 0, 0.5 * s, 0)
	bb.StudsOffset = Vector3.new(0, 4 * s, 0)
	bb.AlwaysOnTop = true
	bb.MaxDistance = 120
	local back = Instance.new("Frame")
	back.Size = UDim2.fromScale(1, 1)
	back.BackgroundColor3 = Color3.fromHex("1E1B33")
	back.BorderSizePixel = 0
	back.Parent = bb
	local fill = Instance.new("Frame")
	fill.Name = "Fill"
	fill.Size = UDim2.fromScale(1, 1)
	fill.BackgroundColor3 = if boss then Color3.fromHex("FF4F7B") else Color3.fromHex("FF6B4A")
	fill.BorderSizePixel = 0
	fill.Parent = back
	bb.Adornee = body
	bb.Parent = body
	m.Parent = parent
	return { model = m, body = body, hp = hp, maxHp = hp, nextAttack = os.clock() + 1.5, bar = fill, height = 2.2 * s }
end

local function pushState(st: FightState)
	st.lastStatePush = os.clock()
	statePush:Fire(st.player, {
		stage = st.stage,
		boss = st.boss,
		hp = math.max(0, math.floor(st.hp)),
		maxHp = math.floor(st.maxHp),
		left = #st.enemies,
		total = st.total,
		timeLeft = math.max(0, math.floor(C.timeLimit - (os.clock() - st.startedAt))),
	})
end

local function rollFragment(zone: number, luck: number): string
	local weights = GameConfig.FragmentDrops[zone] or GameConfig.FragmentDrops[1]
	local function roll(): string
		local total = 0
		for _, w in weights do
			total += w
		end
		local r = rng:NextNumber() * total
		for _, rarity in GameConfig.Rarities do
			local w = weights[rarity]
			if w then
				r -= w
				if r <= 0 then
					return rarity
				end
			end
		end
		return "Common"
	end
	local a = roll()
	if luck > 0 and rng:NextNumber() < luck then
		local b = roll()
		if (table.find(GameConfig.Rarities, b) or 0) > (table.find(GameConfig.Rarities, a) or 0) then
			return b
		end
	end
	return a
end

local function finish(st: FightState, won: boolean, reason: string)
	if st.ending then
		return
	end
	st.ending = true
	local player = st.player
	fights[player] = nil
	padCooldown[player] = os.clock() + AFTER_FIGHT_COOLDOWN
	st.folder:Destroy()
	player:SetAttribute("InFight", false)
	if player.Parent ~= Players then
		return
	end
	if won then
		local coins = GameConfig.StageCoins(st.stage)
		local cs = Stands.GetCombatStats(player)
		local frags: { [string]: number } = {}
		for _ = 1, if st.boss then 3 else 1 do
			local r = rollFragment(st.zone, cs.fragmentLuck)
			frags[r] = (frags[r] or 0) + 1
		end
		Stats.AddCoins(player, coins)
		for r, n in frags do
			Stats.AddFragments(player, r, n)
		end
		local rerolls = if st.boss then 1 else 0
		if rerolls > 0 then
			Stats.AddTraitRerolls(player, rerolls)
		end
		Stats.ClearStage(player, st.stage)
		endPush:Fire(player, true, { stage = st.stage, coins = coins, fragments = frags, rerolls = rerolls })
	else
		local hrp = hrpOf(player)
		local spawn = workspace:FindFirstChild("LobbySpawn", true)
		if hrp and spawn and spawn:IsA("BasePart") and reason ~= "left" then
			hrp.CFrame = spawn.CFrame + Vector3.new(0, 4, 0)
		end
		endPush:Fire(player, false, { stage = st.stage, reason = reason })
	end
end

local function damageEnemy(st: FightState, e: Enemy, amount: number, kind: string)
	if e.hp <= 0 then
		return
	end
	local dealt = math.min(e.hp, amount)
	e.hp -= amount
	local lifesteal = Stands.GetCombatStats(st.player).lifesteal
	if lifesteal > 0 then
		st.hp = math.min(st.maxHp, st.hp + dealt * lifesteal)
	end
	hitPush:Fire(st.player, e.body.Position + Vector3.new(0, e.height, 0), math.floor(amount), kind)
	if e.hp <= 0 then
		local i = table.find(st.enemies, e)
		if i then
			table.remove(st.enemies, i)
		end
		e.model:Destroy()
	else
		e.bar.Size = UDim2.fromScale(math.clamp(e.hp / e.maxHp, 0, 1), 1)
	end
end

local function baseHit(player: Player): number
	local s = Stats.Get(player)
	local cs = Stands.GetCombatStats(player)
	return (1 + (if s then s.Power else 0) * C.damagePerPower) * cs.power
end

local function nearest(st: FightState, from: Vector3, range: number): Enemy?
	local best, bestD = nil, range
	for _, e in st.enemies do
		local d = (e.body.Position - from).Magnitude
		if d <= bestD then
			best, bestD = e, d
		end
	end
	return best
end

function Fight.Start(player: Player, zone: number)
	if fights[player] then
		return
	end
	local s = Stats.Get(player)
	local hrp = hrpOf(player)
	local zf = zoneFolder(zone)
	if not s or not hrp or not zf then
		return
	end
	local minStage, maxStage = (zone - 1) * C.stagesPerZone + 1, zone * C.stagesPerZone
	local nextStage = s.HighestStage + 1
	if nextStage < minStage then
		notify:Fire(player, `Clear Stage {minStage - 1} to unlock Zone {zone}`, "locked")
		return
	end
	local stage = math.min(nextStage, maxStage)
	local boss = GameConfig.IsBoss(stage)
	local spawns = zf:FindFirstChild("EnemySpawns")
	if not spawns then
		return
	end
	local folder = Instance.new("Folder")
	folder.Name = tostring(player.UserId)
	folder.Parent = fightsFolder
	local cs = Stands.GetCombatStats(player)
	local maxHp = (C.playerBaseHP + s.Power * C.playerHPPerPower) * cs.durability
	local st: FightState = {
		player = player, stage = stage, zone = zone, boss = boss, enemies = {}, total = 0,
		hp = maxHp, maxHp = maxHp, startedAt = os.clock(), nextAttackAt = 0, skillReadyAt = 0, ultReadyAt = 0,
		center = Vector3.zero, folder = folder, lastStatePush = 0, ending = false,
	}
	local hp = GameConfig.EnemyHP(stage)
	if boss then
		local at = spawns:FindFirstChild("BossSpawn")
		if at and at:IsA("BasePart") then
			table.insert(st.enemies, makeEnemy(folder, at.Position - Vector3.new(0, at.Position.Y, 0), zone, true, hp * C.bossHPMult))
		end
	else
		for k = 1, C.enemiesPerStage do
			local at = spawns:FindFirstChild("Spawn" .. k)
			if at and at:IsA("BasePart") then
				table.insert(st.enemies, makeEnemy(folder, at.Position - Vector3.new(0, at.Position.Y, 0), zone, false, hp))
			end
		end
	end
	st.total = #st.enemies
	local floor = zf:FindFirstChild("Floor")
	st.center = if floor and floor:IsA("BasePart") then floor.Position else hrp.Position
	fights[player] = st
	player:SetAttribute("InFight", true)
	pushState(st)
end

local function step()
	local now = os.clock()
	for player, st in fights do
		if st.ending then
			continue
		end
		local hrp = hrpOf(player)
		if not hrp then
			finish(st, false, "died")
			continue
		end
		if now - st.startedAt > C.timeLimit then
			finish(st, false, "time")
			continue
		end
		if (Vector3.new(hrp.Position.X, 0, hrp.Position.Z) - Vector3.new(st.center.X, 0, st.center.Z)).Magnitude > C.leashDistance then
			finish(st, false, "left")
			continue
		end
		local target = Vector3.new(hrp.Position.X, 0, hrp.Position.Z)
		local dt = 1 / 30
		for _, e in st.enemies do
			local pos = e.body.Position
			local flat = Vector3.new(pos.X, 0, pos.Z)
			local to = target - flat
			local dist = to.Magnitude
			local reach = C.enemyReach * (if st.boss then 1.8 else 1)
			if dist > reach then
				local move = to.Unit * math.min(C.enemySpeed * dt, dist - reach)
				flat += move
			end
			local at = Vector3.new(flat.X, pos.Y, flat.Z)
			if dist > 0.1 then
				e.model:PivotTo(CFrame.lookAt(at, Vector3.new(target.X, pos.Y, target.Z)))
			end
			if dist <= reach + 1 and now >= e.nextAttack then
				e.nextAttack = now + C.enemyAttackInterval
				st.hp -= e.maxHp * C.enemyHitFraction / (if st.boss then C.bossHPMult / 2 else 1)
				pushState(st)
				if st.hp <= 0 then
					finish(st, false, "defeated")
					break
				end
			end
		end
		if not st.ending and now - st.lastStatePush >= 1 then
			pushState(st)
		end
	end
end

local function onAttack(player: Player, kind: string)
	local st = fights[player]
	local hrp = hrpOf(player)
	if not st or st.ending or not hrp then
		return
	end
	local now = os.clock()
	local cs = Stands.GetCombatStats(player)
	local def = Stands.GetEquipped(player)
	if not def then
		return
	end
	if kind == "hit" then
		if now < st.nextAttackAt then
			return
		end
		st.nextAttackAt = now + C.baseAttackInterval / cs.speed
		local e = nearest(st, hrp.Position, C.attackRange)
		if e then
			damageEnemy(st, e, baseHit(player), "hit")
		end
	else
		local ab = if kind == "skill" then def.skill else def.ultimate
		local readyAt = if kind == "skill" then st.skillReadyAt else st.ultReadyAt
		if now < readyAt then
			return
		end
		local targets: { Enemy } = {}
		if ab.hitsAll then
			local range = if kind == "ultimate" then math.huge else C.attackRange * 1.5
			for _, e in st.enemies do
				if (e.body.Position - hrp.Position).Magnitude <= range then
					table.insert(targets, e)
				end
			end
		else
			local e = nearest(st, hrp.Position, C.attackRange * 1.5)
			if e then
				targets = { e }
			end
		end
		if #targets == 0 then
			return
		end
		local cd = ab.cooldown * (1 - (if kind == "skill" then cs.skillCooldown else cs.ultimateCooldown))
		if kind == "skill" then
			st.skillReadyAt = now + cd
		else
			st.ultReadyAt = now + cd
		end
		cdPush:Fire(player, kind, cd)
		local repeats = if kind == "ultimate" then 1 + cs.ultimateRepeat else 1
		for _ = 1, repeats do
			for _, e in targets do
				damageEnemy(st, e, baseHit(player) * ab.damage, kind)
			end
		end
	end
	if #st.enemies == 0 then
		finish(st, true, "cleared")
	else
		pushState(st)
	end
end

function Fight.Init()
	fightsFolder = Instance.new("Folder")
	fightsFolder.Name = "Fights"
	fightsFolder.Parent = workspace
	statePush = Net.Push("Fight.State")
	hitPush = Net.Push("Fight.Hit")
	endPush = Net.Push("Fight.End")
	cdPush = Net.Push("Fight.Cooldown")
	notify = assert(Training.Notify, "Fight.Init must run after Training.Init")

	Net.Listen("Fight.Attack", { rate = { burst = 10, perSecond = 8 }, args = {}, handler = function(p: Player) onAttack(p, "hit") end })
	Net.Listen("Fight.Skill", { rate = { burst = 3, perSecond = 1 }, args = {}, handler = function(p: Player) onAttack(p, "skill") end })
	Net.Listen("Fight.Ultimate", { rate = { burst = 3, perSecond = 1 }, args = {}, handler = function(p: Player) onAttack(p, "ultimate") end })
	Net.Listen("Fight.Leave", { rate = { burst = 2, perSecond = 0.5 }, args = {}, handler = function(p: Player)
		local st = fights[p]
		if st then
			finish(st, false, "fled")
		end
	end })

	local debounce = padCooldown
	local function hookPad(pad: Instance)
		if not pad:IsA("BasePart") then
			return
		end
		pad.Touched:Connect(function(hit: BasePart)
			local char = hit:FindFirstAncestorOfClass("Model")
			local player = char and Players:GetPlayerFromCharacter(char)
			if not player or fights[player] then
				return
			end
			if (debounce[player] or 0) > os.clock() then
				return
			end
			debounce[player] = math.max(debounce[player] or 0, os.clock() + 2)
			local zone = pad:GetAttribute("ZoneIndex")
			if type(zone) == "number" then
				Fight.Start(player, zone)
			end
		end)
	end
	for _, pad in CollectionService:GetTagged("StageStart") do
		hookPad(pad)
	end
	CollectionService:GetInstanceAddedSignal("StageStart"):Connect(hookPad)

	local acc = 0
	RunService.Heartbeat:Connect(function(dt: number)
		acc += dt
		if acc >= 1 / 30 then
			acc = 0
			step()
		end
	end)
	Players.PlayerRemoving:Connect(function(player: Player)
		debounce[player] = nil
		local st = fights[player]
		if st then
			finish(st, false, "left")
		end
	end)
end

return Fight
