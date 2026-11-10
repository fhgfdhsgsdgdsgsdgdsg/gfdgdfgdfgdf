"""Classic Roblox R6 rig: part sizes and the six standard Motor6D joints.

C0/C1 values are the stock values Roblox uses for every R6 character.
Part1.CFrame = Part0.CFrame * C0 * Transform * C1:Inverse()
"""
from __future__ import annotations

import numpy as np

from . import cf

SIZES = {
    "HumanoidRootPart": (2.0, 2.0, 1.0),
    "Torso": (2.0, 2.0, 1.0),
    "Head": (2.0, 1.0, 1.0),
    "Right Arm": (1.0, 2.0, 1.0),
    "Left Arm": (1.0, 2.0, 1.0),
    "Right Leg": (1.0, 2.0, 1.0),
    "Left Leg": (1.0, 2.0, 1.0),
}

_ROOT = (-1, 0, 0, 0, 0, 1, 0, 1, 0)
_RIGHT = (0, 0, 1, 0, 1, 0, -1, 0, 0)
_LEFT = (0, 0, -1, 0, 1, 0, 1, 0, 0)

# name, Part0, Part1, C0, C1
MOTORS = [
    ("RootJoint", "HumanoidRootPart", "Torso", cf.new(0, 0, 0, *_ROOT), cf.new(0, 0, 0, *_ROOT)),
    ("Neck", "Torso", "Head", cf.new(0, 1, 0, *_ROOT), cf.new(0, -0.5, 0, *_ROOT)),
    ("Right Shoulder", "Torso", "Right Arm", cf.new(1, 0.5, 0, *_RIGHT), cf.new(-0.5, 0.5, 0, *_RIGHT)),
    ("Left Shoulder", "Torso", "Left Arm", cf.new(-1, 0.5, 0, *_LEFT), cf.new(0.5, 0.5, 0, *_LEFT)),
    ("Right Hip", "Torso", "Right Leg", cf.new(1, -1, 0, *_RIGHT), cf.new(0.5, 1, 0, *_RIGHT)),
    ("Left Hip", "Torso", "Left Leg", cf.new(-1, -1, 0, *_LEFT), cf.new(-0.5, 1, 0, *_LEFT)),
]
MOTOR_BY_PART1 = {m[2]: m for m in MOTORS}
PARTS = ["HumanoidRootPart", "Torso", "Head", "Right Arm", "Left Arm", "Right Leg", "Left Leg"]

# R6 HumanoidRootPart sits 3 studs above the floor (legs 2 + half torso 1).
HRP_HEIGHT = 3.0

# Legacy R6 RightGrip weld: Right Arm -> Tool.Handle, C1 = Tool.Grip.
RIGHT_GRIP_C0 = cf.new(0, -1, 0, 1, 0, 0, 0, 0, 1, 0, -1, 0)


def fk(transforms: dict[str, np.ndarray], hrp: np.ndarray | None = None) -> dict[str, np.ndarray]:
    """World CFrames for every part given Motor6D.Transform per Part1 name."""
    world = {"HumanoidRootPart": np.eye(4) if hrp is None else hrp}
    for _, p0, p1, c0, c1 in MOTORS:
        t = transforms.get(p1, np.eye(4))
        world[p1] = world[p0] @ c0 @ t @ cf.inv(c1)
    return world


def solve_transform(part1: str, part0_world: np.ndarray, part1_world: np.ndarray) -> np.ndarray:
    """Motor6D.Transform that places part1 at part1_world (rotation only is meaningful for R6)."""
    _, _, _, c0, c1 = MOTOR_BY_PART1[part1]
    return cf.inv(c0) @ cf.inv(part0_world) @ part1_world @ c1


def pivot_world(part1: str, part0_world: np.ndarray) -> np.ndarray:
    _, _, _, c0, _ = MOTOR_BY_PART1[part1]
    return cf.point(part0_world, c0[:3, 3])


def pivot_local(part1: str) -> np.ndarray:
    _, _, _, _, c1 = MOTOR_BY_PART1[part1]
    return c1[:3, 3].copy()
