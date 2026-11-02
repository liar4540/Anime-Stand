# LihFolk R15 Animation Pipeline

Original keyframed animation for the Roblox R15 rig, authored in Blender 5.2. The clips were built in Blender from pose data and procedural foot trajectories written for this pack. No Mixamo, CMU or other downloaded motion data is used. The only external data is the R15 joint layout and part sizes. These were measured from Roblox's own default R15 rig (see §1).

```
Animations/
  _rig/       LihFolk_R15.blend, LihFolk_R15_reference.fbx (rest pose, skinned blocks), rig_spec.json
  Locomotion/ Idle, Walk (+Walk_axisZ.fbx test variant), Run, Jump
  Combat/     SwordCombo3, GroundSlam, DodgeRoll
  Reactions/  HitReact, Death
  Emotes/     DanceGroove
  <cat>/<Clip>.fbx | .rbxmx | .json | .mp4 | _sheet.png,  <cat>/_src/<Clip>.blend
tools/anim/ (<LihFolk Build>/tools\anim)
  build_rig.py   run.py   lihanim/{rig,clip,gait,measure,export,preview}.py   clips/*.py
```

Rebuild everything:
`"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python "<LihFolk Build>/tools\anim\run.py" -- walk run idle jump dance sword_combo ground_slam dodge_roll hit_react death`
Use `--no-render` for export only. Rebuild the rig with `build_rig.py`.

---

## 1. Rig spec

| Item | Value | Confidence / source |
|---|---|---|
| Hierarchy | HumanoidRootPart > LowerTorso > UpperTorso > Head / {L,R}UpperArm > LowerArm > Hand; LowerTorso > {L,R}UpperLeg > LowerLeg > Foot | High. Creator Docs character specifications and the Maya animation export guide |
| Motor6D names | Root, Waist, Neck, Left/RightShoulder, Elbow, Wrist, Hip, Knee, Ankle | High. Standard R15 |
| Joint positions and part sizes | `_rig/rig_spec.json` (studs, Roblox axes, origin on the ground under the HRP) | **High.** Measured read-only in Studio from `Players:CreateHumanoidModelFromDescription(HumanoidDescription.new(), R15)` (default block body, scale 1). RigAttachment positions were read from an in-memory model that was never parented into the place. |
| HipHeight | 2.1924 (HRP centre 3.1924 above ground, total height about 5.46) | High (measured) |
| C0/C1 rotations | Identity on all R15 RigAttachments, so Motor6D.Transform equals the pose in the parent's axes | High (measured) |
| Rest pose | I-pose (arms straight down), which is what the default rig uses | High |
| Blender convention | 1 BU = 1 stud, Z up, character faces −Y. Armature object `Root`, root bone `HumanoidRootPart`, bone heads at the Motor6D pivots, roll 0. Meshes are `<Part>_Geo` and each is weighted 1:1 to its bone. | Pipeline choice |

Sources:
- Creator Docs, character body specifications (hierarchy, `_Geo` naming, face +Z, I/A/T pose, no Root skin weights): https://create.roblox.com/docs/art/characters/specifications
- Export avatar animations from Maya (Root > HumanoidRootPart > … hierarchy, baked animation, Step 1, mute root translation, *Import > From FBX Animation*): https://create.roblox.com/docs/en-us/art/characters/export-avatar-animations-from-maya.md
- Avatar resources (official reference rigs and templates, e.g. *Rig_and_Attachments_Templates.zip*): https://create.roblox.com/docs/en-us/avatar/resources.md. These were **not** downloaded. The rig was measured from Studio's built-in default instead.
- Blender page (FBX Apply Scalings = FBX Unit Scale, Forward/Up axes, Unit System None): https://create.roblox.com/docs/en-us/art/blender.md
- Character body export (Add Leaf Bones off, Simplify 0, NLA/All Actions off): https://create.roblox.com/docs/en-us/avatar/character-bodies/export.md
- Animation Editor (30 fps, the 7 priorities, looping does not interpolate last→first, final keyframe named `End` when replacing defaults, *Publish to Roblox*): https://create.roblox.com/docs/animation/editor
- Animation events (`AnimationTrack:GetMarkerReachedSignal`, parameter string): https://create.roblox.com/docs/en-us/animation/events.md
- Emote import (*⋯ > Import > From File*, convert to CurveAnimation for emotes, publish, set AnimationId): https://create.roblox.com/docs/en-us/avatar/emotes/import.md
- Open Cloud assets (Animation accepts `.rbxm/.rbxmx` as `model/x-rbxm`, 20 MB cap): https://create.roblox.com/docs/en-us/cloud/guides/usage-assets
- DevForum, community reports that Blender FBX animation import onto R15 can come in offset or rotated (the reason the `.rbxmx` path exists): https://devforum.roblox.com/t/how-can-i-animate-skinned-mesh-r15-in-blender-and-import-into-studio/2962873

