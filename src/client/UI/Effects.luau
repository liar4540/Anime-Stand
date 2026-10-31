--!strict
-- Client-only game feel: floating +numbers, hit sparks, a small stand lunge, crit flash and camera shake.
-- Purely visual; nothing here changes game state.
local Debris = game:GetService("Debris")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local Effects = {}

local fxFolder = Instance.new("Folder")
fxFolder.Name = "ClientFX"
fxFolder.Parent = workspace

local function anchorPart(at: Vector3): Part
	local p = Instance.new("Part")
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Transparency = 1
	p.Size = Vector3.new(0.2, 0.2, 0.2)
	p.CFrame = CFrame.new(at)
	p.Parent = fxFolder
	return p
end

function Effects.FloatText(at: Vector3, str: string, color: Color3, big: boolean?)
	local p = anchorPart(at + Vector3.new(math.random(-10, 10) / 10, 0, math.random(-10, 10) / 10))
	local bb = Instance.new("BillboardGui")
	bb.Size = UDim2.fromOffset(if big then 220 else 150, if big then 70 else 46)
	bb.AlwaysOnTop = true
	bb.LightInfluence = 0
	local t = Instance.new("TextLabel")
	t.BackgroundTransparency = 1
	t.Size = UDim2.fromScale(1, 1)
	t.Font = Enum.Font.FredokaOne
	t.TextScaled = true
	t.Text = str
	t.TextColor3 = color
	local s = Instance.new("UIStroke")
	s.Thickness = 3
	s.Color = Color3.fromHex("1E1B33")
	s.Parent = t
	t.Parent = bb
	bb.Parent = p
	TweenService:Create(p, TweenInfo.new(0.9, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), { CFrame = p.CFrame + Vector3.new(0, 4, 0) }):Play()
	TweenService:Create(t, TweenInfo.new(0.5, Enum.EasingStyle.Quad, Enum.EasingDirection.In, 0, false, 0.45), { TextTransparency = 1 }):Play()
	TweenService:Create(s, TweenInfo.new(0.5, Enum.EasingStyle.Quad, Enum.EasingDirection.In, 0, false, 0.45), { Transparency = 1 }):Play()
	Debris:AddItem(p, 1.1)
end

function Effects.Spark(at: Vector3, color: Color3, big: boolean?)
	local p = anchorPart(at)
	local att = Instance.new("Attachment")
	att.Parent = p
	local pe = Instance.new("ParticleEmitter")
	pe.Color = ColorSequence.new(color, Color3.new(1, 1, 1))
	pe.LightEmission = 1
	pe.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, if big then 1.2 else 0.7), NumberSequenceKeypoint.new(1, 0) })
	pe.Speed = NumberRange.new(10, if big then 26 else 16)
	pe.SpreadAngle = Vector2.new(180, 180)
	pe.Lifetime = NumberRange.new(0.2, 0.4)
	pe.Drag = 6
	pe.Rate = 0
	pe.Parent = att
	pe:Emit(if big then 30 else 12)
	-- quick flash ring
	local ring = Instance.new("Part")
	ring.Shape = Enum.PartType.Ball
	ring.Material = Enum.Material.Neon
	ring.Color = color
	ring.Anchored = true
	ring.CanCollide = false
	ring.CanQuery = false
	ring.CanTouch = false
	ring.Size = Vector3.new(0.6, 0.6, 0.6)
	ring.CFrame = CFrame.new(at)
	ring.Transparency = 0.2
	ring.Parent = fxFolder
	local grow = if big then 5 else 3
	TweenService:Create(ring, TweenInfo.new(0.18, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), { Size = Vector3.new(grow, grow, grow), Transparency = 1 }):Play()
	Debris:AddItem(ring, 0.25)
	Debris:AddItem(p, 0.6)
end

-- Nudge the stand forward along its weld and back (local only; the weld is on the player's own character).
function Effects.Lunge()
	local char = Players.LocalPlayer.Character
	local stand = char and char:FindFirstChild("Stand")
	local root = stand and stand:IsA("Model") and stand.PrimaryPart
	local weld = root and root:FindFirstChild("StandWeld")
	if not weld or not weld:IsA("Weld") then
		return
	end
	local base = weld:GetAttribute("BaseC0")
	if typeof(base) ~= "CFrame" then
		base = weld.C0
		weld:SetAttribute("BaseC0", base)
	end
	local b = base :: CFrame
	weld.C0 = b * CFrame.new(-1.4, 0, -2.2)
	TweenService:Create(weld, TweenInfo.new(0.16, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), { C0 = b }):Play()
end

-- Point in front of the stand (where its punch lands).
function Effects.StandFront(): Vector3?
	local char = Players.LocalPlayer.Character
	local stand = char and char:FindFirstChild("Stand")
	local root = stand and stand:IsA("Model") and stand.PrimaryPart
	if root then
		return (root.CFrame * CFrame.new(-1, 1, -3)).Position
	end
	local hrp = char and char:FindFirstChild("HumanoidRootPart")
	return if hrp and hrp:IsA("BasePart") then (hrp.CFrame * CFrame.new(0, 1, -3)).Position else nil
end

local shakeUntil = 0
local shakeMag = 0
function Effects.Shake(mag: number, seconds: number)
	shakeMag = math.max(shakeMag, mag)
	shakeUntil = math.max(shakeUntil, os.clock() + seconds)
end

RunService.RenderStepped:Connect(function()
	local char = Players.LocalPlayer.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	if not hum then
		return
	end
	if os.clock() < shakeUntil then
		hum.CameraOffset = Vector3.new((math.random() - 0.5) * shakeMag, (math.random() - 0.5) * shakeMag, 0)
	elseif shakeMag > 0 then
		shakeMag = 0
		hum.CameraOffset = Vector3.zero
	end
end)

return Effects
