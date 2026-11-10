"""Reference pose + subtle idle motion for the R6 Thompson hold.

Strategy (keeps both hands locked without any extra joints):
* The gun is welded to the Right Arm (Tool RightGrip), so the right hand is
  locked by construction.
* Both arms are only ever moved together, either rigidly with the Torso or by
  one shared rotation about the line through both shoulder pivots. A rotation
  about that line is a rigid motion of {left arm, right arm, gun}, so the
  left-hand / foregrip contact is preserved exactly.
* Torso breathing pitch pivots on the line through both hip joints, and the
  hips counter-rotate, so the rigid R6 legs stay planted.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import cf, gun, rig

D = math.radians


@dataclass
class Params:
    # Static reference pose
    body_yaw: float = D(70)  # torso + legs turned right of the aim line (bladed stance)
    torso_lean: float = D(2.0)  # forward lean, pivoting on the hip line
    head_pitch: float = D(-3.0)  # negative looks down
    head_yaw: float = D(0.0)  # relative to the aim line
    right_arm: tuple[float, float, float] = (D(0), D(78), D(0))  # yaw, pitch, roll (aim space)
    left_arm_roll: float = D(0)
    hand_point: tuple[float, float, float] = (0.0, -1.0, 0.0)  # right hand on the pistol grip (arm space)
    # Left hand: end face on the foregrip, as with the right hand. The left shoulder is lowered
    # on its own Motor6D (references show the left arm well below the top of the torso).
    left_hand_point: tuple[float, float, float] = (0.0, -1.0, 0.0)
    left_grip_drop: float = 0.0  # left contact height below the pistol-grip hold point (studs)
    left_shoulder_drop: float = 0.55  # studs, in torso space
    # Legs stay strictly vertical: only turned toes-out and set slightly apart.
    leg_toe_out: float = D(10.0)  # each leg yawed outward about its own vertical axis
    leg_spread: float = 0.22  # each leg shifted outward (studs): feet apart, a small gap between the legs
    # Idle motion
    period: float = 5.0
    key_step: float = 0.2
    torso_pitch_amp: float = D(0.8)
    torso_yaw_amp: float = D(0.55)
    shoulder_lift_amp: float = D(0.6)
    head_pitch_amp: float = D(0.6)
    head_yaw_amp: float = D(0.35)
    extra: dict = field(default_factory=dict)


@dataclass
class BasePose:
    params: Params
    world: dict[str, np.ndarray]  # part -> CFrame (HRP space)
    gun: np.ndarray  # gun-local frame -> HRP space
    d: float
    parts: list[gun.GunPart]
    grip: np.ndarray  # Tool.Grip


def _arm_world(side: str, yaw: float, pitch: float, roll: float, torso: np.ndarray, drop: float = 0.0) -> np.ndarray:
    part = f"{side} Arm"
    r = cf.ry(yaw) @ cf.rx(pitch) @ cf.ry(roll)
    piv_w = _shoulder_pivot(part, torso, drop)
    p = piv_w - r[:3, :3] @ rig.pivot_local(part)
    return cf.from_rot(r[:3, :3], p)


def _shoulder_pivot(part: str, torso: np.ndarray, drop: float = 0.0) -> np.ndarray:
    return rig.pivot_world(part, torso) - torso[:3, :3] @ np.array([0.0, drop, 0.0])


def _solve_left(params: Params, torso: np.ndarray, target: np.ndarray) -> tuple[float, float]:
    """Yaw/pitch of the left arm so its foregrip contact matches target in x and y (z sets grip spacing)."""
    hp = np.array(params.left_hand_point)

    def f(v):
        arm = _arm_world("Left", v[0], v[1], params.left_arm_roll, torso, params.left_shoulder_drop)
        h = cf.point(arm, hp)
        return np.array([h[0] - target[0], h[1] - target[1]])

    v = np.array([D(-60), D(70)])
    for _ in range(50):
        fv = f(v)
        if np.linalg.norm(fv) < 1e-12:
            break
        j = np.zeros((2, 2))
        for k in range(2):
            dv = np.zeros(2)
            dv[k] = 1e-7
            j[:, k] = (f(v + dv) - fv) / 1e-7
        v = v - np.linalg.solve(j, fv)
    assert np.linalg.norm(f(v)) < 1e-9, "left arm IK failed"
    return float(v[0]), float(v[1])


def torso_world(params: Params, pitch: float = 0.0, yaw: float = 0.0) -> np.ndarray:
    """Torso CFrame (HRP space). Lean/pitch pivot on the hip line; yaw about the hip midpoint."""
    hip_mid = np.array([0.0, -1.0, 0.0])
    local = cf.about_point(cf.ry(yaw) @ cf.rx(-params.torso_lean + pitch), hip_mid)
    return cf.ry(-params.body_yaw) @ local


def legs_world(params: Params) -> dict[str, np.ndarray]:
    """Static, strictly vertical legs: each turned toes-out about its own vertical axis and
    shifted outward, so the corners poke slightly out from under the torso. Soles stay flat on
    the floor, 3 studs below the HumanoidRootPart."""
    base = cf.ry(-params.body_yaw)
    out = {}
    for side, sx in (("Right", 1.0), ("Left", -1.0)):
        rest = cf.translate(sx * (0.5 + params.leg_spread), -2.0, 0.0)
        out[f"{side} Leg"] = base @ rest @ cf.ry(-sx * params.leg_toe_out)
    return out


def head_world(params: Params, torso: np.ndarray, pitch: float = 0.0, yaw: float = 0.0) -> np.ndarray:
    r = cf.ry(params.head_yaw + yaw) @ cf.rx(params.head_pitch + pitch)
    piv = rig.pivot_world("Head", torso)
    return cf.from_rot(r[:3, :3], piv - r[:3, :3] @ rig.pivot_local("Head"))


def build_base(params: Params | None = None) -> BasePose:
    params = params or Params()
    torso = torso_world(params)
    hp = np.array(params.hand_point)
    ry_, rp_, rr_ = params.right_arm
    rarm = _arm_world("Right", ry_, rp_, rr_, torso)
    p_r = cf.point(rarm, hp)
    target_l = p_r - np.array([0.0, params.left_grip_drop, 0.0])
    ly, lp = _solve_left(params, torso, target_l)
    larm = _arm_world("Left", ly, lp, params.left_arm_roll, torso, params.left_shoulder_drop)
    p_l = cf.point(larm, np.array(params.left_hand_point))
    d = float(p_r[2] - p_l[2])
    gun_cf = cf.translate(*p_r)  # gun axes == aim axes: barrel along -Z, level
    head = head_world(params, torso)
    stock_back = stock_room(gun_cf, torso, head)
    parts = gun.build(d, stock_back, params.left_grip_drop)
    handle = gun_cf @ gun.handle_local(parts)
    grip = cf.inv(handle) @ rarm @ rig.RIGHT_GRIP_C0
    world = {"HumanoidRootPart": np.eye(4), "Torso": torso, "Head": head,
             "Right Arm": rarm, "Left Arm": larm, **legs_world(params)}
    params.extra.update(left_arm=(ly, lp), p_r=p_r, p_l=p_l, stock_back=stock_back)
    return BasePose(params, world, gun_cf, d, parts, grip)


def _inside_box(m: np.ndarray, size, pts: np.ndarray) -> bool:
    inv = cf.inv(m)
    local = (inv[:3, :3] @ pts.T).T + inv[:3, 3]
    return bool(np.any(np.all(np.abs(local) < np.asarray(size) / 2, axis=1)))


def _inside_head(m: np.ndarray, pts: np.ndarray) -> bool:
    inv = cf.inv(m)
    local = (inv[:3, :3] @ pts.T).T + inv[:3, 3]
    return bool(np.any((np.hypot(local[:, 0], local[:, 2]) < 0.62) & (np.abs(local[:, 1]) < 0.62)))


def stock_room(gun_cf: np.ndarray, torso: np.ndarray, head: np.ndarray, clearance: float = 0.06) -> float:
    """Gun-local z where the stock's cross-section would first touch the torso (incl. clothing) or head."""
    xs = np.linspace(-0.12, 0.12, 4)
    ys = np.linspace(0.28, 0.84, 8)
    for z in np.arange(0.40, 1.40, 0.005):
        pts = np.array([cf.point(gun_cf, (x, y, z)) for x in xs for y in ys])
        if _inside_box(torso, (2.1, 2.1, 1.1), pts) or _inside_head(head, pts):
            return float(z - clearance)
    return 1.40


