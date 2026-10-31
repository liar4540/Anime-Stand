--!strict
-- +1 Anime Stand client: sends intent only ("punch", "hit", "skill", "ultimate", "leave") and renders what the
-- server pushes back. Keys for PC: F / left click on the button = punch or hit, Q = skill, R = ultimate, T = auto, G = stands.
local CollectionService = game:GetService("CollectionService")
local ContextActionService = game:GetService("ContextActionService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Net = require(ReplicatedStorage:WaitForChild("LihFolk"):WaitForChild("Net"))
local Shared = ReplicatedStorage:WaitForChild("Shared")
local GameConfig = require(Shared:WaitForChild("GameConfig"))
local Format = require(Shared:WaitForChild("Format"))
local Hud = require(script.Parent:WaitForChild("UI"):WaitForChild("Hud"))
local Effects = require(script.Parent:WaitForChild("UI"):WaitForChild("Effects"))
local StandsPanel = require(script.Parent:WaitForChild("UI"):WaitForChild("StandsPanel"))

local player = Players.LocalPlayer
local hud = Hud.Create()

-- stand inventory (equip) + Studio-only dev grant
local EQUIP_ERRORS = { InFight = "Finish the fight first", NotOwned = "You don't own that stand", NotReady = "Still loading..." }
local standsPanel = StandsPanel.Create(hud.gui, function(uid: string)
	local res = Net.Request("Stands.Equip", uid)
	if res.ok then
		local id = player:GetAttribute("EquippedStand")
		local def = if type(id) == "string" then GameConfig.Stands[id] else nil
		hud.toast((if def then def.name else "Stand") .. " equipped!", Color3.fromHex("9EF57A"))
	else
		hud.toast(EQUIP_ERRORS[res.code] or ("Could not equip (" .. res.code .. ")"), Color3.fromHex("FF8A8A"))
	end
end, function(standId: string)
	local res = Net.Request("Dev.GrantStand", standId)
	local def = GameConfig.Stands[standId]
	if res.ok then
		hud.toast(string.format("[DEV] Got %s (%s)", def.name, tostring(res.data and res.data.trait)), Color3.fromHex("FFB36B"))
	else
		hud.toast("[DEV] " .. res.code, Color3.fromHex("FF8A8A"))
	end
end)
hud.stands.Activated:Connect(standsPanel.toggle)
local inFight = false
local autoOn = false

-- stats panel from server-set attributes
local function refresh()
	local frags = {}
	for _, r in GameConfig.Rarities do
		local n = player:GetAttribute("Frag_" .. r)
		if type(n) == "number" and n > 0 then
			table.insert(frags, string.sub(r, 1, 1) .. ":" .. Format.Short(n))
		end
	end
	local standId = player:GetAttribute("EquippedStand")
	local def = if type(standId) == "string" then GameConfig.Stands[standId] else nil
	local trait = player:GetAttribute("StandTrait")
	local reroll = player:GetAttribute("TraitRerolls")
	hud.setStats(
		Format.Short(tonumber(player:GetAttribute("Power")) or 0),
		Format.Short(tonumber(player:GetAttribute("Coins")) or 0),
		tostring(player:GetAttribute("HighestStage") or 0),
		if #frags > 0 then "Fragments " .. table.concat(frags, " ") else "Fragments: none yet",
		if def then string.format("%s [%s]%s", def.name, tostring(trait or "?"), if (tonumber(reroll) or 0) > 0 then "  Rerolls " .. tostring(reroll) else "") else ""
	)
end
player.AttributeChanged:Connect(refresh)
refresh()

-- spot target lookup for hit sparks
local function spotTarget(spotId: string): Vector3?
	for _, m in CollectionService:GetTagged("TrainingSpot") do
		if m:GetAttribute("SpotId") == spotId then
			local t = m:FindFirstChild("Target", true)
			if t and t:IsA("BasePart") then
				return t.Position
			end
		end
	end
	return nil
end

-- actions
local function punch()
	hud.pulse(hud.punch)
	if inFight then
		Net.Send("Fight.Attack")
	else
		Net.Send("Train.Punch")
	end
end
local function skill()
	if inFight then
		hud.pulse(hud.skill)
		Net.Send("Fight.Skill")
	end
end
local function ultimate()
	if inFight then
		hud.pulse(hud.ult)
		Net.Send("Fight.Ultimate")
	end
end
local function toggleAuto()
	autoOn = not autoOn
	hud.setAuto(autoOn)
end

hud.punch.Activated:Connect(punch)
hud.skill.Activated:Connect(skill)
hud.ult.Activated:Connect(ultimate)
hud.auto.Activated:Connect(toggleAuto)
hud.leave.Activated:Connect(function()
	Net.Send("Fight.Leave")
end)

local function bind(name: string, fn: () -> (), ...: Enum.KeyCode)
	ContextActionService:BindAction(name, function(_, state: Enum.UserInputState)
		if state == Enum.UserInputState.Begin then
			fn()
		end
		return Enum.ContextActionResult.Pass
	end, false, ...)
end
bind("AS_Punch", punch, Enum.KeyCode.F, Enum.KeyCode.ButtonR2)
bind("AS_Skill", skill, Enum.KeyCode.Q, Enum.KeyCode.ButtonX)
bind("AS_Ult", ultimate, Enum.KeyCode.R, Enum.KeyCode.ButtonY)
bind("AS_Auto", toggleAuto, Enum.KeyCode.T)
bind("AS_Stands", function() standsPanel.toggle() end, Enum.KeyCode.G)

task.spawn(function()
	while true do
		task.wait(GameConfig.Training.autoInterval)
		if autoOn then
			if inFight then
				Net.Send("Fight.Attack")
			else
				Net.Send("Train.Punch")
			end
		end
	end
end)

-- server pushes
Net.On("Train.Gain", function(gain: number, crit: boolean, spotId: string)
	Effects.Lunge()
	local at = (if spotId ~= "" then spotTarget(spotId) else nil) or Effects.StandFront()
	if at then
		Effects.Spark(at, if crit then Color3.fromHex("FFD23F") else Color3.fromHex("FFFFFF"), crit)
		Effects.FloatText(at + Vector3.new(0, 2, 0), (if crit then "CRIT +" else "+") .. Format.Short(gain), if crit then Color3.fromHex("FFD23F") else Color3.fromHex("9EF57A"), crit)
	end
	if crit then
		Effects.Shake(0.5, 0.18)
	end
end)

Net.On("Fight.State", function(st: { [string]: any })
	inFight = true
	hud.setFight(st)
end)

Net.On("Fight.Hit", function(at: Vector3, amount: number, kind: string)
	Effects.Lunge()
	local big = kind ~= "hit"
	local color = if kind == "ultimate" then Color3.fromHex("C77DFF") elseif kind == "skill" then Color3.fromHex("4AA8FF") else Color3.fromHex("FFFFFF")
	Effects.Spark(at, color, big)
	Effects.FloatText(at + Vector3.new(0, 1.5, 0), Format.Short(amount), color, big)
	if kind == "ultimate" then
		Effects.Shake(0.8, 0.3)
	end
end)

Net.On("Fight.Cooldown", function(kind: string, seconds: number)
	hud.cooldown(kind, seconds)
end)

Net.On("Fight.End", function(won: boolean, info: { [string]: any })
	inFight = false
	hud.setFight(nil)
	if won then
		local parts = { string.format("Stage %d cleared!  +%s Coins", info.stage, Format.Short(info.coins)) }
		for r, n in info.fragments or {} do
			table.insert(parts, string.format("+%d %s", n, r))
		end
		if (info.rerolls or 0) > 0 then
			table.insert(parts, "+1 Trait Reroll")
		end
		hud.toast(table.concat(parts, "   "), Color3.fromHex("9EF57A"))
	else
		local why = ({ defeated = "You were defeated", time = "Out of time", left = "You left the zone", fled = "You left the fight", died = "Fight lost" })[info.reason] or "Fight lost"
		hud.toast(string.format("%s on Stage %d. Train more Power!", why, info.stage), Color3.fromHex("FF8A8A"))
	end
end)

Net.On("Game.Notify", function(msg: string, kind: string)
	hud.toast(msg, if kind == "locked" then Color3.fromHex("FFB36B") else nil)
end)
