--!strict
-- Procedural Stand animator: drives Motor6D.Transform every frame, blending toward
-- the current pose with per-joint exponential springs (smooth, never snaps).
-- No uploaded AnimationIds required.

local Poses = require(script.Parent:WaitForChild("BrickFistPoses"))

export type Event = "HeavyImpact" | "PunchRight" | "PunchLeft" | "M1Impact"

local StandAnimator = {}
StandAnimator.__index = StandAnimator

export type StandAnimator = typeof(setmetatable({} :: {
    joints: { [string]: { motor: Motor6D, cf: CFrame } },
    state: string,
    stateT: number,
    t: number,
    impactFired: boolean,
    lastPunch: { [string]: number },
    comboIndex: number,
}, StandAnimator))

function StandAnimator.new(model: Model): StandAnimator
    local joints = {}
    for _, d in model:GetDescendants() do
        if d:IsA("Motor6D") then
            joints[d.Name] = { motor = d, cf = CFrame.identity }
        end
    end
    local self = setmetatable({
        joints = joints,
        state = "Idle",
        stateT = 0,
        t = 0,
        impactFired = false,
        lastPunch = { Right = -1, Left = -1 },
        comboIndex = 1,
    }, StandAnimator)
    return self
end

function StandAnimator.Play(self: StandAnimator, state: string)
    self.state = state
    self.stateT = 0
    self.impactFired = false
    self.lastPunch = { Right = -1, Left = 0 }
    if state == "Summon" then
        self:Snap(Poses.SummonPose)
    end
end

function StandAnimator.PlayM1(self: StandAnimator, index: number)
    self.comboIndex = math.clamp(index, 1, Poses.M1Hits)
    self:Play("M1")
end

function StandAnimator.Snap(self: StandAnimator, pose: Poses.Pose)
    for name, j in self.joints do
        j.cf = Poses.ToCFrame(pose[name])
        j.motor.Transform = j.cf
    end
end

-- returns the pose to blend toward, its stiffness, and any one-shot events this frame
function StandAnimator._target(self: StandAnimator, events: { Event }): (Poses.Pose, number)
    local s, st = self.state, self.stateT
    if s == "Summon" then
        if st < Poses.SummonHold then
            return Poses.SummonPose, 9
        end
        self.state = "Idle"
        return Poses.Idle(self.t), 9
    elseif s == "Barrage" then
        local pose = Poses.Barrage(st)
        for _, side in { "Right", "Left" } do
            -- a punch "lands" each time its arm passes full extension (phase 0.32)
            local off = if side == "Right" then 0 else 0.5
            local landed = math.floor(st / Poses.BarragePeriod + off - 0.32)
            if landed > self.lastPunch[side] then
                self.lastPunch[side] = landed
                table.insert(events, if side == "Right" then "PunchRight" else "PunchLeft")
            end
        end
        return pose, 40
    elseif s == "Heavy" then
        if st < Poses.HeavyWindup then
            return Poses.HeavyWindupPose, 14 -- slow anticipation
        elseif st < Poses.HeavyEnd then
            if not self.impactFired and st >= Poses.HeavyImpact then
                self.impactFired = true
                table.insert(events, "HeavyImpact")
            end
            return Poses.HeavyStrikePose, 60 -- explosive snap
        end
        self.state = "Idle"
        return Poses.Idle(self.t), 7 -- weighty recovery
    elseif s == "M1" then
        local i = self.comboIndex
        local finisher = i == Poses.M1Hits
        local chamber = if finisher then Poses.M1FinisherChamber else Poses.M1Chamber
        local impact = if finisher then Poses.M1FinisherImpact else Poses.M1Impact
        local finish = if finisher then Poses.M1FinisherEnd else Poses.M1End
        if st < chamber then
            return Poses.M1ChamberPoses[i], 30
        elseif st < finish then
            if not self.impactFired and st >= impact then
                self.impactFired = true
                table.insert(events, "M1Impact")
            end
            return Poses.M1StrikePoses[i], 55
        end
        self.state = "Idle"
        return Poses.Idle(self.t), 10
    end
    return Poses.Idle(self.t), 10
end

function StandAnimator.Step(self: StandAnimator, dt: number): { Event }
    self.t += dt
    self.stateT += dt
    local events = {}
    local pose, k = self:_target(events)
    for name, j in self.joints do
        local a = 1 - math.exp(-k * (Poses.Stiffness[name] or 1) * dt)
        j.cf = j.cf:Lerp(Poses.ToCFrame(pose[name]), a)
        j.motor.Transform = j.cf
    end
    return events
end

-- 0..1 charge used by VFX to brighten the fist during the heavy wind-up
function StandAnimator.Charge(self: StandAnimator): number
    if self.state == "Heavy" and self.stateT < Poses.HeavyImpact then
        return math.clamp(self.stateT / Poses.HeavyWindup, 0, 1)
    end
    return 0
end

return StandAnimator
