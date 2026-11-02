--!strict
-- ServerScriptService/StandServer
-- Server-authoritative Stand logic: state, cooldowns, hitboxes, damage, knockback.
-- Visuals live on the client; the server only replicates state through Player attributes.

local Debris = game:GetService("Debris")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local CONFIG = {
    ToggleCooldown = 0.6,
    BarrageMaxDuration = 3.5,
    BarrageCooldown = 3,
    BarrageTick = 0.12,
    BarrageDamage = 1.6,
    HeavyCooldown = 4.5,
    HeavyImpactDelay = 0.46, -- matches BrickFistPoses.HeavyImpact
    HeavyRecover = 0.8,
    HeavyDamage = 18,
    HeavyKnockback = 55,
    M1Hits = 4,
    M1Interval = 0.3,
    M1ComboWindow = 0.9, -- combo resets if the next click is later than this
    M1FinisherCooldown = 0.9,
    M1ImpactDelay = 0.11, -- matches BrickFistPoses.M1Impact
    M1FinisherImpactDelay = 0.18, -- matches BrickFistPoses.M1FinisherImpact
    M1Damage = 4,
    M1FinisherDamage = 9,
    M1FinisherKnockback = 35,
    HitboxSize = Vector3.new(5, 6, 5.5),
    HitboxOffset = CFrame.new(0, 0, -4.5),
    MinRemoteInterval = 0.05,
}

local remotes = Instance.new("Folder")
remotes.Name = "StandRemotes"
remotes.Parent = ReplicatedStorage
local actionRemote = Instance.new("RemoteEvent")
actionRemote.Name = "StandAction"
actionRemote.Parent = remotes
local hitRemote = Instance.new("RemoteEvent")
hitRemote.Name = "StandHit"
hitRemote.Parent = remotes

type PlayerState = {
    lastRemote: number,
    lastToggle: number,
    barrageReadyAt: number,
    heavyReadyAt: number,
    barraging: boolean,
    heavyBusy: boolean,
    m1ReadyAt: number,
    m1BusyUntil: number,
    lastM1: number,
    m1Index: number,
    m1Serial: number,
}
local states: { [Player]: PlayerState } = {}

local function rootOf(player: Player): BasePart?
    local char = player.Character
    local hum = char and char:FindFirstChildOfClass("Humanoid")
    if not char or not hum or hum.Health <= 0 then
        return nil
    end
    return char:FindFirstChild("HumanoidRootPart") :: BasePart?
end

local function query(player: Player, root: BasePart): { Humanoid }
    local params = OverlapParams.new()
    params.FilterType = Enum.RaycastFilterType.Exclude
    params.FilterDescendantsInstances = { player.Character :: Model }
    local found, seen = {}, {}
    for _, part in workspace:GetPartBoundsInBox(root.CFrame * CONFIG.HitboxOffset, CONFIG.HitboxSize, params) do
        local model = part:FindFirstAncestorOfClass("Model")
        local hum = model and model:FindFirstChildOfClass("Humanoid")
        if hum and hum.Health > 0 and not seen[hum] then
            seen[hum] = true
            table.insert(found, hum)
        end
    end
    return found
end

local function knockback(hum: Humanoid, dir: Vector3, power: number)
    local target = hum.Parent and hum.Parent:FindFirstChild("HumanoidRootPart") :: BasePart?
    if not target then
        return
    end
    -- constraint (not a velocity set) so it also works on client-owned characters
    local att = Instance.new("Attachment")
    att.Parent = target
    local lv = Instance.new("LinearVelocity")
    lv.Attachment0 = att
    lv.MaxForce = 1e6
    lv.VectorVelocity = dir * power + Vector3.yAxis * power * 0.35
    lv.Parent = target
    Debris:AddItem(att, 0.18)
    Debris:AddItem(lv, 0.18)
end

local function stopBarrage(player: Player, state: PlayerState)
    if state.barraging then
        state.barraging = false
        state.barrageReadyAt = os.clock() + CONFIG.BarrageCooldown
        player:SetAttribute("StandState", "Idle")
    end
end

local handlers: { [string]: (Player, PlayerState) -> () } = {}

function handlers.Toggle(player, state)
    local now = os.clock()
    if now - state.lastToggle < CONFIG.ToggleCooldown or not rootOf(player) then
        return
    end
    state.lastToggle = now
    stopBarrage(player, state)
    player:SetAttribute("StandActive", not player:GetAttribute("StandActive"))
    player:SetAttribute("StandState", "Idle")
end

