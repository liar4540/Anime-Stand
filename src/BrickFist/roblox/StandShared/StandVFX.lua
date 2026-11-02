--!strict
-- Client-side Stand VFX: clean trails, subtle glow, readable impacts.
-- Uses only built-in rbxasset textures, so nothing needs uploading.

local Debris = game:GetService("Debris")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local GLOW = Color3.fromRGB(255, 194, 71)
local CLAY = Color3.fromRGB(181, 120, 79)
local CLAY_DARK = Color3.fromRGB(120, 72, 44)
local DUST = Color3.fromRGB(168, 130, 98)
local TEX_SMOKE = "rbxasset://textures/particles/smoke_main.dds"
local TEX_SPARK = "rbxasset://textures/particles/sparkles_main.dds"

local StandVFX = {}

local fxFolder = Instance.new("Folder")
fxFolder.Name = "StandFX"
fxFolder.Parent = workspace

local function seq(a: number, b: number): NumberSequence
    return NumberSequence.new(a, b)
end

-- lookAt that stays valid when aiming straight up/down
local function aim(pos: Vector3, dir: Vector3): CFrame
    local d = if dir.Magnitude > 0 then dir.Unit else -Vector3.zAxis
    local up = if math.abs(d.Y) > 0.99 then Vector3.zAxis else Vector3.yAxis
    return CFrame.lookAt(pos, pos + d, up)
end

local function find(model: Model, segment: string, child: string): Instance?
    local seg = model:FindFirstChild(segment)
    return seg and seg:FindFirstChild(child)
end

-- invisible anchored holder whose -Z faces `dir`, so EmissionDirection.Front follows it
local function holder(pos: Vector3, dir: Vector3, life: number): (Part, Attachment)
    local p = Instance.new("Part")
    p.Anchored = true
    p.CanCollide, p.CanTouch, p.CanQuery = false, false, false
    p.Transparency = 1
    p.Size = Vector3.one * 0.2
    p.CFrame = aim(pos, dir)
    local a = Instance.new("Attachment")
    a.Parent = p
    p.Parent = fxFolder
    Debris:AddItem(p, life)
    return p, a
end

local function dust(parent: Attachment, size: number, speed: NumberRange, spread: number): ParticleEmitter
    local e = Instance.new("ParticleEmitter")
    e.Texture = TEX_SMOKE
    e.Color = ColorSequence.new(DUST, CLAY_DARK)
    e.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, size * 0.5), NumberSequenceKeypoint.new(1, size * 1.6) })
    e.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.35), NumberSequenceKeypoint.new(1, 1) })
    e.Lifetime = NumberRange.new(0.35, 0.6)
    e.Speed = speed
    e.Drag = 6
    e.SpreadAngle = Vector2.new(spread, spread)
    e.EmissionDirection = Enum.NormalId.Front
    e.Rotation = NumberRange.new(0, 360)
    e.RotSpeed = NumberRange.new(-90, 90)
    e.Enabled = false
    e.Parent = parent
    return e
end

local function flash(parent: Attachment, size: number): ParticleEmitter
    local e = Instance.new("ParticleEmitter")
    e.Texture = TEX_SPARK
    e.Color = ColorSequence.new(GLOW)
    e.LightEmission = 1
    e.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, size), NumberSequenceKeypoint.new(1, size * 1.8) })
    e.Transparency = seq(0, 1)
    e.Lifetime = NumberRange.new(0.08, 0.12)
    e.Speed = NumberRange.new(0)
    e.Enabled = false
    e.Parent = parent
    return e
end

local function shockwave(pos: Vector3, dir: Vector3, size: number, duration: number)
    local ring = Instance.new("Part")
    ring.Shape = Enum.PartType.Cylinder
    ring.Material = Enum.Material.Neon
    ring.Color = GLOW
    ring.Anchored = true
    ring.CanCollide, ring.CanTouch, ring.CanQuery = false, false, false
    ring.CastShadow = false
    ring.Transparency = 0.25
    ring.Size = Vector3.new(0.12, 0.6, 0.6)
    -- cylinder axis is local X; aim it along the hit direction
    ring.CFrame = aim(pos, dir) * CFrame.Angles(0, math.rad(90), 0)
    ring.Parent = fxFolder
    TweenService:Create(ring, TweenInfo.new(duration, Enum.EasingStyle.Quart, Enum.EasingDirection.Out), {
        Size = Vector3.new(0.04, size, size),
        Transparency = 1,
    }):Play()
    Debris:AddItem(ring, duration + 0.05)
