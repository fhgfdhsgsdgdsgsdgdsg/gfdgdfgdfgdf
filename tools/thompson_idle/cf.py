"""Minimal Roblox-style CFrame math on 4x4 numpy matrices.

Conventions match Roblox: +Y up, -Z forward (LookVector), right-handed.
CFrame.new(x, y, z, r00..r22) takes the rotation matrix row by row.
"""
from __future__ import annotations

import math

import numpy as np


def new(x: float = 0.0, y: float = 0.0, z: float = 0.0, *rows: float) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    if rows:
        m[:3, :3] = np.asarray(rows, dtype=float).reshape(3, 3)
    return m


def from_rot(r: np.ndarray, p=(0.0, 0.0, 0.0)) -> np.ndarray:
    m = np.eye(4)
    m[:3, :3] = r
    m[:3, 3] = p
    return m


def rx(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return from_rot(np.array([[1, 0, 0], [0, c, -s], [0, s, c]]))


def ry(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return from_rot(np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]]))


def rz(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return from_rot(np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]]))


def angles(ax: float, ay: float, az: float) -> np.ndarray:
    """CFrame.Angles / fromEulerAnglesXYZ."""
    return rx(ax) @ ry(ay) @ rz(az)


def axis_angle(axis, a: float) -> np.ndarray:
    k = np.asarray(axis, dtype=float)
    k = k / np.linalg.norm(k)
    kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    r = np.eye(3) + math.sin(a) * kx + (1 - math.cos(a)) * (kx @ kx)
    return from_rot(r)


def translate(x: float, y: float, z: float) -> np.ndarray:
    return new(x, y, z)


def inv(m: np.ndarray) -> np.ndarray:
    r = m[:3, :3]
    out = np.eye(4)
    out[:3, :3] = r.T
    out[:3, 3] = -r.T @ m[:3, 3]
    return out


def about_point(rot: np.ndarray, point) -> np.ndarray:
    """Rotation `rot` (4x4, rotation only) applied about `point`."""
    p = np.asarray(point, dtype=float)
    return translate(*p) @ rot @ translate(*(-p))


def pos(m: np.ndarray) -> np.ndarray:
    return m[:3, 3].copy()


def point(m: np.ndarray, local) -> np.ndarray:
    return m[:3, :3] @ np.asarray(local, dtype=float) + m[:3, 3]


def orthonormalize(m: np.ndarray) -> np.ndarray:
    u, _, vt = np.linalg.svd(m[:3, :3])
    out = m.copy()
    out[:3, :3] = u @ vt
    return out


def rot_angle_deg(m: np.ndarray) -> float:
    c = (np.trace(m[:3, :3]) - 1.0) / 2.0
    return math.degrees(math.acos(max(-1.0, min(1.0, c))))


def quat(m: np.ndarray) -> np.ndarray:
    """Rotation part as unit quaternion (w, x, y, z)."""
    r = m[:3, :3]
    t = np.trace(r)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = [0.25 * s, (r[2, 1] - r[1, 2]) / s, (r[0, 2] - r[2, 0]) / s, (r[1, 0] - r[0, 1]) / s]
    elif r[0, 0] > r[1, 1] and r[0, 0] > r[2, 2]:
        s = math.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2]) * 2
        q = [(r[2, 1] - r[1, 2]) / s, 0.25 * s, (r[0, 1] + r[1, 0]) / s, (r[0, 2] + r[2, 0]) / s]
    elif r[1, 1] > r[2, 2]:
        s = math.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2]) * 2
        q = [(r[0, 2] - r[2, 0]) / s, (r[0, 1] + r[1, 0]) / s, 0.25 * s, (r[1, 2] + r[2, 1]) / s]
    else:
        s = math.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1]) * 2
        q = [(r[1, 0] - r[0, 1]) / s, (r[0, 2] + r[2, 0]) / s, (r[1, 2] + r[2, 1]) / s, 0.25 * s]
    q = np.array(q)
    return q / np.linalg.norm(q)


def from_quat(q, p=(0.0, 0.0, 0.0)) -> np.ndarray:
    w, x, y, z = np.asarray(q, dtype=float) / np.linalg.norm(q)
    r = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])
    return from_rot(r, p)


def lerp(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    """CFrame:Lerp — slerp rotation, lerp position."""
    qa, qb = quat(a), quat(b)
    d = float(np.dot(qa, qb))
    if d < 0:
        qb, d = -qb, -d
    if d > 0.9995:
        q = qa + t * (qb - qa)
    else:
        th = math.acos(d)
        q = (math.sin((1 - t) * th) * qa + math.sin(t * th) * qb) / math.sin(th)
    return from_quat(q, (1 - t) * a[:3, 3] + t * b[:3, 3])