## 2. Deliverables per clip and export settings

**A. `<Clip>.rbxmx` is the primary, lowest-risk path.** It is a `KeyframeSequence` built from exact `Motor6D.Transform` CFrames sampled every frame from the evaluated rig. Frames are reduced jointly with Ramer-Douglas-Peucker at 0.2° and 0.003 studs, and every kept keyframe carries all 15 poses with Linear easing. The file also contains `Loop`, `Priority` and real `KeyframeMarker`s. Every export is checked by rebuilding part positions Roblox-style (`Part1 = Part0 * C0 * Transform * C1⁻¹`) and comparing them to Blender. The maximum error is 0.0 studs on all clips.

**B. `<Clip>.fbx`** is for the Animation Editor's *Import > From FBX Animation*. It contains the armature only, baked. Settings are in `lihanim/export.py` (`FBX_SETTINGS`):

| Setting | Value |
|---|---|
| Apply Scalings | FBX Unit Scale (`FBX_SCALE_UNITS`), global scale 1.0, Apply Unit on |
| Forward / Up | −Z / Y, so a character facing Blender −Y faces FBX **+Z**, as the avatar spec requires. `Walk_axisZ.fbx` is the same clip exported Forward = Z, for the axis test in §6. |
| Armature | Add Leaf Bones **off**, primary bone axis Y, secondary X, deform-only off, armature node type Null (the object exports as `Root`) |
| Animation | Bake on, Key All Bones on, NLA Strips off, All Actions off, Force Start/End keys on, Step 1, **Simplify 0** |
| Objects | Armature only. The reference rig FBX in `_rig/` also contains the skinned meshes. |
| Frame rate | 30 fps, frames 0…N. Loops repeat frame 0 at frame N (Roblox does not interpolate last→first). |
| Root motion | None. The HRP bone is never animated, and all travel is in place (see each JSON). |

**C. `<Clip>.json` sidecar** has the shape `{name, fps, frames, length_s, loop, priority, markers:[{name, frame, time, value?}], root_motion, …}`. It also includes QA numbers (`qa`), the file list, and per-clip extras: `native_ground_speed_studs_per_s` for walk and run, `suggested_displacement_studs` for the roll, `segments` for the jump, and `bpm` for the dance. FBX does not carry KeyframeMarkers, so if you import the FBX, add the markers from this JSON (snippet in §3).

**D. `<Clip>.mp4`** is a 480×480 Workbench preview. Loops play twice. On walk and run the grid scrolls at the native ground speed, so a planted foot should look glued to it. Jump and roll previews add preview-only HRP travel; this travel is never exported. `<Clip>_sheet.png` shows 8 key poses: the top row is a 3/4 view and the bottom row is an orthographic side view.