def _c(x: float) -> float:
    return 2.0 * x - 1.0


def channels(params: Params, t: float) -> dict[str, float]:
    """Periodic idle channels (radians). All are exactly periodic in params.period."""
    w = 2 * math.pi / params.period

    def breath(tt: float) -> float:
        u = w * tt + 0.22 * math.sin(w * tt)  # slightly quicker inhale than exhale
        return 0.5 - 0.5 * math.cos(u)

    return {
        "torso_pitch": params.torso_pitch_amp * _c(breath(t)),
        "torso_yaw": params.torso_yaw_amp * math.sin(w * t + 0.9),
        "shoulder_lift": params.shoulder_lift_amp * _c(breath(t - 0.18)),
        "head_pitch": params.head_pitch_amp * _c(breath(t - 0.4)) - 0.5 * params.torso_pitch_amp * _c(breath(t)),
        "head_yaw": params.head_yaw_amp * math.sin(w * (t - 0.45) + 0.9)
        - 0.6 * params.torso_yaw_amp * math.sin(w * t + 0.9),
    }


def world_at(base: BasePose, t: float) -> dict[str, np.ndarray]:
    """Target world CFrames (HRP space) of all parts at time t."""
    p = base.params
    ch = channels(p, t)
    torso0 = base.world["Torso"]
    torso = torso_world(p, pitch=ch["torso_pitch"], yaw=ch["torso_yaw"])
    # Shared rotation about the line through both shoulder pivots (left one lowered): moves
    # arms + gun as one rigid body while each arm still turns only about its own shoulder.
    right_piv = np.array([1.0, 0.5, 0.0])
    left_piv = np.array([-1.0, 0.5 - p.left_shoulder_drop, 0.0])
    lift = cf.about_point(cf.axis_angle(right_piv - left_piv, ch["shoulder_lift"]), right_piv)
    upper = torso @ lift @ cf.inv(torso0)
    out = dict(base.world)
    out["Torso"] = torso
    out["Right Arm"] = upper @ base.world["Right Arm"]
    out["Left Arm"] = upper @ base.world["Left Arm"]
    out["Head"] = head_world(p, torso, pitch=ch["head_pitch"], yaw=ch["head_yaw"])
    return out  # legs keep their base world CFrames


def transforms_from_world(world: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    out = {}
    for _, p0, p1, _, _ in rig.MOTORS:
        t = rig.solve_transform(p1, world[p0], world[p1])
        out[p1] = cf.orthonormalize(t)
    return out


def keyframe_times(params: Params) -> list[float]:
    n = int(round(params.period / params.key_step))
    return [round(i * params.period / n, 6) for i in range(n + 1)]
