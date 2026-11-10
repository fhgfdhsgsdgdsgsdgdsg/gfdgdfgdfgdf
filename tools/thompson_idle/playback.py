"""Read a KeyframeSequence .rbxmx back and sample it the way Roblox plays it.

Used for the preview renders and the checks, so both are driven by the exported
file rather than by the analytic curves that generated it.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import numpy as np

from . import cf, rig


def _cframe(el: ET.Element) -> np.ndarray:
    g = {c.tag: float(c.text) for c in el}
    rows = [g[f"R{i}{j}"] for i in range(3) for j in range(3)]
    return cf.new(g["X"], g["Y"], g["Z"], *rows)


def _props(item: ET.Element) -> dict[str, ET.Element]:
    return {p.get("name"): p for p in item.find("Properties")}


class Sequence:
    def __init__(self, keyframes: list[tuple[float, dict[str, tuple[np.ndarray, int]]]], loop: bool, priority: int):
        self.keyframes = sorted(keyframes, key=lambda k: k[0])
        self.loop = loop
        self.priority = priority
        self.length = self.keyframes[-1][0]

    @classmethod
    def load(cls, path: str, name: str | None = None) -> "Sequence":
        root = ET.parse(path).getroot()
        kfs = [i for i in root.iter("Item") if i.get("class") == "KeyframeSequence"]
        if name:
            kfs = [k for k in kfs if _props(k)["Name"].text == name]
        seq = kfs[0]
        sp = _props(seq)
        keyframes = []
        for kf in seq.findall("Item"):
            if kf.get("class") != "Keyframe":
                continue
            t = float(_props(kf)["Time"].text)
            poses: dict[str, tuple[np.ndarray, int]] = {}
            stack = [p for p in kf.findall("Item") if p.get("class") == "Pose"]
            while stack:
                p = stack.pop()
                pp = _props(p)
                poses[pp["Name"].text] = (_cframe(pp["CFrame"]), int(pp["EasingStyle"].text))
                stack.extend(c for c in p.findall("Item") if c.get("class") == "Pose")
            keyframes.append((t, poses))
        return cls(keyframes, sp["Loop"].text == "true", int(sp["Priority"].text))

    def sample(self, t: float) -> dict[str, np.ndarray]:
        """Motor6D.Transform per Part1 name at time t (linear easing only)."""
        if self.loop:
            t = t % self.length if self.length > 0 else 0.0
        kfs = self.keyframes
        out = {}
        for part in rig.PARTS[1:]:
            i = max(k for k in range(len(kfs)) if kfs[k][0] <= t + 1e-12)
            j = min(i + 1, len(kfs) - 1)
            a, style = kfs[i][1][part]
            b, _ = kfs[j][1][part]
            span = kfs[j][0] - kfs[i][0]
            alpha = 0.0 if span <= 0 else (t - kfs[i][0]) / span
            assert style == 0, "sampler only implements Linear easing"
            out[part] = cf.lerp(a, b, alpha)
        return out
