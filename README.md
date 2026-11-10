# Thompson R6 Idle — Roblox

A seamless 5-second **R6 idle animation** of a character holding a **Thompson
submachine gun** with both hands, plus a textured, Roblox-native Thompson Tool
that the animation is built around.

| Front | Rear-left | Right side |
|---|---|---|
| `preview/front.mp4` | `preview/rear_left.mp4` | `preview/right_side.mp4` |

`preview/thompson_idle_3views.mp4` shows all three side by side (the loop plays twice).
`preview/reference_vs_render.png` puts the three reference screenshots above the matching render angles.

## What's in `roblox/`

| File | What it is |
|---|---|
| `ThompsonIdle_R6.rbxmx` | The animation: an editable `KeyframeSequence` (R6, `Loop = true`, `Priority = Action`, 5.0 s, 26 keyframes, Linear easing). |
| `Thompson.rbxmx` | A `Tool` containing the Thompson (58 welded parts), the `ThompsonIdleController` LocalScript, an `IdleAnimationId` StringValue and a copy of the KeyframeSequence. |
| `src/ThompsonIdleController.client.luau` | Source of the LocalScript embedded in the Tool. |

### Use it in Roblox Studio

1. **Insert the tool.** Right-click `StarterPack` → *Insert from File…* → `roblox/Thompson.rbxmx`.
   The game's avatar type must be **R6** (Game Settings → Avatar).
2. **Play-test right away.** In Studio, when `IdleAnimationId` is empty, the controller registers the bundled KeyframeSequence
   through `KeyframeSequenceProvider:RegisterKeyframeSequence`. That temporary ID only works inside Studio.
3. **Publish for live games.** Insert `roblox/ThompsonIdle_R6.rbxmx`, open it in the Animation Editor (below), then use
   *… → Publish to Roblox*. Paste the resulting ID into `Thompson.IdleAnimationId` (`1234567890` or `rbxassetid://1234567890`).

### Edit it in the Animation Editor

The Animation Clip Editor loads local saves from `ServerStorage.RBX_ANIMSAVES.<rig name>`. Put the inserted
`ThompsonIdle_R6` KeyframeSequence in that folder (create the folders if needed), select your R6 rig, and load it
from the editor's *…* menu. Every keyframe keys all six R6 joints, so any pose can be adjusted directly.

> The gun is welded to the **right arm** (the standard `RightGrip`). The left hand stays on the foregrip only
> while both arms keep the relationship the generator gives them. If you re-pose an arm by hand, change the
> parameters in `tools/thompson_idle/pose.py` and regenerate instead. That keeps the grip exact.

## Rig and weapon details

* **R6 only:** six parts and the six stock Motor6Ds (`RootJoint`, `Neck`, `Left/Right Shoulder`, `Left/Right Hip`)
  with Roblox's default C0/C1. Nothing is added: no elbows, knees, wrists or extra Motor6Ds. Arms and legs stay
  rigid blocks posed only through their existing joints. The Left Shoulder pose carries a constant 0.55-stud
  downward offset (the lowered shoulder in the references). The hip poses carry a small outward offset that sets
  the feet apart.
* **Weapon attachment:** a normal Tool. `Tool.Grip = CFrame.new(0, -0.69, 0.09, 1, 0, 0, 0, 0.9781476, 0.2079117, 0, -0.2079117, 0.9781476)`
  puts the pistol grip in the right hand. All other parts are `Weld`ed to `Handle` (the receiver), so the gun is
  one rigid body.
* **Thompson model:** built only from Parts, Cylinders and one WedgePart, using Roblox materials with no
  uploaded assets. It has a gunmetal `Metal` receiver with ejection port, cocking knob, selector and safety, a
  protected rear sight, a finned barrel, a Cutts compensator with ports, a front sight, a trigger and trigger
  guard, and a 30-round stick magazine. The buttstock, pistol grip and ridged vertical foregrip are walnut `Wood`.
  The stock length is fitted so the butt plate rests against the chest without entering it.
* **Pose** (taken from the three references, read as one 3D pose): the torso and legs are bladed about 70° right
  of the aim line. The head turns back to look down the barrel, which points along `HumanoidRootPart.LookVector`.
  The right hand sits on the pistol grip in front of the chest, with the right arm about 12° below horizontal.
  The left shoulder is lowered 0.55 studs, so the left arm starts well below the top of the torso and rises
  about 9° toward the gun. Its hand sits under the barrel, with its end face on the vertical foregrip, which
  shows half out of the hand as in the references. The gun is level, just below shoulder height (bore 0.11 studs
  under the top of the torso). The two hand contacts are 1.41 studs apart along the gun. The legs are strictly
  vertical with soles flat on the floor. Each is turned 10° toes-out and shifted 0.11 studs outward, so the legs
  stand apart and their corners poke slightly out from under the torso.

## The idle motion

All motion repeats exactly every 5.0 s, and the last keyframe equals the first.

| Element | Motion |
|---|---|
| Breathing | Torso pitch ±0.8°, pivoting on the hip line, with a slightly faster inhale than exhale. |
| Torso sway | Yaw ±0.55° about the hip centre. |
| Shoulders and gun | Both arms lift ±0.6°, lagging the breath by 0.18 s. They rotate about the line through both shoulder pivots, so arms and gun move as one rigid unit, neither hand slides, and each arm still turns only about its own shoulder. Muzzle travel is 0.09 studs. |
| Head | A small lagged nod (world pitch −0.34°…+0.30°). The head partly cancels the torso sway (world yaw ±0.19°), so the gaze stays on the barrel. Head travel is 0.05 studs. |
| Legs | Static in world space (spread stance above). The hip joints counter the torso sway, so feet never slide or lift. |
| Hair / accessories | Ride rigidly on the Head (no extra rig). |

## Regenerate, verify, render

Run from `tools/` (Python 3.11; `uv` shown):

```bash
uv run --no-project --python 3.11 --with numpy==1.26.4 python -m thompson_idle.build    # writes roblox/*.rbxmx
uv run --no-project --python 3.11 --with numpy==1.26.4 python -m thompson_idle.verify   # checks the exported files
uv run --no-project --python 3.11 --with bpy==5.0.1 --with pillow python render_preview.py   # frames -> build/render
./make_preview_videos.sh                                                                 # frames -> preview/*.mp4
```

`verify` reads the `.rbxmx` files back and replays them at 240 Hz with Roblox's interpolation and the `RightGrip`
weld formula. It checks:

* only the R6 joints are used, and the sequence loops with the last keyframe equal to the first;
* both hands stay locked to the gun (max error < 1e-6 studs);
* the feet stay planted (< 1e-5 studs) and the legs stay strictly vertical;
* arms turn only about their (fixed) shoulder pivots, and the head only about the neck;
* the stock never enters the torso or head;
* the motion stays subtle and has no velocity jump at the loop seam bigger than at any other keyframe.

The preview renders use the same replay. The character in them is a **stand-in** built on exact R6 part sizes
and dressed to resemble the reference avatar. In Roblox the animation drives your own avatar, so its face,
hair, clothing and accessories are unchanged.
