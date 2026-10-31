--!strict
-- HUD: mobile-first, one thumb. Bottom-right: big PUNCH button, AUTO toggle; in fights also SKILL and ULT
-- with cooldown sweeps and a LEAVE button. Top-left: Power / Coins / Stage / fragments. Top-centre: fight bar.
-- Centre: short toasts. Built in code so it stays in sync with the Rojo source.
local Players = game:GetService("Players")
local TweenService = game:GetService("TweenService")

local Hud = {}

local FONT = Enum.Font.FredokaOne
local INK = Color3.fromHex("1E1B33")

local function corner(p: Instance, r: number)
	local c = Instance.new("UICorner")
	c.CornerRadius = UDim.new(0, r)
	c.Parent = p
end

local function stroke(p: Instance, t: number, col: Color3?)
	local s = Instance.new("UIStroke")
	s.Thickness = t
	s.Color = col or INK
	s.ApplyStrokeMode = Enum.ApplyStrokeMode.Border
	s.Parent = p
end

local function text(parent: Instance, name: string, str: string, size: UDim2, pos: UDim2, color: Color3?): TextLabel
	local t = Instance.new("TextLabel")
	t.Name = name
	t.BackgroundTransparency = 1
	t.Size = size
	t.Position = pos
	t.Font = FONT
	t.TextScaled = true
	t.Text = str
	t.TextColor3 = color or Color3.new(1, 1, 1)
	t.TextXAlignment = Enum.TextXAlignment.Left
	local s = Instance.new("UIStroke")
	s.Thickness = 2
	s.Color = INK
	s.Parent = t
	t.Parent = parent
	return t
end

local function button(parent: Instance, name: string, label: string, size: UDim2, pos: UDim2, color: Color3): TextButton
	local b = Instance.new("TextButton")
	b.Name = name
	b.Size = size
	b.Position = pos
	b.AnchorPoint = Vector2.new(1, 1)
	b.BackgroundColor3 = color
	b.AutoButtonColor = true
	b.Font = FONT
	b.TextScaled = true
	b.Text = label
	b.TextColor3 = Color3.new(1, 1, 1)
	corner(b, 18)
	stroke(b, 3)
	local pad = Instance.new("UIPadding")
	pad.PaddingLeft = UDim.new(0.12, 0)
	pad.PaddingRight = UDim.new(0.12, 0)
	pad.PaddingTop = UDim.new(0.2, 0)
	pad.PaddingBottom = UDim.new(0.2, 0)
	pad.Parent = b
	local ts = Instance.new("UIStroke")
	ts.ApplyStrokeMode = Enum.ApplyStrokeMode.Contextual
	ts.Thickness = 2
	ts.Color = INK
	ts.Parent = b
	b.Parent = parent
	return b
end

-- Cooldown sweep: a dark overlay that shrinks from full to empty over `seconds`.
local function cooldownOverlay(b: TextButton): Frame
	local o = Instance.new("Frame")
	o.Name = "Cooldown"
	o.BackgroundColor3 = Color3.new(0, 0, 0)
	o.BackgroundTransparency = 0.45
	o.AnchorPoint = Vector2.new(0, 1)
	o.Position = UDim2.fromScale(0, 1)
	o.Size = UDim2.fromScale(1, 0)
	o.ZIndex = 5
	corner(o, 18)
	o.Parent = b
	return o
end

export type HudApi = {
	gui: ScreenGui,
	punch: TextButton,
	auto: TextButton,
	skill: TextButton,
	ult: TextButton,
	leave: TextButton,
	stands: TextButton,
	setStats: (power: string, coins: string, stage: string, frags: string, stand: string) -> (),
	setAuto: (on: boolean) -> (),
	setFight: (state: { [string]: any }?) -> (),
	cooldown: (kind: string, seconds: number) -> (),
	toast: (msg: string, color: Color3?) -> (),
	pulse: (b: GuiObject) -> (),
}

