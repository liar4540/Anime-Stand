--!strict
-- Stands: owned stands, the equipped stand, trait rolls, effective combat stats, and the stand that follows
-- the player. Owns the "Stands" profile slice. Models come from ReplicatedStorage.Stands.<StandId> (rigged by
-- Models/Stands/out/StandSetup.luau); a simple block placeholder is used until a model exists.
local HttpService = game:GetService("HttpService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")

local RunService = game:GetService("RunService")

local PlayerData = require(ServerScriptService:WaitForChild("LihFolk"):WaitForChild("PlayerData"))
local Net = require(ReplicatedStorage:WaitForChild("LihFolk"):WaitForChild("Net"))
local GameConfig = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("GameConfig"))

local MAX_OWNED = 200 -- inventory cap (keeps the save and the OwnedStands attribute small)

export type OwnedStand = { Uid: string, Id: string, Trait: string, Stars: number, Level: number }
export type StandsData = { Owned: { OwnedStand }, Equipped: string }
export type CombatStats = {
	power: number, -- multiplier (stand Power stat x traits)
	speed: number,
	durability: number,
	training: number, -- bonus fraction
	fragmentLuck: number,
	skillCooldown: number, -- reduction fraction
	ultimateCooldown: number,
	lifesteal: number,
	ultimateRepeat: number,
}

local Stands = {}

local rng = Random.new()

function Stands.RollTrait(): string
	local total = 0
	for _, t in GameConfig.Traits do
		total += t.chance
	end
	local roll = rng:NextNumber() * total
	for _, t in GameConfig.Traits do
		roll -= t.chance
		if roll <= 0 then
			return t.id
		end
	end
	return GameConfig.Traits[1].id
end

local function newStands(): StandsData
	return { Owned = {}, Equipped = "" }
end

-- Mirror the inventory into player attributes for the client UI (server-set, read-only for clients).
function Stands.Sync(player: Player)
	local profile = PlayerData.Get(player)
	if not profile then
		return
	end
	local data = profile.Data.Stands :: StandsData
	local list = {}
	for _, s in data.Owned do
		table.insert(list, { u = s.Uid, i = s.Id, t = s.Trait, s = s.Stars })
	end
	local def, owned = Stands.GetEquipped(player)
	player:SetAttribute("OwnedStands", HttpService:JSONEncode(list))
	player:SetAttribute("EquippedUid", data.Equipped)
	player:SetAttribute("EquippedStand", if def then def.id else "")
	player:SetAttribute("StandTrait", if owned then owned.Trait else "")
end

function Stands.Grant(player: Player, standId: string): OwnedStand?
	local profile = PlayerData.Get(player)
	if not profile or not GameConfig.Stands[standId] then
		return nil
	end
	local data = profile.Data.Stands :: StandsData
	if #data.Owned >= MAX_OWNED then
		return nil
	end
	local entry: OwnedStand = { Uid = HttpService:GenerateGUID(false), Id = standId, Trait = Stands.RollTrait(), Stars = 0, Level = 1 }
	table.insert(data.Owned, entry)
	if data.Equipped == "" then
		data.Equipped = entry.Uid
	end
	PlayerData.MarkDirty(profile)
	Stands.Sync(player)
	return entry
end

-- Equip an owned stand by uid. Returns a result code: "ok", "NotOwned", "InFight", "NotReady".
function Stands.Equip(player: Player, uid: string): string
	local profile = PlayerData.Get(player)
	if not profile then
		return "NotReady"
	end
	if player:GetAttribute("InFight") then
		return "InFight"
	end
	local data = profile.Data.Stands :: StandsData
	for _, s in data.Owned do
		if s.Uid == uid then
			if data.Equipped ~= uid then
				data.Equipped = uid
				PlayerData.MarkDirty(profile)
				Stands.Sync(player)
				Stands.AttachFollower(player)
			end
			return "ok"
		end
	end
	return "NotOwned"
end

function Stands.GetEquipped(player: Player): (GameConfig.StandDef?, OwnedStand?)
	local profile = PlayerData.Get(player)
	if not profile then
		return nil, nil
	end
	local data = profile.Data.Stands :: StandsData
	for _, s in data.Owned do
		if s.Uid == data.Equipped then
			return GameConfig.Stands[s.Id], s
		end
	end
	return nil, nil
end

function Stands.GetCombatStats(player: Player): CombatStats
	local def, owned = Stands.GetEquipped(player)
	local trait = GameConfig.GetTrait(owned and owned.Trait)
	local m: GameConfig.TraitMods = if trait then trait.mods else {}
	local all = 1 + (m.allStats or 0)
	local star = 1 + 0.1 * (if owned then owned.Stars else 0)
	local p = if def then def.power else 1
	local sp = if def then def.speed else 1
	local du = if def then def.durability else 1
	return {
		power = GameConfig.StatMult(p) * (1 + (m.power or 0)) * all * star,
		speed = GameConfig.StatMult(sp) * (1 + (m.speed or 0)) * all * star,
		durability = GameConfig.StatMult(du) * (1 + (m.durability or 0)) * all * star,
		training = m.training or 0,
		fragmentLuck = m.fragmentLuck or 0,
		skillCooldown = m.skillCooldown or 0,
		ultimateCooldown = m.ultimateCooldown or 0,
		lifesteal = m.lifesteal or 0,
		ultimateRepeat = m.ultimateRepeat or 0,
	}
