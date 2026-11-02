--!strict
-- Brick Fist pose library. Angles in degrees, joint-local (X = right, Y = up, -Z = forward).
-- Kept in sync with preview/index.html.

export type JointPose = { r: { number }, p: { number }? }
export type Pose = { [string]: JointPose }

local Poses = {}

-- per-joint follow stiffness: lower = more drag / overlap (wrists and legs trail the body)
Poses.Stiffness = {
    Root = 1, Waist = 1, Neck = 0.8,
    RightShoulder = 0.9, LeftShoulder = 0.9, RightElbow = 0.8, LeftElbow = 0.8,
    RightWrist = 0.65, LeftWrist = 0.65,
    RightHip = 0.6, LeftHip = 0.6, RightKnee = 0.5, LeftKnee = 0.5, RightAnkle = 0.45, LeftAnkle = 0.45,
}

Poses.BarragePeriod = 0.16 -- seconds per punch, per arm
Poses.HeavyWindup = 0.38
Poses.HeavyImpact = 0.46
Poses.HeavyEnd = 0.72
Poses.SummonHold = 0.3
-- M1 combo timing (hits 1-3 / finisher)
Poses.M1Hits = 4
Poses.M1Chamber = 0.05
Poses.M1Impact = 0.11
Poses.M1End = 0.28
Poses.M1FinisherChamber = 0.12
Poses.M1FinisherImpact = 0.18
Poses.M1FinisherEnd = 0.45

local function lerp(a: number, b: number, t: number): number
    return a + (b - a) * t
end
local function easeOutCubic(t: number): number
    return 1 - (1 - t) ^ 3
end
local function easeInOutSine(t: number): number
    return -(math.cos(math.pi * t) - 1) / 2
end
local function hash(n: number): number
    local s = math.sin(n * 127.1 + 311.7) * 43758.5453
    return s - math.floor(s)
end

-- fast snap out, slower recoil: punches feel heavy instead of sinusoidal
function Poses.PunchExtension(p: number): number
    if p < 0.32 then
        return easeOutCubic(p / 0.32)
    end
    return 1 - easeInOutSine((p - 0.32) / 0.68)
end

function Poses.Idle(t: number): Pose
    local b = math.sin(t * 1.8)
    return {
        Root = { p = { 0, 0.12 * b, 0 }, r = { -4 + 1.5 * math.sin(t * 1.8 + 0.6), 0, 0 } },
        Waist = { r = { 3 + 1.5 * b, -6, 0 } },
        Neck = { r = { -6 + 1.5 * math.sin(t * 1.8 - 0.8), 8, 0 } },
        RightShoulder = { r = { 18 + 3 * math.sin(t * 1.8 - 0.5), 0, 14 } },
        RightElbow = { r = { 75 + 3 * math.sin(t * 1.8 - 0.9), 0, 0 } },
        RightWrist = { r = { -10, 0, 0 } },
        LeftShoulder = { r = { 8 + 2 * math.sin(t * 1.8 - 0.5), 0, -12 } },
        LeftElbow = { r = { 28, 0, 0 } },
        LeftWrist = { r = { 0, 0, 0 } },
        RightHip = { r = { 22, 0, 5 } }, RightKnee = { r = { -38, 0, 0 } }, RightAnkle = { r = { -28, 0, 0 } },
        LeftHip = { r = { -4, 0, -5 } }, LeftKnee = { r = { -14, 0, 0 } }, LeftAnkle = { r = { -22, 0, 0 } },
    }
end