function handlers.M1(player, state)
    if not player:GetAttribute("StandActive") or state.barraging or state.heavyBusy then
        return
    end
    local now = os.clock()
    if now < state.m1ReadyAt then
        return
    end
    if now - state.lastM1 > CONFIG.M1ComboWindow then
        state.m1Index = 0
    end
    state.m1Index = state.m1Index % CONFIG.M1Hits + 1
    local index = state.m1Index
    local finisher = index == CONFIG.M1Hits
    state.lastM1 = now
    state.m1BusyUntil = now + CONFIG.M1Interval
    state.m1ReadyAt = now + (if finisher then CONFIG.M1FinisherCooldown else CONFIG.M1Interval)
    if finisher then
        state.m1Index = 0
    end
    -- serial*10 + index: a fresh value every swing, so repeated indices still replicate
    state.m1Serial += 1
    player:SetAttribute("StandM1", state.m1Serial * 10 + index)
    task.delay(if finisher then CONFIG.M1FinisherImpactDelay else CONFIG.M1ImpactDelay, function()
        local root = rootOf(player)
        if not root or not player:GetAttribute("StandActive") then
            return
        end
        for _, hum in query(player, root) do
            hum:TakeDamage(if finisher then CONFIG.M1FinisherDamage else CONFIG.M1Damage)
            if finisher then
                knockback(hum, root.CFrame.LookVector, CONFIG.M1FinisherKnockback)
            end
            local hit = hum.Parent and hum.Parent:FindFirstChild("HumanoidRootPart") :: BasePart?
            if hit then
                hitRemote:FireAllClients(if finisher then "M1Finisher" else "M1", hit.Position, root.CFrame.LookVector)
            end
        end
    end)
end

function handlers.BarrageStart(player, state)
    if not player:GetAttribute("StandActive") or state.barraging or state.heavyBusy then
        return
    end
    if os.clock() < state.m1BusyUntil then
        return
    end
    if os.clock() < state.barrageReadyAt then
        return
    end
    state.barraging = true
    player:SetAttribute("StandState", "Barrage")
    task.spawn(function()
        local started = os.clock()
        while state.barraging and os.clock() - started < CONFIG.BarrageMaxDuration do
            local root = rootOf(player)
            if not root then
                break
            end
            for _, hum in query(player, root) do
                hum:TakeDamage(CONFIG.BarrageDamage)
                local hit = hum.Parent and hum.Parent:FindFirstChild("HumanoidRootPart") :: BasePart?
                if hit then
                    hitRemote:FireAllClients("Barrage", hit.Position, root.CFrame.LookVector)
                end
            end
            task.wait(CONFIG.BarrageTick)
        end
        stopBarrage(player, state)
    end)
end

function handlers.BarrageStop(player, state)
    stopBarrage(player, state)
end

function handlers.Heavy(player, state)
    if not player:GetAttribute("StandActive") or state.barraging or state.heavyBusy then
        return
    end
    if os.clock() < state.heavyReadyAt or os.clock() < state.m1BusyUntil then
        return
    end
    state.heavyBusy = true
    state.heavyReadyAt = os.clock() + CONFIG.HeavyCooldown
    player:SetAttribute("StandHeavy", ((player:GetAttribute("StandHeavy") :: number?) or 0) + 1)
    task.delay(CONFIG.HeavyImpactDelay, function()
        local root = rootOf(player)
        if root and player:GetAttribute("StandActive") then
            for _, hum in query(player, root) do
                hum:TakeDamage(CONFIG.HeavyDamage)
                knockback(hum, root.CFrame.LookVector, CONFIG.HeavyKnockback)
                local hit = hum.Parent and hum.Parent:FindFirstChild("HumanoidRootPart") :: BasePart?
                if hit then
                    hitRemote:FireAllClients("Heavy", hit.Position, root.CFrame.LookVector)
                end
            end
        end
        task.wait(CONFIG.HeavyRecover)
        state.heavyBusy = false
    end)
end

actionRemote.OnServerEvent:Connect(function(player: Player, action: unknown)
    local state = states[player]
    if not state or typeof(action) ~= "string" or not handlers[action] then
        return
    end
    local now = os.clock()
    if now - state.lastRemote < CONFIG.MinRemoteInterval then
        return
    end
    state.lastRemote = now
    handlers[action](player, state)
end)

local function onPlayer(player: Player)
    states[player] = {
        lastRemote = 0, lastToggle = 0, barrageReadyAt = 0, heavyReadyAt = 0,
        barraging = false, heavyBusy = false,
        m1ReadyAt = 0, m1BusyUntil = 0, lastM1 = 0, m1Index = 0, m1Serial = 0,
    }
    player:SetAttribute("StandActive", false)
    player:SetAttribute("StandState", "Idle")
    player:SetAttribute("StandHeavy", 0)
    player:SetAttribute("StandM1", 0)
    player.CharacterAdded:Connect(function(char)
        local state = states[player]
        if state then
            stopBarrage(player, state)
        end
        player:SetAttribute("StandActive", false)
        local hum = char:WaitForChild("Humanoid") :: Humanoid
        hum.Died:Connect(function()
            player:SetAttribute("StandActive", false)
        end)
    end)
end

Players.PlayerAdded:Connect(onPlayer)
for _, p in Players:GetPlayers() do
    onPlayer(p)
end
Players.PlayerRemoving:Connect(function(player)
    local state = states[player]
    if state then
        state.barraging = false
    end
    states[player] = nil
end)