end

---------------------------------------------------------------------------
-- Follower model
---------------------------------------------------------------------------

local function placeholder(def: GameConfig.StandDef): Model
	local m = Instance.new("Model")
	local color = GameConfig.RarityColors[def.rarity] or Color3.new(1, 1, 1)
	local function part(name: string, size: Vector3, offset: Vector3, c: Color3): Part
		local p = Instance.new("Part")
		p.Name = name
		p.Size = size
		p.Color = c
		p.Material = Enum.Material.SmoothPlastic
		p.CFrame = CFrame.new(offset)
		p.Parent = m
		return p
	end
	local root = part("Root", Vector3.new(2, 2, 1), Vector3.new(0, 3.5, 0), color)
	root.Transparency = 1
	local pieces = {
		part("Torso", Vector3.new(2.6, 2.6, 1.4), Vector3.new(0, 4.8, 0), color),
		part("Head", Vector3.new(1.3, 1.3, 1.3), Vector3.new(0, 6.8, 0), color:Lerp(Color3.new(1, 1, 1), 0.3)),
		part("ArmL", Vector3.new(0.9, 2.6, 0.9), Vector3.new(-1.8, 4.6, 0), color),
		part("ArmR", Vector3.new(0.9, 2.6, 0.9), Vector3.new(1.8, 4.6, 0), color),
		part("LegL", Vector3.new(1, 3, 1), Vector3.new(-0.6, 1.5, 0), color:Lerp(Color3.new(0, 0, 0), 0.3)),
		part("LegR", Vector3.new(1, 3, 1), Vector3.new(0.6, 1.5, 0), color:Lerp(Color3.new(0, 0, 0), 0.3)),
	}
	for _, p in pieces do
		local w = Instance.new("WeldConstraint")
		w.Part0 = root
		w.Part1 = p
		w.Parent = p
	end
	m.PrimaryPart = root
	m:SetAttribute("Placeholder", true)
	return m
end

function Stands.AttachFollower(player: Player)
	local char = player.Character
	local hrp = char and char:FindFirstChild("HumanoidRootPart")
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	if not char or not hrp or not hrp:IsA("BasePart") or not hum then
		return
	end
	local def, owned = Stands.GetEquipped(player)
	if not def or not owned then
		return
	end
	local old = char:FindFirstChild("Stand")
	if old then
		old:Destroy()
	end
	local folder = ReplicatedStorage:FindFirstChild("Stands")
	local template = folder and folder:FindFirstChild(def.id)
	local model: Model = if template and template:IsA("Model") then template:Clone() else placeholder(def)
	model.Name = "Stand"
	model:SetAttribute("StandId", def.id)
	model:SetAttribute("Trait", owned.Trait)
	local root = model.PrimaryPart
	if not root then
		model:Destroy()
		warn(`[Stands] {def.id} has no PrimaryPart`)
		return
	end
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			d.Anchored = false
			d.CanCollide = false
			d.CanTouch = false
			d.CanQuery = false
			d.Massless = true
		end
	end
	-- Put the stand's feet a little above the ground, behind the player's right shoulder.
	local bbCf, bbSize = model:GetBoundingBox()
	local rootAboveFeet = root.Position.Y - (bbCf.Position.Y - bbSize.Y / 2)
	local hrpAboveGround = hum.HipHeight + hrp.Size.Y / 2
	local offset = CFrame.new(2.8, rootAboveFeet - hrpAboveGround + 0.6, 3)
	model:PivotTo(hrp.CFrame * offset * root.CFrame:ToObjectSpace(model:GetPivot()))
	local weld = Instance.new("Weld")
	weld.Name = "StandWeld"
	weld.Part0 = hrp
	weld.Part1 = root
	weld.C0 = offset
	weld.C1 = CFrame.identity
	weld.Parent = root
	model.Parent = char
end

function Stands.Init()
	PlayerData.RegisterSlice("Stands", newStands)
	local T = Net.T
	Net.Handle("Stands.Equip", {
		rate = { burst = 4, perSecond = 2 },
		args = { T.guid },
		handler = function(player: Player, uid: string): Net.Result
			local code = Stands.Equip(player, uid)
			return if code == "ok" then Net.ok() else Net.fail(code)
		end,
	})
	-- Studio-only test tool: give yourself any stand (equipped at once). Never registered in live servers.
	if RunService:IsStudio() then
		Net.Handle("Dev.GrantStand", {
			rate = { burst = 4, perSecond = 2 },
			args = { T.key(GameConfig.Stands) },
			handler = function(player: Player, standId: string): Net.Result
				local entry = Stands.Grant(player, standId)
				if not entry then
					return Net.fail("Full")
				end
				Stands.Equip(player, entry.Uid)
				return Net.ok({ uid = entry.Uid, trait = entry.Trait })
			end,
		})
	end
	PlayerData.Loaded:Connect(function(player: Player, profile: PlayerData.Profile)
		local data = profile.Data.Stands :: StandsData
		if #data.Owned == 0 then
			Stands.Grant(player, GameConfig.StarterStand)
		end
		Stands.Sync(player)
		Stands.AttachFollower(player)
		player.CharacterAdded:Connect(function(char: Model)
			char:WaitForChild("HumanoidRootPart", 10)
			task.wait(0.2)
			Stands.AttachFollower(player)
		end)
	end)
end

return Stands
