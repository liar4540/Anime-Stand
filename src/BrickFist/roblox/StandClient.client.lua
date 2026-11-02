--!strict
-- StarterPlayer/StarterPlayerScripts/StandClient
-- Input (Q summon, click M1 combo, hold E barrage, R heavy) + renders every player's Stand locally
-- from replicated Player attributes. Stands are local clones: smooth, zero replication cost.

local ContextActionService = game:GetService("ContextActionService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local shared = ReplicatedStorage:WaitForChild("StandShared")
local StandAnimator = require(shared:WaitForChild("StandAnimator"))
local StandVFX = require(shared:WaitForChild("StandVFX"))
local Poses = require(shared:WaitForChild("BrickFistPoses"))
local remotes = ReplicatedStorage:WaitForChild("StandRemotes")
local actionRemote = remotes:WaitForChild("StandAction") :: RemoteEvent
local hitRemote = remotes:WaitForChild("StandHit") :: RemoteEvent
local template = ReplicatedStorage:WaitForChild("Stands"):WaitForChild("BrickFist") :: Model

local localPlayer = Players.LocalPlayer

-- where the Stand hovers relative to its user
local IDLE_OFFSET = CFrame.new(1.9, 0.7, 2.4)
local ATTACK_OFFSET = CFrame.new(0, 0.4, -3.2)
local FADE_SPEED = 2.4

type Stand = {
    owner: Player,
    model: Model,
    anim: StandAnimator.StandAnimator,
    vfx: StandVFX.Handle,
    fade: number,
    leaving: boolean,
    cf: CFrame?,
    connections: { RBXScriptConnection },
}
local stands: { [Player]: Stand } = {}

local function ownerRoot(player: Player): BasePart?
    local char = player.Character
    return char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
end

local function despawn(stand: Stand)
    stand.leaving = true
end

local function spawnStand(player: Player)
    local existing = stands[player]
    if existing then
        existing.leaving = false
        return
    end
    local root = ownerRoot(player)
    if not root then
        return
    end
    local model = template:Clone()
    local anim = StandAnimator.new(model)
    local vfx = StandVFX.Attach(model)
    vfx.SetFade(0)
    model:PivotTo(root.CFrame * IDLE_OFFSET)
    model.Parent = workspace
    anim:Play("Summon")
    StandVFX.Summon((root.CFrame * IDLE_OFFSET).Position - Vector3.new(0, 3, 0))

    local stand: Stand = {
        owner = player, model = model, anim = anim, vfx = vfx,
        fade = 0, leaving = false, cf = nil, connections = {},
    }
    table.insert(stand.connections, player:GetAttributeChangedSignal("StandState"):Connect(function()
        local s = player:GetAttribute("StandState")
        if s == "Barrage" then
            anim:Play("Barrage")
        elseif anim.state == "Barrage" then
            anim:Play("Idle")
        end
    end))
    table.insert(stand.connections, player:GetAttributeChangedSignal("StandHeavy"):Connect(function()
        anim:Play("Heavy")
    end))
    table.insert(stand.connections, player:GetAttributeChangedSignal("StandM1"):Connect(function()
        local n = player:GetAttribute("StandM1")
        if typeof(n) == "number" and n > 0 then
            anim:PlayM1(n % 10)
        end
    end))
    stands[player] = stand
end

local function watch(player: Player)
    player:GetAttributeChangedSignal("StandActive"):Connect(function()
        if player:GetAttribute("StandActive") then
            spawnStand(player)
        elseif stands[player] then
            despawn(stands[player])
        end
    end)
    if player:GetAttribute("StandActive") then
        spawnStand(player)
    end
end
Players.PlayerAdded:Connect(watch)
for _, p in Players:GetPlayers() do
    watch(p)
end
Players.PlayerRemoving:Connect(function(p)
    if stands[p] then
        despawn(stands[p])
    end
end)

local function fistWorld(stand: Stand, side: string): Vector3?
    local hand = stand.model:FindFirstChild(side .. "Hand")
    local center = hand and hand:FindFirstChild("FistCenter") :: Attachment?
    return center and center.WorldPosition
end

RunService.PreSimulation:Connect(function(dt)
    for player, stand in stands do
        local root = ownerRoot(player)
        if not root or not stand.model.Parent then
            stand.leaving = true
        end

        -- fade in / out (unsummon sinks and dissolves before cleanup)
        stand.fade = math.clamp(stand.fade + (if stand.leaving then -dt else dt) * FADE_SPEED, 0, 1)
        stand.vfx.SetFade(stand.fade)
        if stand.leaving and stand.fade <= 0 then
            for _, c in stand.connections do
                c:Disconnect()
            end
            stand.model:Destroy()
            stands[player] = nil
            continue
        end

        -- follow: hover behind-right when idle, step in front to attack
        if root then
            local attacking = stand.anim.state == "Barrage" or stand.anim.state == "Heavy" or stand.anim.state == "M1"
            local goal = root.CFrame * (if attacking then ATTACK_OFFSET else IDLE_OFFSET)
            if stand.leaving then
                goal -= Vector3.new(0, 1.5 * (1 - stand.fade), 0)
            end
            local a = 1 - math.exp(-(if attacking then 18 else 9) * dt)
            stand.cf = if stand.cf then stand.cf:Lerp(goal, a) else goal
            stand.model:PivotTo(stand.cf :: CFrame)
        end

        local events = stand.anim:Step(dt)
        stand.vfx.SetTrails(
            stand.anim.state == "Barrage"
                or (stand.anim.state == "Heavy" and stand.anim.stateT > 0.3)
                or (stand.anim.state == "M1" and stand.anim.stateT > 0.04)
        )
        stand.vfx.Update(stand.anim.t, stand.anim:Charge())

        local look = (stand.cf or stand.model:GetPivot()).LookVector
        for _, ev in events do
            if ev == "HeavyImpact" then
                local pos = fistWorld(stand, "Right")
                if pos then
                    StandVFX.HeavyImpact(pos + look * 0.6, look)
                end
            elseif ev == "M1Impact" then
                local i = stand.anim.comboIndex
                local pos = fistWorld(stand, Poses.M1Sides[i])
                if pos and i == Poses.M1Hits then
                    StandVFX.ComboFinisher(pos + look * 0.6, look)
                elseif pos then
                    StandVFX.Punch(pos + look * 0.5, look)
                end
            else
                local pos = fistWorld(stand, if ev == "PunchRight" then "Right" else "Left")
                if pos then
                    StandVFX.Punch(pos + look * 0.5, look)
                end
            end
        end
    end
end)

hitRemote.OnClientEvent:Connect(function(kind: unknown, pos: unknown, _dir: unknown)
    if typeof(pos) ~= "Vector3" then
        return
    end
    StandVFX.HitSpark(pos)
    if kind == "Heavy" then
        StandVFX.Shake(pos, 0.03, 0.25)
    elseif kind == "M1Finisher" then
        StandVFX.Shake(pos, 0.018, 0.15)
    end
end)

-- input (ContextActionService also creates touch buttons on mobile)
local function bind(name: string, key: Enum.KeyCode, title: string, onBegin: string, onEnd: string?)
    ContextActionService:BindAction(name, function(_, inputState)
        if inputState == Enum.UserInputState.Begin then
            actionRemote:FireServer(onBegin)
        elseif onEnd and inputState == Enum.UserInputState.End then
            actionRemote:FireServer(onEnd)
        end
        return Enum.ContextActionResult.Sink
    end, true, key)
    ContextActionService:SetTitle(name, title)
end
bind("StandToggle", Enum.KeyCode.Q, "Stand", "Toggle")
bind("StandBarrage", Enum.KeyCode.E, "Barrage", "BarrageStart", "BarrageStop")
bind("StandHeavy", Enum.KeyCode.R, "Heavy", "Heavy")

-- M1 passes the click through while the Stand is away, so tools and the world still get it
ContextActionService:BindAction("StandM1", function(_, inputState)
    if not localPlayer:GetAttribute("StandActive") then
        return Enum.ContextActionResult.Pass
    end
    if inputState == Enum.UserInputState.Begin then
        actionRemote:FireServer("M1")
    end
    return Enum.ContextActionResult.Sink
end, true, Enum.UserInputType.MouseButton1, Enum.KeyCode.ButtonR2)
ContextActionService:SetTitle("StandM1", "Punch")
