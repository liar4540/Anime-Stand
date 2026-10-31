--!strict
-- Stats: the player's numbers (Power, Coins, stage progress, fragments, rerolls). Owns the "Stats" profile slice.
-- Every change goes through here so attributes, leaderstats and the save stay in step.
-- Clients read player attributes: Power, Coins, HighestStage, Rebirths, TraitRerolls, Frag_<Rarity>.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")

local PlayerData = require(ServerScriptService:WaitForChild("LihFolk"):WaitForChild("PlayerData"))
local GameConfig = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("GameConfig"))

export type StatsData = {
	Power: number,
	Coins: number,
	HighestStage: number,
	Rebirths: number,
	TraitRerolls: number,
	Fragments: { [string]: number },
}

local Stats = {}

local function newStats(): StatsData
	local frags = {}
	for _, r in GameConfig.Rarities do
		frags[r] = 0
	end
	return { Power = 0, Coins = 0, HighestStage = 0, Rebirths = 0, TraitRerolls = 0, Fragments = frags }
end

function Stats.Get(player: Player): StatsData?
	local profile = PlayerData.Get(player)
	return if profile then profile.Data.Stats :: StatsData else nil
end

local function leaderstat(player: Player, name: string): IntValue?
	local ls = player:FindFirstChild("leaderstats")
	local v = ls and ls:FindFirstChild(name)
	return if v and v:IsA("IntValue") then v else nil
end

function Stats.Sync(player: Player)
	local s = Stats.Get(player)
	if not s then
		return
	end
	player:SetAttribute("Power", s.Power)
	player:SetAttribute("Coins", s.Coins)
	player:SetAttribute("HighestStage", s.HighestStage)
	player:SetAttribute("Rebirths", s.Rebirths)
	player:SetAttribute("TraitRerolls", s.TraitRerolls)
	for _, r in GameConfig.Rarities do
		player:SetAttribute("Frag_" .. r, s.Fragments[r] or 0)
	end
	local p = leaderstat(player, "Power")
	if p then
		p.Value = math.min(s.Power, 2 ^ 53)
	end
	local st = leaderstat(player, "Stage")
	if st then
		st.Value = s.HighestStage
	end
end

local function change(player: Player, fn: (StatsData) -> ())
	local profile = PlayerData.Get(player)
	if not profile then
		return false
	end
	fn(profile.Data.Stats :: StatsData)
	PlayerData.MarkDirty(profile)
	Stats.Sync(player)
	return true
end

function Stats.AddPower(player: Player, amount: number): boolean
	assert(amount >= 0 and amount == amount, "AddPower: bad amount")
	return change(player, function(s)
		s.Power += amount
	end)
end

function Stats.AddCoins(player: Player, amount: number): boolean
	assert(amount >= 0 and amount == amount, "AddCoins: bad amount")
	return change(player, function(s)
		s.Coins += amount
	end)
end

function Stats.AddFragments(player: Player, rarity: string, count: number): boolean
	assert(table.find(GameConfig.Rarities, rarity) ~= nil and count >= 0, "AddFragments: bad args")
	return change(player, function(s)
		s.Fragments[rarity] = (s.Fragments[rarity] or 0) + count
	end)
end

function Stats.AddTraitRerolls(player: Player, count: number): boolean
	return change(player, function(s)
		s.TraitRerolls += count
	end)
end

function Stats.ClearStage(player: Player, stage: number): boolean
	return change(player, function(s)
		s.HighestStage = math.max(s.HighestStage, math.clamp(stage, 0, GameConfig.Combat.maxStage))
	end)
end

function Stats.Init()
	PlayerData.RegisterSlice("Stats", newStats)
	PlayerData.Loaded:Connect(function(player: Player)
		local ls = Instance.new("Folder")
		ls.Name = "leaderstats"
		for _, n in { "Power", "Stage" } do
			local v = Instance.new("IntValue")
			v.Name = n
			v.Parent = ls
		end
		ls.Parent = player
		Stats.Sync(player)
	end)
	PlayerData.LoadFailed:Connect(function(player: Player, reason: string)
		warn(`[Stats] {player.UserId} failed to load: {reason}`)
	end)
end

return Stats
