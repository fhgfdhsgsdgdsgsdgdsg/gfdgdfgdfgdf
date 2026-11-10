"""Blender (bpy) preview renderer for the Thompson R6 idle.

Run with the bpy-enabled interpreter, from the repository root:
    python tools/render_preview.py --still            # one frame, three views
    python tools/render_preview.py                    # full loop, three views

Input is build/preview_frames.json (written by `python -m thompson_idle.build`),
which is sampled from the exported KeyframeSequence exactly as Roblox plays it.
The character is a stand-in built on exact R6 part sizes, dressed to resemble
the reference avatar; in Roblox the animation drives the user's own avatar.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
from pathlib import Path

import bpy  # bpy must be imported before bmesh/mathutils
import bmesh
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
C4 = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))  # Roblox -> Blender axes

PALETTE = {
    "skin": (226, 155, 64),
    "white": (238, 240, 244),
    "maroon": (150, 72, 88),
    "maroon_dark": (118, 54, 68),
    "belt": (104, 66, 62),
    "gold": (226, 204, 128),
    "boot": (34, 38, 50),
    "boot_sole": (22, 24, 30),
    "strap": (30, 32, 38),
    "hair": (128, 78, 196),
    "hair_light": (168, 118, 224),
    "hair_dark": (92, 54, 160),
    "hair_tie": (26, 26, 40),
    "ground": (120, 124, 132),
}


def lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgba(rgb) -> tuple[float, float, float, float]:
    return (lin(rgb[0]), lin(rgb[1]), lin(rgb[2]), 1.0)


def rmat(m) -> Matrix:
    return Matrix([list(r) for r in m])


# ----------------------------------------------------------------------------- materials
_MATS: dict[str, bpy.types.Material] = {}


def _principled(name: str):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    return m, nt, bsdf


def plastic(key: str, rough: float = 0.55, spec: float = 0.35):
    name = f"plastic_{key}"
    if name not in _MATS:
        m, nt, b = _principled(name)
        b.inputs["Base Color"].default_value = rgba(PALETTE[key])
        b.inputs["Roughness"].default_value = rough
        b.inputs["Specular IOR Level"].default_value = spec
        _MATS[name] = m
    return _MATS[name]


def gold():
    if "gold" not in _MATS:
        m, nt, b = _principled("gold")
        b.inputs["Base Color"].default_value = rgba(PALETTE["gold"])
        b.inputs["Metallic"].default_value = 0.75
        b.inputs["Roughness"].default_value = 0.35
        _MATS["gold"] = m
    return _MATS["gold"]


def roblox_metal(rgb):
    """Roblox 'Metal': dark brushed steel with streaky roughness/tone variation."""
    name = f"metal_{rgb}"
    if name in _MATS:
        return _MATS[name]
    m, nt, b = _principled(name)
    n = nt.nodes
    tex = n.new("ShaderNodeTexCoord")
    mapping = n.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (2.0, 2.0, 40.0)
    noise = n.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 6.0
    noise.inputs["Detail"].default_value = 8.0
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[1].position = 0.75
    base = rgba(rgb)
    ramp.color_ramp.elements[0].color = tuple(c * 0.75 for c in base[:3]) + (1,)
    ramp.color_ramp.elements[1].color = tuple(min(1, c * 1.35) for c in base[:3]) + (1,)
    rough = n.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.28
    rough.inputs["To Max"].default_value = 0.5
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    nt.links.new(tex.outputs["Object"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(noise.outputs["Fac"], rough.inputs["Value"])
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(rough.outputs["Result"], b.inputs["Roughness"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Metallic"].default_value = 0.65
    _MATS[name] = m
    return m


def roblox_wood(rgb, axis: str):
    """Roblox 'Wood': walnut with ring grain running along the part's long axis."""
    name = f"wood_{rgb}_{axis}"
    if name in _MATS:
        return _MATS[name]
    m, nt, b = _principled(name)
    n = nt.nodes
    tex = n.new("ShaderNodeTexCoord")
    wave = n.new("ShaderNodeTexWave")
    wave.wave_type = "RINGS"
    wave.rings_direction = axis
    wave.inputs["Scale"].default_value = 3.5
    wave.inputs["Distortion"].default_value = 6.0
    wave.inputs["Detail"].default_value = 3.0
    wave.inputs["Detail Scale"].default_value = 1.5
    ramp = n.new("ShaderNodeValToRGB")
    base = rgba(rgb)
    ramp.color_ramp.elements[0].color = tuple(c * 0.62 for c in base[:3]) + (1,)
    ramp.color_ramp.elements[1].color = tuple(min(1, c * 1.18) for c in base[:3]) + (1,)
    ramp.color_ramp.elements[0].position = 0.2
    ramp.color_ramp.elements[1].position = 0.8
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    nt.links.new(tex.outputs["Object"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.55
    _MATS[name] = m
    return m


def smooth_plastic(rgb):
    name = f"smooth_{rgb}"
    if name not in _MATS:
        m, nt, b = _principled(name)
        b.inputs["Base Color"].default_value = rgba(rgb)
        b.inputs["Roughness"].default_value = 0.4
        _MATS[name] = m
    return _MATS[name]


def face_material(face_png: Path):
    """Skin + planar-projected face decal on the front of the head (-Z in Roblox space)."""
    m, nt, b = _principled("head")
    n = nt.nodes
    tex = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    u = n.new("ShaderNodeMapRange")
    v = n.new("ShaderNodeMapRange")
    for node in (u, v):
        node.inputs["From Min"].default_value = -0.6
        node.inputs["From Max"].default_value = 0.6
    comb = n.new("ShaderNodeCombineXYZ")
    img = n.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(str(face_png))
    img.extension = "CLIP"
    front = n.new("ShaderNodeMath")
    front.operation = "LESS_THAN"
    front.inputs[1].default_value = -0.15
    mask = n.new("ShaderNodeMath")
    mask.operation = "MULTIPLY"
    mix = n.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = rgba(PALETTE["skin"])
    nt.links.new(tex.outputs["Object"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["X"], u.inputs["Value"])
    nt.links.new(sep.outputs["Y"], v.inputs["Value"])
    nt.links.new(u.outputs["Result"], comb.inputs["X"])
    nt.links.new(v.outputs["Result"], comb.inputs["Y"])
    nt.links.new(comb.outputs["Vector"], img.inputs["Vector"])
    # Object coords are Blender-local; the head mesh is authored in Roblox axes, so -Z(rbx) == -Z(local).
    nt.links.new(sep.outputs["Z"], front.inputs[0])
    nt.links.new(front.outputs["Value"], mask.inputs[0])
    nt.links.new(img.outputs["Alpha"], mask.inputs[1])
    nt.links.new(mask.outputs["Value"], mix.inputs["Factor"])
    nt.links.new(img.outputs["Color"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.5
    b.inputs["Specular IOR Level"].default_value = 0.35
    return m


def draw_face(path: Path) -> None:
    """Confident smirk face like the reference: angled brows, narrow eyes, side smile, freckles."""
    from PIL import Image, ImageDraw

    s = 1024
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def px(x, y):  # head-local studs (x right, y up) -> pixels; texture spans [-0.6, 0.6]
        return ((x + 0.6) / 1.2 * s, (0.6 - y) / 1.2 * s)

    ink = (24, 18, 16, 255)
    # Image x grows toward the character's right (+X in Roblox head space), seen from the front.
    for sx in (-1, 1):
        brow = [px(sx * 0.09, 0.115), px(sx * 0.22, 0.17), px(sx * 0.37, 0.19), px(sx * 0.37, 0.165),
                px(sx * 0.22, 0.135), px(sx * 0.09, 0.09)]
        d.polygon(brow, fill=ink)
        eye = [px(sx * 0.12, 0.045), px(sx * 0.2, 0.075), px(sx * 0.33, 0.07), px(sx * 0.35, 0.035),
               px(sx * 0.27, 0.005), px(sx * 0.16, 0.01)]
        d.polygon(eye, fill=ink)
        gx, gy = px(sx * 0.215, 0.05)
        d.ellipse([gx - 9, gy - 9, gx + 9, gy + 9], fill=(250, 250, 250, 255))
    # Smirk: rises toward the character's left (viewer's right).
    pts = [px(-0.12, -0.2), px(-0.02, -0.215), px(0.08, -0.205), px(0.15, -0.175), px(0.19, -0.14)]
    d.line(pts, fill=ink, width=16, joint="curve")
    for x, y, r in ((-0.36, -0.12, 11), (-0.31, -0.16, 9), (-0.4, -0.17, 8), (0.35, -0.13, 10), (0.31, -0.17, 8)):
        cx, cy = px(x, y)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(170, 96, 40, 200))
    img.save(path)


# ----------------------------------------------------------------------------- meshes
def _obj(name: str, mesh, mat, parent, local: Matrix):
    o = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(o)
    if mat is not None:
        o.data.materials.append(mat)
    o.parent = parent
    o.matrix_parent_inverse = Matrix.Identity(4)
    o.matrix_basis = local
    return o


def _finish(bm, name):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def box(name, size, mat, parent, local=Matrix.Identity(4), bevel=0.0, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    me = _finish(bm, name)
    o = _obj(name, me, mat, parent, local)
    if bevel > 0:
        mod = o.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 3
        mod.limit_method = "NONE"
        mod.harden_normals = True
        for p in me.polygons:
            p.use_smooth = smooth
    return o


def cylinder(name, length, diameter, mat, parent, local=Matrix.Identity(4), segs=32, bevel=0.0):
    """Roblox cylinder: axis along local X."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=diameter / 2, radius2=diameter / 2, depth=length)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    me = _finish(bm, name)
    for p in me.polygons:
        p.use_smooth = len(p.vertices) == 4
    o = _obj(name, me, mat, parent, local)
    if bevel > 0:
        mod = o.modifiers.new("bevel", "BEVEL")
        mod.width = bevel
        mod.segments = 2
        mod.limit_method = "ANGLE"
        mod.harden_normals = True
    return o


def ball(name, dims, mat, parent, local=Matrix.Identity(4)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.5)
    for v in bm.verts:
        v.co = Vector((v.co.x * dims[0], v.co.y * dims[1], v.co.z * dims[2]))
    me = _finish(bm, name)
    for p in me.polygons:
        p.use_smooth = True
    return _obj(name, me, mat, parent, local)


def wedge(name, size, mat, parent, local=Matrix.Identity(4)):
    """Roblox WedgePart: full-height face at +Z, slope down to the -Z bottom edge."""
    sx, sy, sz = (s / 2 for s in size)
    verts = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, -sy, sz), (-sx, -sy, sz), (-sx, sy, sz), (sx, sy, sz)]
    faces = [(0, 3, 2, 1), (3, 4, 5, 2), (0, 1, 5, 4), (0, 4, 3), (1, 2, 5)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    return _obj(name, me, mat, parent, local)


def rounded_cylinder_head(name, mat, parent):
    """Classic R6 head mesh (SpecialMesh Head, scale 1.25): ~1.2 stud rounded cylinder."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=0.6, radius2=0.6, depth=1.2)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(-math.pi / 2, 3, "X"))
    me = _finish(bm, name)
    o = _obj(name, me, mat, parent, Matrix.Identity(4))
    mod = o.modifiers.new("bevel", "BEVEL")
    mod.width = 0.22
    mod.segments = 6
    mod.limit_method = "ANGLE"
    for p in me.polygons:
        p.use_smooth = True
    return o


def strand(name, pts, radii, mat, parent):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = 10
    cu.bevel_depth = 1.0
    cu.bevel_resolution = 3
    cu.use_fill_caps = True
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, p, r in zip(sp.bezier_points, pts, radii):
        bp.co = Vector(p)
        bp.handle_left_type = bp.handle_right_type = "AUTO"
        bp.radius = r
    o = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(o)
    o.data.materials.append(mat)
    o.parent = parent
    o.matrix_parent_inverse = Matrix.Identity(4)
    return o


def T(x=0.0, y=0.0, z=0.0) -> Matrix:
    return Matrix.Translation((x, y, z))


def R(axis: str, deg: float) -> Matrix:
    return Matrix.Rotation(math.radians(deg), 4, axis)


# ----------------------------------------------------------------------------- character
def build_character(empties: dict, face_png: Path) -> None:
    P = PALETTE
    white, skin, maroon = plastic("white"), plastic("skin"), plastic("maroon", 0.7)
    maroon_d, belt, boot = plastic("maroon_dark", 0.7), plastic("belt", 0.6), plastic("boot", 0.5)
    strap, sole = plastic("strap", 0.5), plastic("boot_sole", 0.6)
    hair = [plastic("hair", 0.42, 0.5), plastic("hair_light", 0.42, 0.5), plastic("hair_dark", 0.45, 0.5)]
    tie = plastic("hair_tie")

    # Torso: white shirt, maroon high-waist trousers + bib, suspenders, belt, back pouch.
    t = empties["Torso"]
    box("shirt", (2.0, 2.0, 1.0), white, t, bevel=0.06)
    box("waist", (2.05, 0.98, 1.05), maroon, t, T(0, -0.52, 0), bevel=0.05)
    box("bib", (1.25, 0.55, 0.06), maroon, t, T(0, 0.2, -0.53), bevel=0.02)
    for sx in (-1, 1):
        box(f"pad{sx}", (0.42, 0.14, 0.62), maroon, t, T(sx * 0.62, 1.03, 0.02), bevel=0.05)
        box(f"strapF{sx}", (0.16, 0.6, 0.04), strap, t, T(sx * 0.48, 0.72, -0.53))
        box(f"strapB{sx}", (0.16, 1.05, 0.04), strap, t, T(sx * 0.42, 0.5, 0.53))
    box("belt", (2.09, 0.17, 1.09), belt, t, T(0, -0.62, 0), bevel=0.02)
    for name, sz, loc in (("bkT", (0.3, 0.045, 0.04), (0, -0.53, -0.56)), ("bkB", (0.3, 0.045, 0.04), (0, -0.71, -0.56)),
                          ("bkL", (0.045, 0.22, 0.04), (-0.13, -0.62, -0.56)), ("bkR", (0.045, 0.22, 0.04), (0.13, -0.62, -0.56))):
        box(name, sz, gold(), t, T(*loc))
    box("pouch", (0.62, 0.4, 0.2), maroon, t, T(0, -0.68, 0.6), bevel=0.04)
    box("pouchFlap", (0.64, 0.16, 0.22), maroon_d, t, T(0, -0.52, 0.6), bevel=0.03)
    box("clasp", (0.12, 0.07, 0.03), gold(), t, T(0, -0.56, 0.715))

    # Arms: white puffed sleeve over the upper half, skin forearm/hand.
    for side in ("Right Arm", "Left Arm"):
        a = empties[side]
        box(f"{side}_sleeve", (1.07, 1.08, 1.07), white, a, T(0, 0.47, 0), bevel=0.09)
        box(f"{side}_hand", (0.98, 1.0, 0.98), skin, a, T(0, -0.5, 0), bevel=0.07)

    # Legs: maroon trousers with thigh strap + gold buckle, side pocket, black boots.
    for side, sx in (("Right Leg", 1), ("Left Leg", -1)):
        lg = empties[side]
        box(f"{side}_pants", (1.03, 1.3, 1.03), maroon, lg, T(0, 0.35, 0), bevel=0.06)
        box(f"{side}_strap", (1.07, 0.13, 1.07), belt, lg, T(0, 0.52, 0), bevel=0.02)
        for name, sz, loc in (("t", (0.22, 0.04, 0.04), (0, 0.6, -0.55)), ("b", (0.22, 0.04, 0.04), (0, 0.44, -0.55)),
                              ("l", (0.04, 0.2, 0.04), (-0.09, 0.52, -0.55)), ("r", (0.04, 0.2, 0.04), (0.09, 0.52, -0.55))):
            box(f"{side}_buckle{name}", sz, gold(), lg, T(*loc))
        box(f"{side}_pocket", (0.06, 0.36, 0.44), maroon_d, lg, T(sx * 0.53, 0.08, 0.02), bevel=0.02)
        box(f"{side}_boot", (1.06, 0.8, 1.08), boot, lg, T(0, -0.6, -0.02), bevel=0.07)
        box(f"{side}_cuff", (1.12, 0.14, 1.14), boot, lg, T(0, -0.21, -0.02), bevel=0.04)
        box(f"{side}_sole", (1.08, 0.07, 1.14), sole, lg, T(0, -0.965, -0.04), bevel=0.02)

    # Head + face + purple hair with high ponytail.
    h = empties["Head"]
    rounded_cylinder_head("head", face_material(face_png), h)
    ball("hairCap", (1.36, 0.8, 1.36), hair[0], h, T(0, 0.33, 0.04))
    box("hairBack", (1.3, 0.95, 0.5), hair[0], h, T(0, -0.02, 0.38), bevel=0.2)
    for sx in (-1, 1):
        box(f"hairSide{sx}", (0.2, 0.85, 0.75), hair[0], h, T(sx * 0.6, 0.02, 0.1), bevel=0.08)
        box(f"bang{sx}", (0.6, 0.17, 0.2), hair[1], h, T(sx * 0.27, 0.43, -0.56) @ R("Z", -sx * 14), bevel=0.07)
    rng = random.Random(7)
    for sx in (-1, 1):  # face-framing locks
        for k in range(3):
            x0 = sx * (0.4 + 0.09 * k)
            z0 = -0.55 + 0.12 * k
            pts = [(x0, 0.38, z0), (sx * (0.62 + 0.02 * k), 0.08, z0 + 0.04),
                   (sx * (0.66 + 0.03 * k), -0.32, z0 + 0.06 + rng.uniform(-0.03, 0.03)),
                   (sx * (0.6 + 0.04 * k), -0.78 + 0.06 * k, z0 + 0.1)]
            strand(f"lock{sx}{k}", pts, [0.08, 0.075, 0.06, 0.03], hair[k % 3], h)
    tie_m = T(0, 0.6, 0.46) @ R("X", -35) @ R("Z", 90)
    cylinder("tie", 0.14, 0.3, tie, h, tie_m)
    ball("puff", (0.55, 0.5, 0.55), hair[0], h, T(0, 0.84, 0.5))
    for k in range(13):
        a = (k / 12.0 - 0.5)
        x_end = a * 0.8 + rng.uniform(-0.05, 0.05)
        top = (a * 0.3, 1.0 + rng.uniform(0, 0.12), 0.48 + rng.uniform(-0.05, 0.08))
        pts = [(a * 0.18, 0.86, 0.45), top,
               (a * 0.45, 0.9, 0.95 + rng.uniform(0, 0.1)),
               (x_end * 0.9, 0.3 + rng.uniform(-0.08, 0.08), 1.05 + rng.uniform(-0.05, 0.08)),
               (x_end, -0.35 + rng.uniform(-0.1, 0.1), 1.0 + rng.uniform(-0.04, 0.06)),
               (x_end * 1.1 + rng.uniform(-0.08, 0.08), -0.95 + rng.uniform(-0.2, 0.15), 0.98 + rng.uniform(0, 0.12))]
        strand(f"tail{k}", pts, [0.1, 0.12, 0.11, 0.09, 0.07, 0.025], hair[k % 3], h)


def build_gun(parent, parts) -> None:
    for p in parts:
        size = p["size"]
        local = rmat(p["cframe"])
        if p["material"] == "Wood":
            axis = "XYZ"[max(range(3), key=lambda i: size[i])]
            mat = roblox_wood(tuple(p["color"]), axis)
        elif p["material"] == "Metal":
            mat = roblox_metal(tuple(p["color"]))
        else:
            mat = smooth_plastic(tuple(p["color"]))
        if p["shape"] == "Block":
            box(p["name"], size, mat, parent, local, bevel=min(0.012, min(size) * 0.2))
        elif p["shape"] == "Cylinder":
            cylinder(p["name"], size[0], min(size[1], size[2]), mat, parent, local, bevel=0.006)
        elif p["shape"] == "Ball":
            ball(p["name"], size, mat, parent, local)
        elif p["shape"] == "Wedge":
            wedge(p["name"], size, mat, parent, local)


# ----------------------------------------------------------------------------- scene
def setup_scene(res: int, samples: int):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"

    world = bpy.data.worlds.new("world")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = rgba((176, 196, 214))
    bg.inputs["Strength"].default_value = 0.9

    sun = bpy.data.lights.new("sun", "SUN")
    sun.energy = 3.2
    sun.angle = math.radians(4)
    so = bpy.data.objects.new("sun", sun)
    sc.collection.objects.link(so)
    so.rotation_euler = (math.radians(38), 0, math.radians(-35))

    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=60)
    me = _finish(bm, "ground")
    ground = bpy.data.objects.new("ground", me)
    sc.collection.objects.link(ground)
    ground.data.materials.append(plastic("ground", 0.85, 0.2))
    return sc


def add_camera(name: str, pos_r, target_r, fov_deg: float):
    cam = bpy.data.cameras.new(name)
    cam.sensor_fit = "VERTICAL"
    cam.angle = math.radians(fov_deg)
    o = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(o)
    pos = C4 @ Vector((*pos_r, 1.0))
    tgt = C4 @ Vector((*target_r, 1.0))
    o.location = pos.xyz
    o.rotation_euler = (tgt.xyz - pos.xyz).to_track_quat("-Z", "Y").to_euler()
    return o


def cameras(body_yaw: float) -> dict:
    """Required views approximate the three reference shots; the rest are extra coverage angles."""

    def orbit(name, azimuth_deg, dist, height, target, fov):
        a = math.radians(azimuth_deg)  # 0 = in front of the aim line (-Z), positive toward the character's right
        pos = (target[0] + math.sin(a) * dist, height, target[2] - math.cos(a) * dist)
        return add_camera(name, pos, target, fov)

    back = 180 + math.degrees(body_yaw)  # directly behind the torso
    return {
        "front": orbit("front", 14, 9.4, 4.4, (0.25, 2.75, -0.6), 40),
        "rear_left": orbit("rear_left", back + 12, 9.0, 5.0, (-0.2, 2.85, -0.6), 40),
        "right_side": orbit("right_side", 102, 9.0, 4.5, (0.3, 2.95, -0.8), 40),
        "front_right": orbit("front_right", 50, 9.4, 4.2, (0.3, 2.85, -0.6), 40),
        "left_side": orbit("left_side", -90, 9.0, 4.0, (0.3, 2.6, -0.8), 38),
        "rear_right": orbit("rear_right", 145, 9.0, 4.6, (0.2, 2.7, -0.4), 38),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default=str(ROOT / "build" / "preview_frames.json"))
    ap.add_argument("--out", default=str(ROOT / "build" / "render"))
    ap.add_argument("--res", type=int, default=720)
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--still", action="store_true", help="render frame 0 only")
    ap.add_argument("--frame", type=int, default=0)
    ap.add_argument("--start", type=int, default=0, help="first frame (full-loop mode)")
    ap.add_argument("--end", type=int, default=-1, help="last frame, inclusive (full-loop mode)")
    ap.add_argument("--views", default="front,rear_left,right_side")
    args = ap.parse_args()

    data = json.loads(Path(args.frames).read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = setup_scene(args.res, args.samples)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    face_png = out / "face.png"
    draw_face(face_png)

    empties = {}
    for name in ("Torso", "Head", "Right Arm", "Left Arm", "Right Leg", "Left Leg", "Gun"):
        e = bpy.data.objects.new(name, None)
        sc.collection.objects.link(e)
        empties[name] = e
    build_character(empties, face_png)
    build_gun(empties["Gun"], data["gun_parts"])
    cams = cameras(data["body_yaw"])
    views = args.views.split(",")

    last = len(data["frames"]) - 1 if args.end < 0 else min(args.end, len(data["frames"]) - 1)
    frames = [args.frame] if args.still else range(args.start, last + 1)
    for i in frames:
        f = data["frames"][i]
        for name, e in empties.items():
            e.matrix_world = C4 @ rmat(f[name])
        for v in views:
            sc.camera = cams[v]
            sc.render.filepath = str(out / v / f"frame_{i:04d}.png")
            bpy.ops.render.render(write_still=True)
        print(f"frame {i} done", flush=True)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
