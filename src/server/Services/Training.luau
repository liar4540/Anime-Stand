--!strict
-- Training: the +1 loop. The client only says "I punched"; the server picks the spot from the character's
-- position, checks the Power gate, computes the gain (spot x stand Power x trait x rebirths, 5% crit for 10x)
-- and pushes the result back for feedback. Punching anywhere trains at 1x; standing on an unlocked spot
-- uses that spot's multiplier.
local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Net = require(ReplicatedStorage:WaitForChild("LihFolk"):WaitForChild("Net"))
local GameConfig = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("GameConfig"))
local Stats = require(script.Parent.Stats)
local Stands = require(script.Parent.Stands)

local Training = {}
Training.Notify = nil :: Net.Push?

type Spot = { def: GameConfig.SpotDef, position: Vector3 }
local spots: { Spot } = {}
local rng = Random.new()

local function findSpots()
	table.clear(spots)
	for _, inst in CollectionService:GetTagged("TrainingSpot") do
		local id = inst:GetAttribute("SpotId")
		if inst:IsA("Model") and inst.PrimaryPart and type(id) == "string" then
			for _, def in GameConfig.TrainingSpots do
				if def.id == id then
					table.insert(spots, { def = def, position = inst.PrimaryPart.Position })
				end
			end
		end
	end
end

-- The spot the player stands on (nearest within range), or nil.
function Training.SpotAt(position: Vector3): GameConfig.SpotDef?
	local best, bestDist = nil, GameConfig.Training.spotRange
	for _, s in spots do
		local d = (Vector3.new(s.position.X, 0, s.position.Z) - Vector3.new(position.X, 0, position.Z)).Magnitude
		if d <= bestDist and math.abs(position.Y - s.position.Y) < 12 then
			best, bestDist = s.def, d
		end
	end
	return best
end

-- Pure gain formula (exported for tests and balance sheets).
function Training.Gain(spotMult: number, standPower: number, trainingBonus: number, rebirths: number, crit: boolean): number
	local g = math.max(1, math.floor(spotMult * standPower * (1 + trainingBonus) * (1 + rebirths)))
	return if crit then g * GameConfig.Training.critMultiplier else g
end

function Training.Init()
	findSpots()
	local gainPush = Net.Push("Train.Gain")
	local notify = Net.Push("Game.Notify")
	Training.Notify = notify -- shared with Fight (a remote is declared once)
	local cfg = GameConfig.Training
	Net.Listen("Train.Punch", {
		rate = { burst = math.ceil(cfg.punchesPerSecond * 1.5), perSecond = cfg.punchesPerSecond },
		args = {},
		handler = function(player: Player)
			if player:GetAttribute("InFight") then
				return
			end
			local s = Stats.Get(player)
			local char = player.Character
			local hrp = char and char:FindFirstChild("HumanoidRootPart")
			if not s or not hrp or not hrp:IsA("BasePart") then
				return
			end
			local spot = Training.SpotAt(hrp.Position)
			local mult, spotId = 1, ""
			if spot then
				if s.Power >= spot.requiredPower then
					mult, spotId = spot.multiplier, spot.id
				else
					notify:Fire(player, `{spot.name} needs {spot.requiredPower} Power`, "locked")
				end
			end
			local cs = Stands.GetCombatStats(player)
			local crit = rng:NextNumber() < cfg.critChance
			local gain = Training.Gain(mult, cs.power, cs.training, s.Rebirths, crit)
			if Stats.AddPower(player, gain) then
				gainPush:Fire(player, gain, crit, spotId)
			end
		end,
	})
end

return Training