end

local function lightPop(parent: Instance, brightness: number, range: number, duration: number)
    local l = Instance.new("PointLight")
    l.Color = GLOW
    l.Range = range
    l.Brightness = brightness
    l.Shadows = false
    l.Parent = parent
    TweenService:Create(l, TweenInfo.new(duration, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), { Brightness = 0 }):Play()
end

local function bricks(pos: Vector3, dir: Vector3, count: number, force: number)
    local rng = Random.new()
    for _ = 1, count do
        local b = Instance.new("Part")
        b.Size = Vector3.new(rng:NextNumber(0.3, 0.55), rng:NextNumber(0.16, 0.26), rng:NextNumber(0.2, 0.32))
        b.Color = CLAY:Lerp(CLAY_DARK, rng:NextNumber(0, 0.6))
        b.Material = Enum.Material.SmoothPlastic
        b.CanTouch, b.CanQuery = false, false
        b.CFrame = CFrame.new(pos + rng:NextUnitVector() * 0.4) * CFrame.Angles(rng:NextNumber(0, 6), rng:NextNumber(0, 6), 0)
        b.Parent = fxFolder
        local spray = (dir.Unit + rng:NextUnitVector() * 0.7 + Vector3.yAxis * 0.5).Unit
        b.AssemblyLinearVelocity = spray * force * rng:NextNumber(0.6, 1.1)
        b.AssemblyAngularVelocity = rng:NextUnitVector() * 15
        task.delay(0.9, function()
            TweenService:Create(b, TweenInfo.new(0.5), { Transparency = 1, Size = b.Size * 0.4 }):Play()
        end)
        Debris:AddItem(b, 1.5)
    end
end

-- camera shake (local player only), decays smoothly
local shakeT, shakeDur, shakeMag = 0, 1, 0
RunService:BindToRenderStep("StandShake", Enum.RenderPriority.Camera.Value + 1, function(dt)
    if shakeT <= 0 then
        return
    end
    shakeT -= dt
    local m = shakeMag * math.max(shakeT / shakeDur, 0) ^ 2
    local cam = workspace.CurrentCamera
    if cam then
        cam.CFrame *= CFrame.Angles((math.random() - 0.5) * m, (math.random() - 0.5) * m, 0)
    end
end)

function StandVFX.Shake(pos: Vector3, magnitude: number, duration: number)
    local cam = workspace.CurrentCamera
    if not cam then
        return
    end
    local falloff = math.clamp(1 - (cam.Focus.Position - pos).Magnitude / 40, 0, 1)
    if falloff * magnitude > shakeMag * (shakeT / shakeDur) then
        shakeT, shakeDur, shakeMag = duration, duration, magnitude * falloff
    end
end

-- ---------------------------------------------------------------- one-shots
function StandVFX.Punch(pos: Vector3, dir: Vector3)
    local _, a = holder(pos, dir, 1)
    dust(a, 0.9, NumberRange.new(4, 7), 35):Emit(3)
    flash(a, 1.6):Emit(1)
end

function StandVFX.HeavyImpact(pos: Vector3, dir: Vector3)
    local p, a = holder(pos, dir, 2)
    flash(a, 5):Emit(1)
    dust(a, 2.2, NumberRange.new(10, 18), 55):Emit(16)
    shockwave(pos, dir, 11, 0.4)
    task.delay(0.06, shockwave, pos + dir * 0.8, dir, 7, 0.32)
    lightPop(p, 6, 14, 0.35)
    bricks(pos, dir, 10, 32)
    StandVFX.Shake(pos, 0.045, 0.35)
end

function StandVFX.ComboFinisher(pos: Vector3, dir: Vector3)
    local p, a = holder(pos, dir, 1.5)
    flash(a, 3):Emit(1)
    dust(a, 1.4, NumberRange.new(7, 12), 45):Emit(9)
    shockwave(pos, dir, 7, 0.3)
    lightPop(p, 4, 10, 0.25)
    bricks(pos, dir, 5, 22)
    StandVFX.Shake(pos, 0.025, 0.2)