-- returns the pose plus each arm's extension (0..1) for VFX timing
function Poses.Barrage(t: number): (Pose, { [string]: number })
    local pose: Pose = {}
    local ext = {}
    for _, arm in { { side = "Right", sg = 1, off = 0 }, { side = "Left", sg = -1, off = 0.5 } } do
        local side, sg = arm.side, arm.sg
        local u = t / Poses.BarragePeriod + arm.off
        local n = math.floor(u)
        local e = Poses.PunchExtension(u - n)
        local h = hash(n * 2 + (if sg > 0 then 0 else 1)) -- per-punch variation, never robotic
        ext[side] = e
        pose[side .. "Shoulder"] = { r = { lerp(55, 90, e) + (h - 0.5) * 18, 10 * sg * e + (h - 0.5) * 8, lerp(10 * sg, 0, e) } }
        pose[side .. "Elbow"] = { r = { lerp(115, 4, e), 0, 0 } }
        pose[side .. "Wrist"] = { r = { lerp(-20, 0, e), -70 * sg * e, 0 } }
    end
    local twist = 9 * (ext.Right - ext.Left)
    pose.Root = { p = { 0, 0.05 * math.sin(t * 40), -0.6 }, r = { -14, 0, 0 } }
    pose.Waist = { r = { 6, twist, 0 } }
    pose.Neck = { r = { -10, -twist * 0.6, 0 } }
    pose.RightHip = { r = { -10, 0, 4 } }
    pose.RightKnee = { r = { -45, 0, 0 } }
    pose.RightAnkle = { r = { -35, 0, 0 } }
    pose.LeftHip = { r = { -6, 0, -4 } }
    pose.LeftKnee = { r = { -40, 0, 0 } }
    pose.LeftAnkle = { r = { -35, 0, 0 } }
    return pose, ext
end

Poses.HeavyWindupPose = {
    Root = { p = { 0, 0.15, 0.4 }, r = { 6, -25, 0 } }, Waist = { r = { -4, -30, 0 } }, Neck = { r = { -6, 35, 0 } },
    RightShoulder = { r = { -35, 0, 35 } }, RightElbow = { r = { 125, 0, 0 } }, RightWrist = { r = { -25, 0, 0 } },
    LeftShoulder = { r = { 75, -10, 0 } }, LeftElbow = { r = { 25, 0, 0 } }, LeftWrist = { r = { 0, 0, 0 } },
    RightHip = { r = { -25, 0, 5 } }, RightKnee = { r = { -60, 0, 0 } }, RightAnkle = { r = { -30, 0, 0 } },
    LeftHip = { r = { 40, 0, -5 } }, LeftKnee = { r = { -50, 0, 0 } }, LeftAnkle = { r = { -20, 0, 0 } },
} :: Pose

Poses.HeavyStrikePose = {
    Root = { p = { 0, 0, -1.8 }, r = { -20, 20, 0 } }, Waist = { r = { 8, 28, 0 } }, Neck = { r = { -12, -30, 0 } },
    RightShoulder = { r = { 92, 12, 0 } }, RightElbow = { r = { 0, 0, 0 } }, RightWrist = { r = { 0, -70, 0 } },
    LeftShoulder = { r = { -30, 0, -40 } }, LeftElbow = { r = { 100, 0, 0 } }, LeftWrist = { r = { -20, 0, 0 } },
    RightHip = { r = { -35, 0, 5 } }, RightKnee = { r = { -70, 0, 0 } }, RightAnkle = { r = { -40, 0, 0 } },
    LeftHip = { r = { 50, 0, -5 } }, LeftKnee = { r = { -30, 0, 0 } }, LeftAnkle = { r = { -25, 0, 0 } },
} :: Pose

Poses.SummonPose = {
    Root = { p = { 0, -2.5, 0 }, r = { 12, 0, 0 } }, Waist = { r = { 8, 0, 0 } }, Neck = { r = { 15, 0, 0 } },
    RightShoulder = { r = { 70, 40, 0 } }, RightElbow = { r = { 80, 0, 0 } }, RightWrist = { r = { 0, 0, 0 } },
    LeftShoulder = { r = { 70, -40, 0 } }, LeftElbow = { r = { 80, 0, 0 } }, LeftWrist = { r = { 0, 0, 0 } },
    RightHip = { r = { 10, 0, 0 } }, RightKnee = { r = { -20, 0, 0 } }, RightAnkle = { r = { -30, 0, 0 } },
    LeftHip = { r = { 10, 0, 0 } }, LeftKnee = { r = { -20, 0, 0 } }, LeftAnkle = { r = { -30, 0, 0 } },
} :: Pose

