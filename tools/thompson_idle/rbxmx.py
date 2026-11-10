"""Roblox XML model (.rbxmx) writer for the few classes this project emits."""
from __future__ import annotations

import itertools
from xml.sax.saxutils import escape

import numpy as np

MATERIALS = {"Plastic": 256, "SmoothPlastic": 272, "Wood": 512, "WoodPlanks": 528,
             "Metal": 1088, "DiamondPlate": 1056, "CorrodedMetal": 1040, "Foil": 1072}
PART_SHAPES = {"Ball": 0, "Block": 1, "Cylinder": 2}


def _num(v: float) -> str:
    s = f"{float(v):.7f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


class Node:
    _ids = itertools.count(1)

    def __init__(self, cls: str, name: str):
        self.cls = cls
        self.ref = f"RBX{next(Node._ids):08X}"
        self.props: list[str] = []
        self.children: list[Node] = []
        self.string("Name", name)

    def add(self, child: "Node") -> "Node":
        self.children.append(child)
        return child

    def string(self, name, v):
        self.props.append(f'<string name="{name}">{escape(v)}</string>')
        return self

    def bool(self, name, v):
        self.props.append(f'<bool name="{name}">{"true" if v else "false"}</bool>')
        return self

    def float(self, name, v):
        self.props.append(f'<float name="{name}">{_num(v)}</float>')
        return self

    def token(self, name, v):
        self.props.append(f'<token name="{name}">{int(v)}</token>')
        return self

    def ref_prop(self, name, node: "Node"):
        self.props.append(f'<Ref name="{name}">{node.ref}</Ref>')
        return self

    def vector3(self, name, v):
        x, y, z = (_num(c) for c in v)
        self.props.append(f'<Vector3 name="{name}"><X>{x}</X><Y>{y}</Y><Z>{z}</Z></Vector3>')
        return self

    def color3uint8(self, name, rgb):
        r, g, b = rgb
        self.props.append(f'<Color3uint8 name="{name}">{0xFF000000 | (r << 16) | (g << 8) | b}</Color3uint8>')
        return self

    def cframe(self, name, m: np.ndarray):
        p = m[:3, 3]
        r = m[:3, :3]
        body = "".join(f"<{k}>{_num(v)}</{k}>" for k, v in zip("XYZ", p))
        body += "".join(f"<R{i}{j}>{_num(r[i, j])}</R{i}{j}>" for i in range(3) for j in range(3))
        self.props.append(f'<CoordinateFrame name="{name}">{body}</CoordinateFrame>')
        return self

    def source(self, code: str):
        self.props.append(f'<ProtectedString name="Source"><![CDATA[{code}]]></ProtectedString>')
        return self

    def xml(self, indent: int = 1) -> str:
        pad = "\t" * indent
        inner = "\n".join(f"{pad}\t\t{p}" for p in self.props)
        kids = "".join(c.xml(indent + 1) for c in self.children)
        return (f'{pad}<Item class="{self.cls}" referent="{self.ref}">\n{pad}\t<Properties>\n{inner}\n'
                f"{pad}\t</Properties>\n{kids}{pad}</Item>\n")


def document(*roots: Node) -> str:
    body = "".join(r.xml() for r in roots)
    return ('<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">\n'
            "\t<External>null</External>\n\t<External>nil</External>\n"
            f"{body}</roblox>\n")
