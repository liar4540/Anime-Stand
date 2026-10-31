--!strict
-- Stand inventory: a card per owned stand (name, rarity, trait, Power/Speed/Durability, abilities) with an EQUIP
-- button. Reads the server-set OwnedStands / EquippedUid attributes; equipping is a server request.
-- In Studio a DEV row lets you give yourself any stand for testing (the server only accepts it in Studio).
local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local GameConfig = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("GameConfig"))

local StandsPanel = {}

local FONT = Enum.Font.FredokaOne
local INK = Color3.fromHex("1E1B33")
local PANEL = Color3.fromHex("2B2752")

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

local function label(parent: Instance, text: string, size: UDim2, pos: UDim2, color: Color3?, align: Enum.TextXAlignment?): TextLabel
	local t = Instance.new("TextLabel")
	t.BackgroundTransparency = 1
	t.Size = size
	t.Position = pos
	t.Font = FONT
	t.TextScaled = true
	t.Text = text
	t.TextColor3 = color or Color3.new(1, 1, 1)
	t.TextXAlignment = align or Enum.TextXAlignment.Left
	local s = Instance.new("UIStroke")
	s.Thickness = 1.5
	s.Color = INK
	s.Parent = t
	t.Parent = parent
	return t
end

local function textButton(parent: Instance, text: string, size: UDim2, pos: UDim2, color: Color3): TextButton
	local b = Instance.new("TextButton")
	b.Size = size
	b.Position = pos
	b.BackgroundColor3 = color
	b.Font = FONT
	b.TextScaled = true
	b.Text = text
	b.TextColor3 = Color3.new(1, 1, 1)
	corner(b, 10)
	stroke(b, 2)
	local pad = Instance.new("UIPadding")
	pad.PaddingTop = UDim.new(0.15, 0)
	pad.PaddingBottom = UDim.new(0.15, 0)
	pad.PaddingLeft = UDim.new(0.06, 0)
	pad.PaddingRight = UDim.new(0.06, 0)
	pad.Parent = b
	b.Parent = parent
	return b
end

export type Entry = { u: string, i: string, t: string, s: number }
export type Api = { open: () -> (), close: () -> (), toggle: () -> (), refresh: () -> () }