end

function StandVFX.HitSpark(pos: Vector3)
    local _, a = holder(pos, Vector3.yAxis, 1)
    flash(a, 2.2):Emit(1)
    dust(a, 0.7, NumberRange.new(3, 6), 180):Emit(2)
end

function StandVFX.Summon(pos: Vector3)
    local p, a = holder(pos, Vector3.yAxis, 2)
    dust(a, 1.8, NumberRange.new(6, 10), 80):Emit(14)
    shockwave(pos, Vector3.yAxis, 9, 0.5)
    lightPop(p, 3, 10, 0.5)
    bricks(pos, Vector3.yAxis, 6, 18)
end

-- ---------------------------------------------------------------- persistent
export type Handle = {
    SetTrails: (on: boolean) -> (),
    SetFade: (alpha: number) -> (),
    Update: (t: number, charge: number) -> (),
}

function StandVFX.Attach(model: Model): Handle
    local trails: { Trail } = {}
    local parts: { BasePart } = {}
    local glows: { BasePart } = {}
    for _, d in model:GetDescendants() do
        if d:IsA("MeshPart") then
            table.insert(parts, d)
            if d:GetAttribute("StandMaterial") == "Glow" then
                table.insert(glows, d)
            end
        end
    end
    for _, side in { "Right", "Left" } do
        local hand = model:FindFirstChild(side .. "Hand")
        local top = hand and hand:FindFirstChild("TrailTop")
        local bottom = hand and hand:FindFirstChild("TrailBottom")
        if hand and top and bottom then
            local tr = Instance.new("Trail")
            tr.Attachment0 = top :: Attachment
            tr.Attachment1 = bottom :: Attachment
            tr.Color = ColorSequence.new(GLOW, CLAY)
            tr.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.2), NumberSequenceKeypoint.new(1, 1) })
            tr.WidthScale = NumberSequence.new(1, 0.2)
            tr.Lifetime = 0.14
            tr.LightEmission = 0.6
            tr.FaceCamera = true
            tr.Enabled = false
            tr.Parent = hand
            table.insert(trails, tr)
        end
    end

    local fistLight = Instance.new("PointLight")
    fistLight.Color, fistLight.Range, fistLight.Brightness, fistLight.Shadows = GLOW, 7, 0, false
    fistLight.Parent = find(model, "RightHand", "FistCenter") or model.PrimaryPart

    local eyeLight = Instance.new("PointLight")
    eyeLight.Color, eyeLight.Range, eyeLight.Brightness, eyeLight.Shadows = GLOW, 4, 0.8, false
    eyeLight.Parent = find(model, "Head", "Eyes") or model.PrimaryPart

    local aura = Instance.new("ParticleEmitter")
    aura.Texture = TEX_SMOKE
    aura.Color = ColorSequence.new(DUST)
    aura.Size = NumberSequence.new(0.25, 0.6)
    aura.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(0.3, 0.75), NumberSequenceKeypoint.new(1, 1) })
    aura.Lifetime = NumberRange.new(1.5, 2.5)
    aura.Rate = 5
    aura.Speed = NumberRange.new(0.3, 0.8)
    aura.SpreadAngle = Vector2.new(180, 180)
    aura.Acceleration = Vector3.new(0, 0.6, 0)
    aura.Parent = find(model, "HumanoidRootPart", "Aura") or model.PrimaryPart

    local handle: Handle = {
        SetTrails = function(on: boolean)
            for _, tr in trails do
                tr.Enabled = on
            end
        end,
        SetFade = function(alpha: number)
            for _, p in parts do
                p.LocalTransparencyModifier = 1 - alpha
            end
            aura.Enabled = alpha > 0.5
        end,
        Update = function(t: number, charge: number)
            local pulse = 0.5 + 0.5 * math.sin(t * 3)
            local c = GLOW:Lerp(Color3.new(1, 0.93, 0.7), pulse * 0.35 + charge * 0.65)
            for _, g in glows do
                g.Color = c
            end
            eyeLight.Brightness = 0.6 + pulse * 0.4 + charge * 1.5
            fistLight.Brightness = charge * 4
        end,
    }
    return handle
end

return StandVFX
