"""Checks run against the exported .rbxmx files (not the generator's curves).

    python -m thompson_idle.verify          (run from tools/)

Exits non-zero if any hard requirement fails.
"""
from __future__ import annotations

import math
import sys
import xml.etree.ElementTree as ET

import numpy as np

from . import cf, gun, pose, rig
from .build import ROBLOX, SEQ_NAME, gun_world_from_arm
from .playback import Sequence, _cframe, _props

R6_POSES = {"HumanoidRootPart", "Torso", "Head", "Right Arm", "Left Arm", "Right Leg", "Left Leg"}


def _tool_grip(path) -> np.ndarray:
    root = ET.parse(path).getroot()
    tool = next(i for i in root.iter("Item") if i.get("class") == "Tool")
    return _cframe(_props(tool)["Grip"])


def _tool_parts(path) -> tuple[dict, list]:
    root = ET.parse(path).getroot()
    parts, welds = {}, []
    for item in root.iter("Item"):
        if item.get("class") in ("Part", "WedgePart"):
            parts[item.get("referent")] = _cframe(_props(item)["CFrame"])
        if item.get("class") == "Weld":
            p = _props(item)
            welds.append((p["Part0"].text, p["Part1"].text, _cframe(p["C0"]), _cframe(p["C1"])))
    return parts, welds


def _pose_names(path) -> tuple[set, int]:
    root = ET.parse(path).getroot()
    seq = next(i for i in root.iter("Item") if i.get("class") == "KeyframeSequence")
    names, count = set(), 0
    for kf in seq.findall("Item"):
        count += 1
        for p in kf.iter("Item"):
            if p.get("class") == "Pose":
                names.add(_props(p)["Name"].text)
    return names, count