function StandsPanel.Create(gui: ScreenGui, onEquip: (uid: string) -> (), onDevGrant: (standId: string) -> ()): Api
	local player = Players.LocalPlayer

	local root = Instance.new("Frame")
	root.Name = "StandsPanel"
	root.AnchorPoint = Vector2.new(0.5, 0.5)
	root.Position = UDim2.fromScale(0.5, 0.5)
	root.Size = UDim2.new(0.9, 0, 0.8, 0)
	root.BackgroundColor3 = PANEL
	root.Visible = false
	root.ZIndex = 20
	corner(root, 16)
	stroke(root, 4)
	local maxSize = Instance.new("UISizeConstraint")
	maxSize.MaxSize = Vector2.new(720, 470)
	maxSize.Parent = root
	root.Parent = gui

	label(root, "MY STANDS", UDim2.new(1, -120, 0, 38), UDim2.fromOffset(16, 10), Color3.fromHex("FFD23F"))
	local close = textButton(root, "X", UDim2.fromOffset(44, 44), UDim2.new(1, -56, 0, 8), Color3.fromHex("FF5A5A"))

	local devOn = RunService:IsStudio()
	local devHeight = if devOn then 64 else 0
	local list = Instance.new("ScrollingFrame")
	list.Name = "List"
	list.BackgroundTransparency = 1
	list.BorderSizePixel = 0
	list.Position = UDim2.fromOffset(12, 58)
	list.Size = UDim2.new(1, -24, 1, -70 - devHeight)
	list.ScrollBarThickness = 8
	list.AutomaticCanvasSize = Enum.AutomaticSize.Y
	list.CanvasSize = UDim2.new()
	list.Parent = root
	local grid = Instance.new("UIGridLayout")
	grid.CellSize = UDim2.fromOffset(212, 150)
	grid.CellPadding = UDim2.fromOffset(10, 10)
	grid.SortOrder = Enum.SortOrder.LayoutOrder
	grid.HorizontalAlignment = Enum.HorizontalAlignment.Center
	grid.Parent = list

	if devOn then
		local dev = Instance.new("ScrollingFrame")
		dev.Name = "Dev"
		dev.BackgroundColor3 = Color3.fromHex("3B2F12")
		dev.BorderSizePixel = 0
		dev.Position = UDim2.new(0, 12, 1, -devHeight - 4)
		dev.Size = UDim2.new(1, -24, 0, devHeight - 4)
		dev.ScrollingDirection = Enum.ScrollingDirection.X
		dev.AutomaticCanvasSize = Enum.AutomaticSize.X
		dev.CanvasSize = UDim2.new()
		dev.ScrollBarThickness = 6
		corner(dev, 10)
		dev.Parent = root
		local row = Instance.new("UIListLayout")
		row.FillDirection = Enum.FillDirection.Horizontal
		row.Padding = UDim.new(0, 6)
		row.VerticalAlignment = Enum.VerticalAlignment.Center
		row.SortOrder = Enum.SortOrder.LayoutOrder
		row.Parent = dev
		local pad = Instance.new("UIPadding")
		pad.PaddingLeft = UDim.new(0, 6)
		pad.Parent = dev
		local tag = label(dev, "DEV (Studio)", UDim2.fromOffset(90, 30), UDim2.new(), Color3.fromHex("FFB36B"))
		tag.LayoutOrder = 0
		for id, def in GameConfig.Stands do
			local b = textButton(dev, "+ " .. def.name, UDim2.fromOffset(120, 44), UDim2.new(), GameConfig.RarityColors[def.rarity] or Color3.new(0.5, 0.5, 0.5))
			b.LayoutOrder = def.order
			b.Activated:Connect(function()
				onDevGrant(id)
			end)
		end
	end

	local api = {} :: Api

	function api.refresh()
		for _, c in list:GetChildren() do
			if c:IsA("Frame") then
				c:Destroy()
			end
		end
		local raw = player:GetAttribute("OwnedStands")
		local ok, entries = pcall(function()
			return HttpService:JSONDecode(if type(raw) == "string" then raw else "[]")
		end)
		if not ok or type(entries) ~= "table" then
			return
		end
		local equipped = player:GetAttribute("EquippedUid")
		local rarityIndex = {}
		for i, r in GameConfig.Rarities do
			rarityIndex[r] = i
		end
		for _, e in entries :: { Entry } do
			local def = GameConfig.Stands[e.i]
			if not def then
				continue
			end
			local isOn = e.u == equipped
			local rc = GameConfig.RarityColors[def.rarity] or Color3.new(1, 1, 1)
			local card = Instance.new("Frame")
			card.BackgroundColor3 = Color3.fromHex("1F1C3D")
			-- equipped first, then rarer first
			card.LayoutOrder = if isOn then -100 else -(rarityIndex[def.rarity] or 0) * 10 + def.order
			corner(card, 12)
			stroke(card, if isOn then 4 else 2, if isOn then Color3.fromHex("FFD23F") else rc)
			label(card, def.name, UDim2.new(1, -16, 0, 26), UDim2.fromOffset(8, 6), rc)
			label(card, def.rarity .. "  -  " .. e.t, UDim2.new(1, -16, 0, 18), UDim2.fromOffset(8, 32), Color3.fromHex("E3D7FF"))
			label(card, string.format("PWR %d   SPD %d   DUR %d", def.power, def.speed, def.durability), UDim2.new(1, -16, 0, 18), UDim2.fromOffset(8, 52), Color3.fromHex("9EE6FF"))
			label(card, def.skill.name .. " / " .. def.ultimate.name, UDim2.new(1, -16, 0, 16), UDim2.fromOffset(8, 72), Color3.fromHex("C7F0C2"))
			local b = textButton(card, if isOn then "EQUIPPED" else "EQUIP", UDim2.new(1, -16, 0, 44), UDim2.new(0, 8, 1, -52),
				if isOn then Color3.fromHex("5A6378") else Color3.fromHex("3DBE6A"))
			b.AutoButtonColor = not isOn
			if not isOn then
				b.Activated:Connect(function()
					onEquip(e.u)
				end)
			end
			card.Parent = list
		end
	end

	function api.open()
		api.refresh()
		root.Visible = true
	end
	function api.close()
		root.Visible = false
	end
	function api.toggle()
		if root.Visible then
			api.close()
		else
			api.open()
		end
	end

	close.Activated:Connect(api.close)
	player:GetAttributeChangedSignal("OwnedStands"):Connect(function()
		if root.Visible then
			api.refresh()
		end
	end)
	player:GetAttributeChangedSignal("EquippedUid"):Connect(function()
		if root.Visible then
			api.refresh()
		end
	end)
	return api
end

return StandsPanel