function Hud.Create(): HudApi
	local player = Players.LocalPlayer
	local gui = Instance.new("ScreenGui")
	gui.Name = "AnimeStandHud"
	gui.ResetOnSpawn = false
	gui.IgnoreGuiInset = false
	gui.ScreenInsets = Enum.ScreenInsets.CoreUISafeInsets
	gui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling

	local scale = Instance.new("UIScale")
	scale.Parent = gui
	local function rescale()
		local cam = workspace.CurrentCamera
		local vp = if cam then cam.ViewportSize else Vector2.new(1280, 720)
		scale.Scale = math.clamp(math.min(vp.X / 1100, vp.Y / 640), 0.6, 1.25)
	end
	rescale()
	if workspace.CurrentCamera then
		workspace.CurrentCamera:GetPropertyChangedSignal("ViewportSize"):Connect(rescale)
	end

	-- stats panel
	local panel = Instance.new("Frame")
	panel.Name = "Stats"
	panel.Size = UDim2.fromOffset(250, 150)
	panel.Position = UDim2.fromOffset(12, 12)
	panel.BackgroundColor3 = Color3.fromHex("2B2752")
	panel.BackgroundTransparency = 0.15
	corner(panel, 14)
	stroke(panel, 3)
	panel.Parent = gui
	local power = text(panel, "Power", "Power 0", UDim2.new(1, -20, 0, 34), UDim2.fromOffset(12, 8), Color3.fromHex("FFD23F"))
	local coins = text(panel, "Coins", "Coins 0", UDim2.new(1, -20, 0, 26), UDim2.fromOffset(12, 44), Color3.fromHex("FFE680"))
	local stage = text(panel, "Stage", "Stage 0", UDim2.new(1, -20, 0, 22), UDim2.fromOffset(12, 72), Color3.fromHex("9EE6FF"))
	local frags = text(panel, "Frags", "", UDim2.new(1, -20, 0, 18), UDim2.fromOffset(12, 98), Color3.fromHex("E3D7FF"))
	local stand = text(panel, "Stand", "", UDim2.new(1, -20, 0, 18), UDim2.fromOffset(12, 120), Color3.fromHex("C7F0C2"))

	-- action buttons (bottom-right, thumb zone)
	local punch = button(gui, "Punch", "PUNCH", UDim2.fromOffset(150, 150), UDim2.new(1, -16, 1, -16), Color3.fromHex("FF5A5A"))
	local pc = punch:FindFirstChildOfClass("UICorner")
	if pc then
		pc.CornerRadius = UDim.new(0.5, 0)
	end
	local auto = button(gui, "Auto", "AUTO: OFF", UDim2.fromOffset(150, 46), UDim2.new(1, -16, 1, -176), Color3.fromHex("5A6378"))
	local skill = button(gui, "Skill", "SKILL", UDim2.fromOffset(96, 96), UDim2.new(1, -178, 1, -16), Color3.fromHex("4AA8FF"))
	local ult = button(gui, "Ultimate", "ULT", UDim2.fromOffset(96, 96), UDim2.new(1, -178, 1, -124), Color3.fromHex("B565FF"))
	local leave = button(gui, "Leave", "LEAVE", UDim2.fromOffset(96, 40), UDim2.new(1, -178, 1, -232), Color3.fromHex("5A6378"))
	-- inventory button under the stats panel (anchor is bottom-right, so position = its bottom-right corner)
	local stands = button(gui, "Stands", "STANDS", UDim2.fromOffset(150, 48), UDim2.fromOffset(12 + 150, 172 + 48), Color3.fromHex("B565FF"))
	local skillCd = cooldownOverlay(skill)
	local ultCd = cooldownOverlay(ult)
	skill.Visible, ult.Visible, leave.Visible = false, false, false

	-- fight bar
	local fight = Instance.new("Frame")
	fight.Name = "Fight"
	fight.AnchorPoint = Vector2.new(0.5, 0)
	fight.Position = UDim2.new(0.5, 0, 0, 12)
	fight.Size = UDim2.fromOffset(360, 74)
	fight.BackgroundColor3 = Color3.fromHex("2B2752")
	fight.BackgroundTransparency = 0.15
	fight.Visible = false
	corner(fight, 14)
	stroke(fight, 3)
	fight.Parent = gui
	local fightTitle = text(fight, "Title", "", UDim2.new(1, -20, 0, 28), UDim2.fromOffset(10, 4))
	fightTitle.TextXAlignment = Enum.TextXAlignment.Center
	local hpBack = Instance.new("Frame")
	hpBack.Size = UDim2.new(1, -20, 0, 26)
	hpBack.Position = UDim2.fromOffset(10, 38)
	hpBack.BackgroundColor3 = Color3.fromHex("14122A")
	corner(hpBack, 8)
	hpBack.Parent = fight
	local hpFill = Instance.new("Frame")
	hpFill.Size = UDim2.fromScale(1, 1)
	hpFill.BackgroundColor3 = Color3.fromHex("5BD16B")
	corner(hpFill, 8)
	hpFill.Parent = hpBack
	local hpText = text(hpBack, "HP", "", UDim2.fromScale(1, 1), UDim2.fromScale(0, 0))
	hpText.TextXAlignment = Enum.TextXAlignment.Center
	hpText.ZIndex = 2

	-- toast
	local toastLabel = text(gui, "Toast", "", UDim2.fromOffset(520, 40), UDim2.new(0.5, -260, 0.22, 0))
	toastLabel.TextXAlignment = Enum.TextXAlignment.Center
	toastLabel.Visible = false
	local toastToken = 0

	gui.Parent = player:WaitForChild("PlayerGui")

	local api = {} :: HudApi
	api.gui, api.punch, api.auto, api.skill, api.ult, api.leave = gui, punch, auto, skill, ult, leave
	api.stands = stands

	function api.setStats(p: string, c: string, s: string, f: string, sn: string)
		power.Text = "Power " .. p
		coins.Text = "Coins " .. c
		stage.Text = "Best Stage " .. s
		frags.Text = f
		stand.Text = sn
	end

	function api.setAuto(on: boolean)
		auto.Text = if on then "AUTO: ON" else "AUTO: OFF"
		auto.BackgroundColor3 = if on then Color3.fromHex("3DBE6A") else Color3.fromHex("5A6378")
	end

	function api.setFight(st: { [string]: any }?)
		local inFight = st ~= nil
		fight.Visible = inFight
		skill.Visible, ult.Visible, leave.Visible = inFight, inFight, inFight
		punch.Text = if inFight then "HIT" else "PUNCH"
		if st then
			fightTitle.Text = string.format("%sStage %d  -  %d/%d left  -  %ds", if st.boss then "BOSS  " else "", st.stage, st.left, st.total, st.timeLeft)
			local frac = if st.maxHp > 0 then math.clamp(st.hp / st.maxHp, 0, 1) else 0
			hpFill.Size = UDim2.fromScale(frac, 1)
			hpFill.BackgroundColor3 = if frac > 0.5 then Color3.fromHex("5BD16B") elseif frac > 0.25 then Color3.fromHex("FFB52E") else Color3.fromHex("FF4F4F")
			hpText.Text = string.format("HP %d / %d", st.hp, st.maxHp)
		else
			skillCd.Size = UDim2.fromScale(1, 0)
			ultCd.Size = UDim2.fromScale(1, 0)
		end
	end

	function api.cooldown(kind: string, seconds: number)
		local o = if kind == "skill" then skillCd else ultCd
		o.Size = UDim2.fromScale(1, 1)
		TweenService:Create(o, TweenInfo.new(seconds, Enum.EasingStyle.Linear), { Size = UDim2.fromScale(1, 0) }):Play()
	end

	function api.toast(msg: string, color: Color3?)
		toastToken += 1
		local token = toastToken
		toastLabel.Text = msg
		toastLabel.TextColor3 = color or Color3.new(1, 1, 1)
		toastLabel.Visible = true
		task.delay(2.2, function()
			if toastToken == token then
				toastLabel.Visible = false
			end
		end)
	end

	function api.pulse(b: GuiObject)
		local sc = b:FindFirstChildOfClass("UIScale") or Instance.new("UIScale")
		sc.Parent = b
		sc.Scale = 0.9
		TweenService:Create(sc, TweenInfo.new(0.12, Enum.EasingStyle.Back, Enum.EasingDirection.Out), { Scale = 1 }):Play()
	end

	return api
end

return Hud