**E. Per-clip grip roll override (sword clips).** The shared sword grip rolls the handle +45° about its own axis (`rig.TOOL_GRIP_ROLL_Y`; in-game `Tool.Grip = CFrame.fromEulerAnglesYXZ(math.rad(30), math.rad(-45), 0)`). A clip module may declare `GRIP_ROLL = <deg>` at module level to author against a different roll. `run.py` calls `rig.set_grip_roll()` before every build: the clip's `GRIP_ROLL` when present, otherwise `rig.GRIP_ROLL_DEFAULT` (+45, or `LIH_GRIP_ROLL` when set). An explicit `LIH_GRIP_ROLL` env sweep still wins over a clip's value. `set_grip_roll` also refreshes the import-time copies of the handle frame (`clip.BLADE0/EDGE0`, `sword.HF`, `twist`/`twist_dp`), so clips built later in the same Blender session are not affected. Clips without `GRIP_ROLL` are byte-identical to before; this was checked by rebuilding SwordLight1, where the JSON was byte-identical and the rbxmx identical except for its random referent IDs. When a clip overrides the roll, `_sword.finish()` rewrites the JSON `grip` text and adds `tool_grip_roll_deg`. Game code must then set that `Tool.Grip` while the track plays and restore the shared grip afterwards; `qa.edge_lead.grip_roll_deg` records the value used. Sweep a clip with `LIH_GRIP_ROLL=<deg> LIH_TEST_OUT=1`. Preview-only option: `c.cam_follow = True` (default off) parents the preview cameras to the preview HRP travel, which keeps dash clips framed tight.

## 3. Importing into Roblox Studio (one time per clip)

Path A, rbxmx (recommended):
1. Open your place. In Explorer, right-click **ServerStorage**, choose **Insert from File…**, pick `<Clip>.rbxmx`, and a `KeyframeSequence` appears.
2. Optional check: open **Avatar › Animation Editor**, select an R15 rig (Avatar › Rig Builder › R15 Block), then **⋯ › Load** and pick the sequence. Play it.
3. Publish: right-click the KeyframeSequence and choose **Save to Roblox…**, or in the Animation Editor use **⋯ › Publish to Roblox**. Enter a title, choose the group as Creator for group games, and Submit. **You do this step yourself.** No asset IDs are created or invented by this pipeline.
4. Copy the new asset ID into an `Animation` object (`rbxassetid://<id>`) and play it with `Humanoid.Animator:LoadAnimation(anim)`.

Path B, FBX:
1. Rig Builder › R15 Block. Animation Editor, select the rig, name the clip, then **⋯ › Import › From FBX Animation** and pick `<Clip>.fbx`.
2. Set **⋯ › Set Animation Priority** and **Looping** from the JSON, and add markers with **Show Animation Events** at the JSON frames (time = frame/30). Publish as above.

Markers in code:
```lua
local track = animator:LoadAnimation(anim)
track:GetMarkerReachedSignal("Hit"):Connect(function(param) -- param = "1"/"2"/"3"
    -- server-validate the hit here
end)
```
If you need markers on an FBX import, run this in the command bar after the KeyframeSequence exists. It reads the JSON contents you paste in:
```lua
local data = game:GetService("HttpService"):JSONDecode([[ PASTE <Clip>.json HERE ]])
local seq = game.ServerStorage[data.name]
for _, m in data.markers do
    local best, bestDt = nil, math.huge
    for _, kf in seq:GetKeyframes() do
        local dt = math.abs(kf.Time - m.time); if dt < bestDt then best, bestDt = kf, dt end
    end
    local km = Instance.new("KeyframeMarker"); km.Name = m.name; km.Value = m.value or ""; best:AddMarker(km)
end
```

Open Cloud alternative: the Assets API lists Animation as uploadable from `.rbxm/.rbxmx` (`model/x-rbxm`, 20 MB max, one asset per call, API key with asset write scope). One community tool (Asphalt) says animation upload still needs a session cookie. Test one `.rbxmx` first before relying on it. Files "edited outside Studio may fail", so if the upload is rejected, re-save the sequence from Studio as `.rbxm` and upload that.

Gameplay notes:
- **Walk/Run** are in place. The animation looks right at its `native_ground_speed` (Walk 3.19, Run 10.0 studs/s). At other speeds call `track:AdjustSpeed(humanoid.WalkSpeed / native)`. At Roblox's default WalkSpeed of 16, the run should play about 1.6× faster, or use a longer stride variant.
- **Jump** is in place. Apply the physical jump on the `Takeoff` marker (frame 5). The air frames assume about 0.54 s of airtime (JumpHeight 7.2), `Apex` is frame 13 and `Land` is frame 21.
- **DodgeRoll** is in place. Move the HRP about 6 studs, eased, between `RollStart` (frame 5) and `RollEnd` (frame 22). `IFrameStart`/`IFrameEnd` are frames 7 and 19.
- **Death** holds its last pose, and the body lies about 1 stud ahead of the HRP. Keep the track at its end, or ragdoll after `BodyImpact`.
- To replace a default Animate-script animation, rename the final keyframe to `End` before publishing.

