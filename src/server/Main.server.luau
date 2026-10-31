--!strict
-- +1 Anime Stand: the only server Script. Wiring order (LihFolk Systems): PlayerData.Configure -> service Init
-- (each registers its profile slice and remotes) -> PlayerData.Start (loads players).
local ServerScriptService = game:GetService("ServerScriptService")

local PlayerData = require(ServerScriptService:WaitForChild("LihFolk"):WaitForChild("PlayerData"))
local Services = script.Parent:WaitForChild("Services")
local Stats = require(Services:WaitForChild("Stats"))
local Stands = require(Services:WaitForChild("Stands"))
local Training = require(Services:WaitForChild("Training"))
local Fight = require(Services:WaitForChild("Fight"))

PlayerData.Configure({
	storeName = "AnimeStand_Player_v1", -- never rename after launch
	schemaVersion = 1,
	migrations = {},
})

Stats.Init()
Stands.Init()
Training.Init()
Fight.Init()

PlayerData.Start()
print("[AnimeStand] server ready")
