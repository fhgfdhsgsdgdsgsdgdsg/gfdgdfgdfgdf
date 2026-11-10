"""Generate every deliverable from the pose definition in pose.py.

    python -m thompson_idle.build            (run from tools/)

Writes:
  roblox/ThompsonIdle_R6.rbxmx   KeyframeSequence (editable in the Animation Editor)
  roblox/Thompson.rbxmx          Tool: textured Thompson + controller + bundled sequence
  build/preview_frames.json      Roblox-style playback samples for the preview renderer
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from . import cf, gun, pose, rbxmx, rig
from .playback import Sequence

ROOT = Path(__file__).resolve().parents[2]
ROBLOX = ROOT / "roblox"
BUILD = ROOT / "build"
SEQ_NAME = "ThompsonIdle_R6"
PREVIEW_FPS = 30


def keyframe_sequence(base: pose.BasePose) -> rbxmx.Node:
    p = base.params
    seq = rbxmx.Node("KeyframeSequence", SEQ_NAME)
    seq.bool("Loop", True).token("Priority", 2)  # Enum.AnimationPriority.Action
    times = pose.keyframe_times(p)
    frames = [pose.transforms_from_world(pose.world_at(base, t)) for t in times[:-1]]
    frames.append(frames[0])  # last keyframe == first: exact loop closure
    children = {"HumanoidRootPart": ["Torso"], "Torso": ["Head", "Right Arm", "Left Arm", "Right Leg", "Left Leg"]}
    for t, tr in zip(times, frames):
        kf = seq.add(rbxmx.Node("Keyframe", "Keyframe"))
        kf.float("Time", t)

        def pose_node(part: str) -> rbxmx.Node:
            n = rbxmx.Node("Pose", part)
            n.cframe("CFrame", tr.get(part, np.eye(4)))
            n.token("EasingDirection", 0).token("EasingStyle", 0)  # In, Linear
            n.float("Weight", 1)
            for c in children.get(part, []):
                n.add(pose_node(c))
            return n

        kf.add(pose_node("HumanoidRootPart"))
    return seq


def tool_model(base: pose.BasePose, seq: rbxmx.Node, controller_src: str) -> rbxmx.Node:
    tool = rbxmx.Node("Tool", "Thompson")
    tool.cframe("Grip", base.grip)
    tool.bool("CanBeDropped", False).bool("RequiresHandle", True).bool("ManualActivationOnly", False)
    tool.string("ToolTip", "Thompson submachine gun")
    # Display placement when the tool sits in Workspace: gun frame at y=3.
    place = cf.translate(0, 3, 0)
    handle_local = gun.handle_local(base.parts)
    handle_world = place @ handle_local
    nodes = {}
    for part in base.parts:
        n = rbxmx.Node(part.class_name, part.name)
        if part.class_name == "Part":
            n.token("shape", rbxmx.PART_SHAPES[part.shape])
        n.bool("Anchored", False).bool("CanCollide", False).bool("CanTouch", False).bool("CanQuery", False)
        n.bool("Massless", True).bool("CastShadow", True).bool("Locked", False)
        n.cframe("CFrame", place @ part.cframe)
        n.vector3("size", part.size)
        n.color3uint8("Color3uint8", part.color)
        n.token("Material", rbxmx.MATERIALS[part.material])
        n.float("Reflectance", 0).float("Transparency", 0)
        for s in ("Top", "Bottom", "Front", "Back", "Left", "Right"):
            n.token(f"{s}Surface", 0)
        nodes[part.name] = n
        tool.add(n)
    handle = nodes["Handle"]
    for part in base.parts:
        if part.name == "Handle":
            continue
        w = rbxmx.Node("Weld", "HandleWeld")
        w.cframe("C0", cf.inv(handle_world) @ place @ part.cframe).cframe("C1", np.eye(4))
        w.ref_prop("Part0", handle).ref_prop("Part1", nodes[part.name])
        nodes[part.name].add(w)
    anim_id = rbxmx.Node("StringValue", "IdleAnimationId")
    anim_id.string("Value", "")
    tool.add(anim_id)
    script = rbxmx.Node("LocalScript", "ThompsonIdleController")
    script.bool("Disabled", False).source(controller_src)
    tool.add(script)
    tool.add(seq)
    return tool


def gun_world_from_arm(right_arm: np.ndarray, grip: np.ndarray, parts) -> np.ndarray:
    """Gun-local frame in world, via the engine's RightGrip weld (C0 legacy, C1 = Tool.Grip)."""
    handle = right_arm @ rig.RIGHT_GRIP_C0 @ cf.inv(grip)
    return handle @ cf.inv(gun.handle_local(parts))


def preview_frames(base: pose.BasePose, seq: Sequence) -> dict:
    hrp = cf.translate(0, rig.HRP_HEIGHT, 0)
    n = int(round(seq.length * PREVIEW_FPS))
    frames = []
    for i in range(n):
        world = rig.fk(seq.sample(i / PREVIEW_FPS), hrp)
        world["Gun"] = gun_world_from_arm(world["Right Arm"], base.grip, base.parts)
        frames.append({k: v.tolist() for k, v in world.items()})
    return {
        "fps": PREVIEW_FPS,
        "body_yaw": base.params.body_yaw,
        "frames": frames,
        "gun_parts": [{"name": p.name, "shape": p.shape, "size": p.size, "cframe": p.cframe.tolist(),
                       "color": p.color, "material": p.material} for p in base.parts],
    }


def main() -> None:
    base = pose.build_base()
    ROBLOX.mkdir(exist_ok=True)
    BUILD.mkdir(exist_ok=True)
    controller = (ROBLOX / "src" / "ThompsonIdleController.client.luau").read_text()

    seq_node = keyframe_sequence(base)
    seq_path = ROBLOX / f"{SEQ_NAME}.rbxmx"
    seq_path.write_text(rbxmx.document(seq_node))
    (ROBLOX / "Thompson.rbxmx").write_text(rbxmx.document(tool_model(base, keyframe_sequence(base), controller)))

    seq = Sequence.load(str(seq_path))
    (BUILD / "preview_frames.json").write_text(json.dumps(preview_frames(base, seq)))

    e = base.params.extra
    print(f"grip spacing d={base.d:.3f}  right hold={np.round(e['p_r'], 3)}  "
          f"left arm yaw/pitch={[round(math.degrees(a), 1) for a in e['left_arm']]}")
    print(f"keyframes={len(seq.keyframes)} length={seq.length}s parts={len(base.parts)}")


if __name__ == "__main__":
    main()
