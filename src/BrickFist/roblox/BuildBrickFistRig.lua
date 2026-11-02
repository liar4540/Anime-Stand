--[[
    Brick Fist — rig builder. Run ONCE in the Studio Command Bar (View > Command Bar)
    after importing out/BrickFist.obj with the 3D Importer.

    1. Select the imported BrickFist model in the Explorer (or leave it in Workspace named "BrickFist").
    2. Paste this whole file into the Command Bar and press Enter.
    3. Result: ReplicatedStorage.Stands.BrickFist — a jointed, coloured, ready-to-animate rig.
]]

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Selection = game:GetService("Selection")

local MATERIALS = {
    Clay = { Color3.fromRGB(181, 120, 79), Enum.Material.SmoothPlastic },
    ClayLight = { Color3.fromRGB(210, 152, 108), Enum.Material.SmoothPlastic },
    Trim = { Color3.fromRGB(120, 72, 44), Enum.Material.SmoothPlastic },
    Core = { Color3.fromRGB(62, 38, 26), Enum.Material.SmoothPlastic },
    Glow = { Color3.fromRGB(255, 194, 71), Enum.Material.Neon },
}

-- joint = { parent segment, child segment }  (must match tools/build_brickfist.py)
local JOINTS = {
    { "Root", "HumanoidRootPart", "LowerTorso" },
    { "Waist", "LowerTorso", "UpperTorso" },
    { "Neck", "UpperTorso", "Head" },
    { "RightShoulder", "UpperTorso", "RightUpperArm" },
    { "RightElbow", "RightUpperArm", "RightLowerArm" },
    { "RightWrist", "RightLowerArm", "RightHand" },
    { "LeftShoulder", "UpperTorso", "LeftUpperArm" },
    { "LeftElbow", "LeftUpperArm", "LeftLowerArm" },
    { "LeftWrist", "LeftLowerArm", "LeftHand" },
    { "RightHip", "LowerTorso", "RightUpperLeg" },
    { "RightKnee", "RightUpperLeg", "RightLowerLeg" },
    { "RightAnkle", "RightLowerLeg", "RightFoot" },
    { "LeftHip", "LowerTorso", "LeftUpperLeg" },
    { "LeftKnee", "LeftUpperLeg", "LeftLowerLeg" },
    { "LeftAnkle", "LeftLowerLeg", "LeftFoot" },
}

local source = Selection:Get()[1] or workspace:FindFirstChild("BrickFist")
assert(source, "Select the imported BrickFist model first")

local meshes, pivots = {}, {}
for _, d in source:GetDescendants() do
    if d:IsA("MeshPart") then
        local pivotName = d.Name:match("^Pivot_(.+)$")
        if pivotName then
            pivots[pivotName] = d.Position
        elseif d.Name:find("__") then
            table.insert(meshes, d)
        end
    end
end
assert(pivots.Root and pivots.Forward, "Pivot markers missing — was 'Merge Meshes' left on during import?")

-- orientation frame from the markers, so import offset / rotation never matters
local fwd = pivots.Forward - pivots.Root
local frame = CFrame.lookAt(Vector3.zero, Vector3.new(fwd.X, 0, fwd.Z))

local rig = Instance.new("Model")
rig.Name = "BrickFist"

local function makeRoot(name, cf, size)
    local p = Instance.new("Part")
    p.Name = name
    p.Size = size or Vector3.new(0.2, 0.2, 0.2)
    p.CFrame = cf
    p.Transparency = 1
    p.CanCollide, p.CanTouch, p.CanQuery = false, false, false
    p.Massless = true
    p.Parent = rig
    return p
end

local hrp = makeRoot("HumanoidRootPart", frame + pivots.Root, Vector3.new(2, 2, 1))
hrp.Anchored = true
hrp.Massless = false
rig.PrimaryPart = hrp

local segments = { HumanoidRootPart = hrp }
for _, j in JOINTS do
    local name, parentName, childName = j[1], j[2], j[3]
    assert(pivots[name], "Missing pivot " .. name)
    local child = makeRoot(childName, frame + pivots[name])
    segments[childName] = child
    local parent = segments[parentName]
    local motor = Instance.new("Motor6D")
    motor.Name = name
    motor.Part0 = parent
    motor.Part1 = child
    motor.C0 = parent.CFrame:ToObjectSpace(child.CFrame)
    motor.C1 = CFrame.identity
    motor.Parent = child
end

for _, mesh in meshes do
    local segName, matName = mesh.Name:match("^(.-)__(.+)$")
    local seg = segments[segName]
    local mat = MATERIALS[matName]
    if seg and mat then
        mesh.Anchored = false
        mesh.CanCollide, mesh.CanTouch, mesh.CanQuery = false, false, false
        mesh.Massless = true
        mesh.Color, mesh.Material = mat[1], mat[2]
        mesh.CastShadow = matName ~= "Glow"
        mesh:SetAttribute("StandMaterial", matName)
        mesh.Parent = rig
        local weld = Instance.new("WeldConstraint")
        weld.Part0 = seg
        weld.Part1 = mesh
        weld.Parent = mesh
    end
end

-- VFX anchor points
local function attach(parent, name, worldPos)
    local a = Instance.new("Attachment")
    a.Name = name
    a.WorldPosition = worldPos
    a.Parent = parent
    return a
end
for _, side in { "Right", "Left" } do
    local hand = segments[side .. "Hand"]
    local fist = rig:FindFirstChild(side .. "Hand__Clay")
    local center = fist and fist.Position or hand.Position
    local across = frame.RightVector * 0.38
    attach(hand, "FistCenter", center)
    attach(hand, "TrailTop", center + across)
    attach(hand, "TrailBottom", center - across)
end
local eyes = rig:FindFirstChild("Head__Glow")
attach(segments.Head, "Eyes", eyes and eyes.Position or segments.Head.Position)
attach(hrp, "Aura", hrp.Position)

local folder = ReplicatedStorage:FindFirstChild("Stands") or Instance.new("Folder")
folder.Name = "Stands"
folder.Parent = ReplicatedStorage
local old = folder:FindFirstChild("BrickFist")
if old then
    old:Destroy()
end
rig.Parent = folder
source:Destroy()
print(("[BrickFist] Rig built: %d mesh parts, %d joints -> ReplicatedStorage.Stands.BrickFist"):format(#meshes, #JOINTS))