-- mirror a pose across the body's centre plane (swap sides, negate Y/Z rotation and X offset)
local function mirror(pose: Pose): Pose
    local out: Pose = {}
    for name, j in pose do
        local swapped = if name:sub(1, 5) == "Right" then "Left" .. name:sub(6)
            elseif name:sub(1, 4) == "Left" then "Right" .. name:sub(5)
            else name
        local p = j.p
        out[swapped] = { r = { j.r[1], -j.r[2], -j.r[3] }, p = if p then { -p[1], p[2], p[3] } else nil }
    end
    return out
end

local M1_LEGS = {
    RightHip = { r = { -20, 0, 5 } }, RightKnee = { r = { -50, 0, 0 } }, RightAnkle = { r = { -30, 0, 0 } },
    LeftHip = { r = { 25, 0, -5 } }, LeftKnee = { r = { -40, 0, 0 } }, LeftAnkle = { r = { -25, 0, 0 } },
}
local function withLegs(pose: Pose): Pose
    for name, j in M1_LEGS do
        pose[name] = j
    end
    return pose
end

-- right-handed source poses; left-handed ones are mirrored
local JabChamber = withLegs({
    Root = { p = { 0, 0.1, 0.2 }, r = { -6, -10, 0 } }, Waist = { r = { 2, -14, 0 } }, Neck = { r = { -8, 12, 0 } },
    RightShoulder = { r = { 35, 0, 20 } }, RightElbow = { r = { 120, 0, 0 } }, RightWrist = { r = { -20, 0, 0 } },
    LeftShoulder = { r = { 45, 0, -15 } }, LeftElbow = { r = { 105, 0, 0 } }, LeftWrist = { r = { -10, 0, 0 } },
})
local JabStrike = withLegs({
    Root = { p = { 0, 0, -0.9 }, r = { -12, 14, 0 } }, Waist = { r = { 4, 18, 0 } }, Neck = { r = { -8, -18, 0 } },
    RightShoulder = { r = { 90, 8, 0 } }, RightElbow = { r = { 2, 0, 0 } }, RightWrist = { r = { 0, -70, 0 } },
    LeftShoulder = { r = { 40, 0, -15 } }, LeftElbow = { r = { 110, 0, 0 } }, LeftWrist = { r = { -10, 0, 0 } },
})
local HookChamber = withLegs({
    Root = { p = { 0, 0.05, 0.3 }, r = { -4, -30, 0 } }, Waist = { r = { 2, -30, 0 } }, Neck = { r = { -8, 30, 0 } },
    RightShoulder = { r = { 40, -20, 60 } }, RightElbow = { r = { 95, 0, 0 } }, RightWrist = { r = { -10, 0, 0 } },
    LeftShoulder = { r = { 45, 0, -15 } }, LeftElbow = { r = { 105, 0, 0 } }, LeftWrist = { r = { -10, 0, 0 } },
})
local HookStrike = withLegs({
    Root = { p = { 0, 0, -1 }, r = { -10, 35, 0 } }, Waist = { r = { 4, 40, 0 } }, Neck = { r = { -8, -38, 0 } },
    RightShoulder = { r = { 85, 35, 30 } }, RightElbow = { r = { 70, 0, 0 } }, RightWrist = { r = { 0, -40, 0 } },
    LeftShoulder = { r = { 30, 0, -25 } }, LeftElbow = { r = { 115, 0, 0 } }, LeftWrist = { r = { -10, 0, 0 } },
})

-- 1 right jab, 2 left jab, 3 right hook, 4 left lunging straight (finisher)
Poses.M1Sides = { "Right", "Left", "Right", "Left" }
Poses.M1ChamberPoses = { JabChamber, mirror(JabChamber), HookChamber, mirror(Poses.HeavyWindupPose) }
Poses.M1StrikePoses = { JabStrike, mirror(JabStrike), HookStrike, mirror(Poses.HeavyStrikePose) }

local RAD = math.pi / 180
function Poses.ToCFrame(j: JointPose?): CFrame
    if not j then
        return CFrame.identity
    end
    local p = j.p or { 0, 0, 0 }
    return CFrame.new(p[1], p[2], p[3]) * CFrame.Angles(j.r[1] * RAD, j.r[2] * RAD, j.r[3] * RAD)
end

return Poses
