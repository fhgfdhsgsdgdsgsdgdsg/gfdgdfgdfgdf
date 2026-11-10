"""Thompson M1928/M1A1-style submachine gun built from Roblox primitives.

Gun-local frame: origin = right-hand hold point on the pistol grip,
-Z = muzzle direction, +Y = up. The foregrip hold point is (0, 0, -d), so
both hands share one horizontal line under the bore.
Cylinders follow Roblox convention (axis = local X); wedges follow WedgePart
(full-height face at +Z, slope rising from -Z bottom edge to +Z top edge).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import cf

# Colors (RGB 0-255)
GUNMETAL = (58, 60, 66)
BLUED = (36, 38, 43)
STEEL_LIGHT = (92, 95, 102)
BLACK = (16, 16, 18)
WALNUT = (122, 72, 38)
WALNUT_DARK = (96, 55, 30)
MAG = (30, 31, 35)

BORE_Y = 0.70


@dataclass
class GunPart:
    name: str
    shape: str  # Block | Cylinder | Ball | Wedge
    size: tuple[float, float, float]
    cframe: np.ndarray  # gun-local
    color: tuple[int, int, int]
    material: str  # Roblox Enum.Material name

    @property
    def class_name(self) -> str:
        return "WedgePart" if self.shape == "Wedge" else "Part"


def _at(x: float, y: float, z: float, rot: np.ndarray | None = None) -> np.ndarray:
    m = cf.translate(x, y, z)
    return m @ rot if rot is not None else m


ALONG_Z = cf.ry(math.pi / 2)  # cylinder axis (local X) -> gun Z
ALONG_Y = cf.rz(math.pi / 2)  # cylinder axis (local X) -> gun Y


def build(d: float, stock_back: float = 1.28, fore_drop: float = 0.0) -> list[GunPart]:
    """Parts for grip spacing `d`, butt position `stock_back` (gun-local +Z) and the
    left-hand contact `fore_drop` studs below the pistol-grip hold point."""
    p: list[GunPart] = []

    def add(name, shape, size, cframe, color, material="Metal"):
        p.append(GunPart(name, shape, tuple(float(s) for s in size), cframe, color, material))

    # --- Receiver (Handle) -------------------------------------------------
    rec_rear, rec_front = 0.48, -0.66
    add("Handle", "Block", (0.30, 0.34, rec_rear - rec_front),
        _at(0, 0.69, (rec_rear + rec_front) / 2), GUNMETAL)
    add("ReceiverTop", "Block", (0.20, 0.035, 0.80), _at(0, 0.875, -0.15), BLUED)
    add("RearCap", "Cylinder", (0.06, 0.30, 0.30), _at(0, 0.69, rec_rear + 0.02, ALONG_Z), BLUED)
    add("EjectionPort", "Block", (0.012, 0.15, 0.30), _at(0.150, 0.73, -0.27), BLACK, "SmoothPlastic")
    add("CockingKnobPost", "Cylinder", (0.10, 0.07, 0.07), _at(0, 0.92, -0.20, ALONG_Y), STEEL_LIGHT)
    add("CockingKnob", "Ball", (0.12, 0.12, 0.12), _at(0, 0.975, -0.20), STEEL_LIGHT)
    add("SafetyLever", "Block", (0.02, 0.05, 0.13), _at(-0.155, 0.60, 0.22, cf.rx(math.radians(-20))), STEEL_LIGHT)
    add("SelectorLever", "Block", (0.02, 0.05, 0.13), _at(-0.155, 0.60, 0.02, cf.rx(math.radians(15))), STEEL_LIGHT)
    add("SelectorPivot", "Cylinder", (0.02, 0.06, 0.06), _at(-0.16, 0.62, 0.12), STEEL_LIGHT)

    # Rear sight (protected L-type) on the receiver top
    add("RearSightBase", "Block", (0.16, 0.04, 0.18), _at(0, 0.88, 0.30), BLUED)
    add("RearSightEarL", "Block", (0.03, 0.12, 0.12), _at(-0.065, 0.95, 0.30), BLUED)
    add("RearSightEarR", "Block", (0.03, 0.12, 0.12), _at(0.065, 0.95, 0.30), BLUED)
    add("RearSightLeaf", "Block", (0.07, 0.09, 0.025), _at(0, 0.94, 0.30), STEEL_LIGHT)

    # Lower frame, trigger guard, trigger
    add("TriggerFrame", "Block", (0.24, 0.12, 0.56), _at(0, 0.46, 0.16), GUNMETAL)
    add("TriggerGuardBottom", "Block", (0.06, 0.04, 0.32), _at(0, 0.22, -0.16), BLUED)
    add("TriggerGuardFront", "Block", (0.06, 0.24, 0.04), _at(0, 0.32, -0.30), BLUED)
    add("Trigger", "Block", (0.03, 0.14, 0.035), _at(0, 0.33, -0.13, cf.rx(math.radians(-15))), BLACK)

    # Pistol grip (walnut, raked back) through the hold point
    rake = math.radians(-14)
    add("PistolGrip", "Block", (0.20, 1.05, 0.26), _at(0, -0.03, 0.008, cf.rx(rake)), WALNUT, "Wood")
    add("PistolGripCap", "Block", (0.21, 0.035, 0.27),
        _at(0, -0.545, 0.135, cf.rx(rake)), BLUED)

    # Stick magazine ahead of the trigger guard
    add("MagWell", "Block", (0.20, 0.12, 0.28), _at(0, 0.46, -0.48), GUNMETAL)
    add("Magazine", "Block", (0.15, 0.80, 0.22), _at(0, 0.12, -0.48), MAG)
    add("MagazineBase", "Block", (0.17, 0.035, 0.24), _at(0, -0.29, -0.48), BLUED)
    add("MagazineRib", "Block", (0.155, 0.62, 0.03), _at(0, 0.10, -0.596), BLUED)

    # --- Barrel: finned section, plain barrel, Cutts compensator -----------
    fin_start = rec_front - 0.02
    fin_end = -(d + 0.40)
    muzzle = -max(d + 0.95, 2.35)  # overall length independent of the hand spacing
    comp_len = 0.26
    barrel_core_len = abs(muzzle - rec_front) - comp_len
    add("Barrel", "Cylinder", (barrel_core_len, 0.11, 0.11),
        _at(0, BORE_Y, rec_front - barrel_core_len / 2, ALONG_Z), BLUED)
    add("FinCore", "Cylinder", (fin_start - fin_end, 0.16, 0.16),
        _at(0, BORE_Y, (fin_start + fin_end) / 2, ALONG_Z), BLUED)
    n_fins = int(round((fin_start - fin_end) / 0.075))
    for i in range(n_fins):
        z = fin_start - 0.04 - i * (fin_start - fin_end - 0.08) / max(n_fins - 1, 1)
        add(f"Fin{i + 1:02d}", "Cylinder", (0.035, 0.25, 0.25), _at(0, BORE_Y, z, ALONG_Z), BLUED)
    comp_mid = muzzle + comp_len / 2
    add("Compensator", "Cylinder", (comp_len, 0.17, 0.17), _at(0, BORE_Y, comp_mid, ALONG_Z), STEEL_LIGHT)
    for i in range(4):
        add(f"CompensatorSlot{i + 1}", "Block", (0.10, 0.012, 0.022),
            _at(0, BORE_Y + 0.082, muzzle + 0.06 + i * 0.045), BLACK, "SmoothPlastic")
    add("MuzzleBore", "Cylinder", (0.012, 0.07, 0.07), _at(0, BORE_Y, muzzle - 0.002, ALONG_Z), BLACK, "SmoothPlastic")
    add("FrontSight", "Block", (0.025, 0.09, 0.07), _at(0, BORE_Y + 0.12, muzzle + 0.21), STEEL_LIGHT)

    # --- Vertical foregrip at the support-hand point -----------------------
    # Its raked axis passes exactly through the left-hand contact (0, -fore_drop, -d);
    # the lower end sits inside the hand.
    fz = -d
    add("ForegripCollar", "Cylinder", (0.12, 0.29, 0.29), _at(0, BORE_Y, fz, ALONG_Z), GUNMETAL)
    add("ForegripMount", "Block", (0.12, 0.10, 0.14), _at(0, BORE_Y - 0.15, fz), GUNMETAL)
    rake = math.radians(4)
    yh = -fore_drop
    top, bottom = BORE_Y - 0.10, yh - 0.12
    yc = (top + bottom) / 2
    grip_cf = _at(0, yc, fz - (yh - yc) * math.tan(rake), cf.rx(rake))
    add("Foregrip", "Block", (0.19, (top - bottom) / math.cos(rake), 0.25), grip_cf, WALNUT, "Wood")
    t_contact = (yh - yc) / math.cos(rake)
    for i in range(3):
        add(f"ForegripRidge{i + 1}", "Block", (0.17, 0.05, 0.03),
            grip_cf @ cf.translate(0, t_contact + 0.30 + i * 0.12, -0.135), WALNUT_DARK, "Wood")

    # --- Buttstock ----------------------------------------------------------
    # Length is fitted per pose so the butt plate rests just short of the chest.
    s_front = 0.46
    s_back = min(stock_back, 1.28) - 0.035
    s_len = s_back - s_front
    toe_len, toe_h = 0.7 * s_len, 0.24
    add("StockUpper", "Block", (0.22, 0.30, s_len), _at(0, 0.67, (s_front + s_back) / 2), WALNUT, "Wood")
    # WedgePart flipped upside down: tall face at the butt, taper toward the wrist.
    add("StockToe", "Wedge", (0.22, toe_h, toe_len), _at(0, 0.52 - toe_h / 2, s_back - toe_len / 2, cf.rz(math.pi)),
        WALNUT, "Wood")
    add("StockTang", "Block", (0.24, 0.18, 0.10), _at(0, 0.70, s_front + 0.02), BLUED)
    add("ButtPlate", "Block", (0.235, 0.56, 0.035), _at(0, 0.55, s_back + 0.0175), BLUED)
    add("SlingSwivel", "Cylinder", (0.03, 0.08, 0.08), _at(0, 0.51, s_front + 0.14), STEEL_LIGHT)
    return p


def hold_points(d: float, fore_drop: float = 0.0) -> dict[str, np.ndarray]:
    return {"right": np.zeros(3), "left": np.array([0.0, -fore_drop, -d])}


def handle_local(parts: list[GunPart]) -> np.ndarray:
    return next(x.cframe for x in parts if x.name == "Handle")
