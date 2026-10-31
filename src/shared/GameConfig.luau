--!strict
-- +1 Anime Stand: the one balance module. Server and client both read it; the server is the only one that acts on it.
-- First-guess numbers from the GDD; tune after playtests. Forge, rebirth, star up and dismantle fields are here
-- already so later systems plug in without changing the data shape.

export type Ability = { name: string, cooldown: number, damage: number, hitsAll: boolean }
export type StandDef = {
	id: string,
	name: string,
	rarity: string,
	forgeChance: number, -- % with 5 Common fragments (GDD table)
	power: number, -- 1..10
	speed: number,
	durability: number,
	skill: Ability,
	ultimate: Ability,
	order: number,
}
export type TraitMods = {
	power: number?,
	speed: number?,
	durability: number?,
	training: number?,
	fragmentLuck: number?,
	skillCooldown: number?,
	ultimateCooldown: number?,
	lifesteal: number?,
	ultimateRepeat: number?,
	allStats: number?,
}
export type TraitDef = { id: string, rarity: string, chance: number, desc: string, mods: TraitMods }
export type SpotDef = { id: string, name: string, requiredPower: number, multiplier: number }

local GameConfig = {}

GameConfig.Rarities = { "Common", "Uncommon", "Rare", "Epic", "Legendary", "Mythic" }
GameConfig.RarityColors = {
	Common = Color3.fromHex("B8BCC8"),
	Uncommon = Color3.fromHex("5BD16B"),
	Rare = Color3.fromHex("4AA8FF"),
	Epic = Color3.fromHex("B565FF"),
	Legendary = Color3.fromHex("FFB52E"),
	Mythic = Color3.fromHex("FF4F7B"),
} :: { [string]: Color3 }

local function ability(name: string, cooldown: number, damage: number, hitsAll: boolean): Ability
	return { name = name, cooldown = cooldown, damage = damage, hitsAll = hitsAll }
end

-- damage = multiplier of a normal hit. hitsAll = hits every enemy of the fight, else the current target.
GameConfig.Stands = {
	BrickFist = { id = "BrickFist", name = "Brick Fist", rarity = "Common", forgeChance = 30, power = 2, speed = 2, durability = 4,
		skill = ability("Jab Rush", 6, 5, false), ultimate = ability("Wall Slam", 35, 18, false), order = 1 },
	PaperCrane = { id = "PaperCrane", name = "Paper Crane", rarity = "Common", forgeChance = 30, power = 2, speed = 4, durability = 2,
		skill = ability("Paper Cut", 6, 4, false), ultimate = ability("Thousand Folds", 35, 10, true), order = 2 },
	NeonBolt = { id = "NeonBolt", name = "Neon Bolt", rarity = "Uncommon", forgeChance = 15, power = 3, speed = 5, durability = 2,
		skill = ability("Volt Dash", 5, 4, true), ultimate = ability("Overcharge", 40, 14, false), order = 3 },
	Tidecaller = { id = "Tidecaller", name = "Tidecaller", rarity = "Uncommon", forgeChance = 15, power = 3, speed = 3, durability = 4,
		skill = ability("Bubble Shield", 8, 2, false), ultimate = ability("Riptide", 35, 11, true), order = 4 },
	EmberRonin = { id = "EmberRonin", name = "Ember Ronin", rarity = "Rare", forgeChance = 7, power = 5, speed = 5, durability = 3,
		skill = ability("Flame Draw", 6, 6, true), ultimate = ability("Burning Path", 35, 14, true), order = 5 },
	Gravewatch = { id = "Gravewatch", name = "Gravewatch", rarity = "Epic", forgeChance = 2.5, power = 6, speed = 3, durability = 7,
		skill = ability("Soul Lantern", 7, 6, false), ultimate = ability("Night Toll", 40, 16, true), order = 6 },
	Starforge = { id = "Starforge", name = "Starforge", rarity = "Legendary", forgeChance = 0.45, power = 8, speed = 6, durability = 7,
		skill = ability("Meteor Knuckle", 6, 8, false), ultimate = ability("Supernova", 45, 20, true), order = 7 },
	ChronoZero = { id = "ChronoZero", name = "Chrono Zero", rarity = "Mythic", forgeChance = 0.05, power = 9, speed = 9, durability = 6,
		skill = ability("Rewind", 8, 5, false), ultimate = ability("Frozen Second", 40, 24, true), order = 8 },
} :: { [string]: StandDef }

GameConfig.StarterStand = "BrickFist"