## 4. Quality checklist (applied to every clip)

- [ ] Clear key poses that read in silhouette from both the 3/4 and side views (contact sheet).
- [ ] Timing: anticipation is longer than the action, and the action takes 2–4 frames for hits. No linear interpolation except baked IK legs and the roll spin.
- [ ] Spacing: Bezier easing presets per key. `smooth` uses auto-clamped handles (ease in and out at extremes). `snap` arrives at full speed and stops dead (impacts). `launch` eases into an anticipation pose and leaves fast. `flat` is a long cushion or moving hold. `hold` is constant.
- [ ] Overlap: `Clip.offset()` delays the head, arms, forearms and hands by 1–8 frames behind the torso, wrapping on loops.
- [ ] Arcs: limbs are aimed with `aim()` (swing + twist) and interpolated as rotations, so hands travel on arcs. Steps use a lift arc.
- [ ] Weight: the pelvis shifts over the stance foot, and contacts sit lowest with a down-pose after impact.
- [ ] Feet: IK foot tracks are baked per frame. Planted pivots (heel, flat, toe) move with the ground, steps finish horizontally before touching down, and toe or heel rolls pin that edge. Measured with `measure.foot_lock` (below).
- [ ] Ground: `measure.lowest_point` checks every body-part box corner. `Clip.ground_solve()` sets the roll, slam hands and death body exactly on the floor.
- [ ] Loops: the first frame is repeated at frame N, with Cycles F-modifiers and cycle-aware auto handles.
- [ ] Export: FK check error is 0, markers come from the JSON, and priority and loop are set.

### Clip-scoped options (all default off; a clip opts in by setting them on its `Clip` in its own module)

- **`c.overlap_exempt = {"frames": (f0, f1), "bones": [...]}`** loosens the body-overlap gate for one clip. On frames f0..f1 (inclusive), any part pair that contains one of the listed bones is left out of `qa.body_overlap.body_max_studs`. These pairs are reported separately under `qa.body_overlap.exempt` (`max_studs`, `pair`, `frame`). All other frames and all other pairs keep the strict 0.05 gate. Use it only with the owner's approval and only where the R15 block geometry makes a real pose impossible. The 1-stud forearm cannot cross the 1-stud-deep chest without intersecting it.
  - **Only user:** TwistBackflip. Its arms are exempt between TwistStart and TwistEnd (f15-25) so the right forearm can wrap across the chest. It reports an exempt depth of 0.37 studs (UpperTorso|RightLowerArm). The rest of the clip stays at 0.027 or less.
- **`c.preview_only_objects = ["Name", ...]`**: `run.py` deletes these objects before it saves `_src/<Clip>.blend`. They still appear in the MP4 and sheet renders, but never in the shipped source file. TwistBackflip uses it for `PV_Shadow`, a floor disc under the centre of mass that acts as a height cue. Nothing preview-only is ever exported: the FBX contains the armature only, and the rbxmx is sampled from the bones.
- **`c.cam[view]["direction"]`**: an optional Blender-space vector from the target to the camera, for a perspective view with a clip-specific name. The default 3q angles are unchanged. TwistBackflip uses `views = ["3qSide", "side", "3q"]`, so its MP4 is a low side-on 3/4 that shows the twist.

## 5. Per-clip results

Foot slide is measured on every frame where a foot corner is within 0.03 studs of the floor. It is measured relative to the scrolling ground for walk and run, and relative to the game-driven displacement for the roll. "Shin clip" is how far the lower-leg block's rear corner goes below the floor in deep knee bends. This comes from the R15 block geometry: the shin box extends 0.05 studs below the ankle. It sits under the floor and inside the foot volume, so it is hidden in-game.