def main() -> int:
    base = pose.build_base()
    seq_path = ROBLOX / f"{SEQ_NAME}.rbxmx"
    tool_path = ROBLOX / "Thompson.rbxmx"
    seq = Sequence.load(str(seq_path))
    grip = _tool_grip(tool_path)
    hp = np.array(base.params.hand_point)
    hrp = cf.translate(0, rig.HRP_HEIGHT, 0)
    results: list[tuple[str, bool, str]] = []

    def check(name, ok, detail):
        results.append((name, bool(ok), detail))

    names, nkf = _pose_names(seq_path)
    check("R6 joints only", names == R6_POSES, f"poses={sorted(names)}")
    check("looped sequence", seq.loop and abs(seq.length - base.params.period) < 1e-6,
          f"Loop={seq.loop} length={seq.length}s keyframes={nkf} priority={seq.priority}")
    first, last = seq.keyframes[0][1], seq.keyframes[-1][1]
    seam = max(np.abs(first[p][0] - last[p][0]).max() for p in rig.PARTS[1:])
    check("last keyframe == first keyframe", seam < 1e-6, f"max diff={seam:.2e}")

    # Tool welds reproduce the authored gun (rigid weapon).
    parts, welds = _tool_parts(tool_path)
    weld_err = max(np.abs(parts[p0] @ c0 @ cf.inv(c1) - parts[p1]).max() for p0, p1, c0, c1 in welds)
    check("gun parts rigidly welded to Handle", weld_err < 1e-5 and len(welds) == len(parts) - 1,
          f"{len(parts)} parts, {len(welds)} welds, max error={weld_err:.1e}")

    fps = 240
    n = int(round(seq.length * fps))
    left_err, right_err, foot_drift, min_foot = 0.0, 0.0, 0.0, 9.0
    shoulder_t, neck_t, hip_t = 0.0, 0.0, 0.0
    muzzle, head_pos, rot_dev = [], [], {p: [] for p in rig.PARTS[1:]}
    stock_clear = 9.0
    feet0 = None
    vels, tr_prev = [], None
    for i in range(n + 1):
        t = i / fps
        tr = seq.sample(t)
        w = rig.fk(tr, hrp)
        g = gun_world_from_arm(w["Right Arm"], grip, base.parts)
        right_err = max(right_err, float(np.linalg.norm(cf.point(w["Right Arm"], hp) - cf.point(g, (0, 0, 0)))))
        left_err = max(left_err, float(np.linalg.norm(cf.point(w["Left Arm"], hp) - cf.point(g, (0, 0, -base.d)))))
        feet = np.array([cf.point(w[leg], (sx * 0.5, -1, sz * 0.5)) for leg in ("Right Leg", "Left Leg")
                         for sx in (-1, 1) for sz in (-1, 1)])
        if feet0 is None:
            feet0 = feet
        foot_drift = max(foot_drift, float(np.abs(feet - feet0).max()))
        min_foot = min(min_foot, float(feet[:, 1].min()))
        shoulder_t = max(shoulder_t, *(float(np.linalg.norm(cf.pos(tr[a]))) for a in ("Right Arm", "Left Arm")))
        neck_t = max(neck_t, float(np.linalg.norm(cf.pos(tr["Head"]))))
        hip_t = max(hip_t, *(float(np.linalg.norm(cf.pos(tr[leg]))) for leg in ("Right Leg", "Left Leg")))
        muzzle.append(cf.point(g, (0, gun.BORE_Y, -(base.d + 0.95))))
        head_pos.append(cf.pos(w["Head"]))
        for p in rig.PARTS[1:]:
            rot_dev[p].append(cf.rot_angle_deg(cf.inv(base.world[p]) @ cf.inv(hrp) @ w[p]))
        if i % 24 == 0:
            stock_clear = min(stock_clear, pose.stock_room(cf.inv(hrp) @ g, cf.inv(hrp) @ w["Torso"],
                                                           cf.inv(hrp) @ w["Head"], clearance=0.0))
        if tr_prev is not None:  # joint angular velocity (deg/s) per sample
            vels.append([cf.rot_angle_deg(cf.inv(tr_prev[p]) @ tr[p]) * fps for p in rig.PARTS[1:]])
        tr_prev = tr

    # Snapping detector: velocity jumps between consecutive samples. The loop seam
    # (last sample -> first sample) must be no worse than an ordinary keyframe.
    vels = np.array(vels)
    jumps = np.abs(np.diff(vels, axis=0)).max(axis=1)
    seam_jump = float(np.abs(vels[0] - vels[-1]).max())

    check("right hand locked to pistol grip", right_err < 1e-4, f"max error={right_err:.2e} studs")
    check("left hand locked to foregrip", left_err < 1e-4, f"max error={left_err:.2e} studs")
    check("feet planted", foot_drift < 0.002 and abs(min_foot) < 1e-3,
          f"max foot drift={foot_drift:.2e} studs, sole height={min_foot:.4f}")
    check("arms rotate only about the shoulder joints", shoulder_t < 1e-6, f"max shoulder offset={shoulder_t:.1e}")
    check("head rotates only about the neck", neck_t < 1e-6, f"max neck offset={neck_t:.1e}")
    check("stock never enters torso/head", stock_clear >= base.params.extra["stock_back"],
          f"butt at z={base.params.extra['stock_back']:.3f}, first contact at z>={stock_clear:.3f}")
    muzzle = np.array(muzzle)
    head_pos = np.array(head_pos)
    span = lambda a: float(np.ptp(a, axis=0).max())  # noqa: E731
    check("subtle motion", span(muzzle) < 0.15 and span(head_pos) < 0.1,
          f"muzzle travel={span(muzzle):.3f} studs, head travel={span(head_pos):.3f} studs")
    check("smooth, no snapping (incl. loop seam)", jumps.max() < 0.5 and seam_jump <= jumps.max() + 1e-6,
          f"max velocity step={jumps.max():.3f} deg/s, at loop seam={seam_jump:.3f} deg/s, "
          f"peak joint speed={vels.max():.2f} deg/s")

    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    print("max deviation from rest pose, world space (deg): " + ", ".join(
        f"{p}={max(v):.2f}" for p, v in rot_dev.items()))
    print(f"hip offset (keeps feet planted during torso sway): {hip_t:.4f} studs")
    print(f"grip spacing d={base.d:.3f}, Tool.Grip position={np.round(cf.pos(grip), 4).tolist()}")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