-- Roll chances add up to 100.
GameConfig.Traits = {
	{ id = "Sturdy", rarity = "Common", chance = 20, desc = "+10% Durability", mods = { durability = 0.10 } },
	{ id = "Strong", rarity = "Common", chance = 20, desc = "+10% Power", mods = { power = 0.10 } },
	{ id = "Quick", rarity = "Common", chance = 15, desc = "+10% Speed", mods = { speed = 0.10 } },
	{ id = "Diligent", rarity = "Uncommon", chance = 12, desc = "+15% training gain", mods = { training = 0.15 } },
	{ id = "Lucky", rarity = "Uncommon", chance = 12, desc = "+10% chance of rarer fragments", mods = { fragmentLuck = 0.10 } },
	{ id = "Focused", rarity = "Rare", chance = 9, desc = "-20% Skill cooldown", mods = { skillCooldown = 0.20 } },
	{ id = "Vampiric", rarity = "Rare", chance = 6, desc = "Heal 5% of damage dealt", mods = { lifesteal = 0.05 } },
	{ id = "Overdrive", rarity = "Epic", chance = 4, desc = "-25% Ultimate cooldown, +15% Power", mods = { ultimateCooldown = 0.25, power = 0.15 } },
	{ id = "Echo", rarity = "Legendary", chance = 1.8, desc = "Ultimate hits twice", mods = { ultimateRepeat = 1 } },
	{ id = "Ascended", rarity = "Mythic", chance = 0.2, desc = "+50% all stats and a golden aura", mods = { allStats = 0.50 } },
} :: { TraitDef }

GameConfig.TrainingSpots = {
	{ id = "PunchingBag", name = "Punching Bag", requiredPower = 0, multiplier = 1 },
	{ id = "Boulder", name = "Boulder", requiredPower = 1_000, multiplier = 3 },
	{ id = "IronPillar", name = "Iron Pillar", requiredPower = 25_000, multiplier = 10 },
	{ id = "Meteor", name = "Meteor", requiredPower = 500_000, multiplier = 40 },
} :: { SpotDef }

GameConfig.Training = {
	critChance = 0.05,
	critMultiplier = 10,
	spotRange = 12, -- studs from a spot's pad centre to count as training there
	punchesPerSecond = 6, -- sustained server limit (burst a little higher)
	autoInterval = 0.3, -- seconds between auto-train punches
}

GameConfig.Combat = {
	zones = 5,
	stagesPerZone = 5,
	maxStage = 25,
	bossEvery = 5,
	enemiesPerStage = 3,
	enemyBaseHP = 30,
	enemyHPGrowth = 1.6, -- per stage
	bossHPMult = 6,
	enemyHitFraction = 0.06, -- an enemy hit deals this share of its own max HP
	enemyAttackInterval = 1.6,
	enemySpeed = 9,
	enemyReach = 5,
	playerBaseHP = 100,
	playerHPPerPower = 0.2,
	damagePerPower = 0.05,
	attackRange = 18,
	baseAttackInterval = 0.45, -- seconds, shortened by Speed
	timeLimit = 120,
	leashDistance = 90, -- leaving the zone this far forfeits the fight
	coinsBase = 10,
	coinsGrowth = 1.3,
	bossCoinMult = 3,
}

-- Fragment rarity weights per zone (drops get rarer the deeper you go).
GameConfig.FragmentDrops = {
	{ Common = 85, Uncommon = 15 },
	{ Common = 60, Uncommon = 32, Rare = 8 },
	{ Common = 35, Uncommon = 40, Rare = 20, Epic = 5 },
	{ Uncommon = 35, Rare = 40, Epic = 20, Legendary = 5 },
	{ Rare = 40, Epic = 38, Legendary = 20, Mythic = 2 },
} :: { { [string]: number } }

-- Stat 1..10 -> multiplier (2 -> 1.25x, 9 -> 3x).
function GameConfig.StatMult(stat: number): number
	return 1 + (stat - 1) * 0.25
end

function GameConfig.GetTrait(id: string?): TraitDef?
	for _, t in GameConfig.Traits do
		if t.id == id then
			return t
		end
	end
	return nil
end

function GameConfig.EnemyHP(stage: number): number
	local c = GameConfig.Combat
	return math.floor(c.enemyBaseHP * c.enemyHPGrowth ^ (stage - 1))
end

function GameConfig.IsBoss(stage: number): boolean
	return stage % GameConfig.Combat.bossEvery == 0
end

function GameConfig.ZoneOf(stage: number): number
	return math.clamp(math.ceil(stage / GameConfig.Combat.stagesPerZone), 1, GameConfig.Combat.zones)
end

function GameConfig.StageCoins(stage: number): number
	local c = GameConfig.Combat
	local coins = math.floor(c.coinsBase * c.coinsGrowth ^ (stage - 1))
	return if GameConfig.IsBoss(stage) then coins * c.bossCoinMult else coins
end

return GameConfig