| Clip | Frames / pri / loop | Foot slide (studs) | Shin clip | Description |
|---|---|---|---|---|
| Idle | 91 / Idle / loop | 0.000 | 0.00 | Subtle breath, contrapposto, glance, layered overlap. |
| Walk | 33 / Movement / loop | **0.0001** | 0.02 | Heel-strike, flat and toe-off roll, down and up poses, pelvis yaw, roll and sway, chest counter-twist, arm swing with drag. This is the strongest clip. |
| Run | 19 / Movement / loop | **0.000** | 0.10 | Flight phase, compression, push-off and pumping arms. |
| Jump | 35 / Action / one-shot | 0.000 | 0.00 | Arms swing back then drive forward-up to lead the two-foot push-off, curled tuck at the apex, legs reach for the ground, deep bent-knee landing with absorb and a 13-frame recovery. Owner-approved. |
| SwordCombo3 | 73 / Action / one-shot | 0.000 | 0.28 | Three readable hits (forehand diagonal, backhand, stepping overhead) with blade direction solved per key, snap contacts on 8, 22 and 41, and combo windows. |
| GroundSlam | 67 / Action / one-shot | 0.004 | 0.43 | A long rise-on-toes anticipation, a 5-frame slam, the hands placed exactly on the floor at impact, squash and moving hold, heavy recovery. |
| DodgeRoll | 39 / Action / one-shot | 0.25 (root-relative, roll window) | 0.16 | A real ground-contact roll: the tuck centre follows the floor and is ground-solved every frame. It includes a dive, tuck and crouch landing, plus i-frame markers. |
| HitReact | 29 / Action2 / one-shot | 0.000 | 0.17 | A 2-frame snap, head whip on a 2-frame lag, arms flung forward, catch-step back, forward overshoot, recovery. |
| Death | 65 / Action4 / one-shot | 0.014 | 0.08 | Hit stiffen, buckle to the knees, sway, topple pivoting on the knees, bounce, head turned, late arm flop. |
| DanceGroove | 61 / Action / loop | 0.000 | 0.15 | Step-touch at 120 BPM: the down-bounce lands on the beat, punch, clap, punch, clap, with head bob 2 frames late and Beat markers. |

Run-wide facts: the FK check error is 0.00000 on all 10 clips. IK reach error is 0 except the slam (0.017, rise on toes) and death (0.08, prone). Walk and run foot slide is ≤ 0.0001 studs.

Size per clip as shipped (FBX + rbxmx + JSON + MP4 + sheet + source .blend) is **0.9–1.5 MB, about 1.2 MB on average**. The game-ready payload alone (FBX + rbxmx + JSON) is **0.29–0.76 MB, about 0.53 MB on average**. With previews included, 2.5 GB holds about 2,000 clips, or about 4,500 clips with the payload only. The rbxmx is the largest part of the payload; raising `reduce_frames` tolerance to 0.35° would roughly halve it.

## 6. Open questions for a one-time Studio import test

1. **FBX axis.** Import `Walk.fbx` (Forward −Z, faces +Z) and `Walk_axisZ.fbx` (Forward Z). Keep whichever walks forward with the correct facing, and update `FBX_SETTINGS["axis_forward"]` to match.
2. **FBX root naming.** The Maya guide names the root joint `HumanoidRootPart` (used here), while the avatar spec shows `HumanoidRootNode`. Check that the FBX import binds LowerTorso motion. If it does not, rename the root bone and re-export.
3. **FBX translation scale.** Check that the LowerTorso bob, for example walk −0.21 studs, comes in at stud scale, not ×100 or ×0.01, with FBX Unit Scale.
4. **Bone roll and rest orientation.** The FBX importer may compute rotations relative to bone orientation. If poses come in twisted, use the `.rbxmx` path, which needs no axis interpretation.
5. **`.rbxmx` acceptance.** Confirm that Insert from File accepts the generated KeyframeSequence (properties: Name, Loop, Priority token, Keyframe.Time, Pose.CFrame/EasingStyle/EasingDirection/Weight, KeyframeMarker.Name/Value). Also confirm whether the HRP placeholder pose with Weight 0 is fine.
6. **Open Cloud.** Confirm whether an API key alone can upload an Animation `.rbxmx`.
