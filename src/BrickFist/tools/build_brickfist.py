"""
Brick Fist — Stand mesh generator.

Builds the Stand out of sculpted, beveled, layered armour plates (rounded-box
cores deformed with taper / bulge / shear, never raw cubes or cylinders) and
writes a single OBJ that Roblox Studio's 3D Importer turns into one MeshPart
per object.

Object naming:   <Segment>__<Material>     e.g. RightHand__Clay
Joint markers:   Pivot_<JointName>         tiny octahedra the rig builder reads
Units: studs. Up = +Y. Front = -Z (Roblox LookVector). Right = +X.

Run:  python tools/build_brickfist.py
"""
import math
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "out")

# Material palette (also mirrored in the Luau rig builder and the preview).
MATERIALS = {
    "Clay":      (181 / 255, 120 / 255, 79 / 255),   # main fired-clay plates
    "ClayLight": (210 / 255, 152 / 255, 108 / 255),  # raised highlight plates
    "Trim":      (120 / 255, 72 / 255, 44 / 255),    # baked-brown trim bands
    "Core":      (62 / 255, 38 / 255, 26 / 255),     # mortar under-layer / body
    "Glow":      (1.0, 0.76, 0.28),                  # kiln-amber energy
    "Pivot":     (1.0, 0.0, 1.0),
}

# Joint name -> (position, parent segment, child segment)
JOINTS = {}
objects = defaultdict(lambda: {"v": [], "n": [], "f": []})


# --------------------------------------------------------------------------
# Geometry core
# --------------------------------------------------------------------------
def _axis_samples(h, inner, r, bevel_steps, mid_steps):
    pts = []
    for k in range(bevel_steps + 1):
        a = (1 - k / bevel_steps) * math.pi / 2
        pts.append(-inner - r * math.sin(a))
    for k in range(1, 2 * mid_steps):
        pts.append(-inner + 2 * inner * k / (2 * mid_steps))
    for k in range(bevel_steps, -1, -1):
        a = (1 - k / bevel_steps) * math.pi / 2
        pts.append(inner + r * math.sin(a))
    return pts


def rounded_box(size, r, bevel_steps=3, mid_steps=2):
    """Rounded box centred at origin: smooth bevels, no hard primitive edges."""
    h = [s / 2 for s in size]
    r = min(r, h[0] * 0.95, h[1] * 0.95, h[2] * 0.95)
    inner = [hh - r for hh in h]
    samples = [_axis_samples(h[i], inner[i], r, bevel_steps, mid_steps) for i in range(3)]

    verts, index, faces = [], {}, []

    def vid(p):
        key = (round(p[0], 5), round(p[1], 5), round(p[2], 5))
        if key not in index:
            index[key] = len(verts)
            verts.append(list(key))
        return index[key]

    def project(p):
        q = [max(-inner[i], min(inner[i], p[i])) for i in range(3)]
        d = [p[i] - q[i] for i in range(3)]
        L = math.sqrt(sum(c * c for c in d))
        if L < 1e-9:
            return p
        return [q[i] + d[i] / L * r for i in range(3)]

    for a in range(3):
        u, v = [i for i in range(3) if i != a]
        for sg in (-1, 1):
            su, sv = samples[u], samples[v]
            grid = []
            for x in su:
                row = []
                for y in sv:
                    p = [0.0, 0.0, 0.0]
                    p[a], p[u], p[v] = sg * h[a], x, y
                    row.append(vid(project(p)))
                grid.append(row)
            for i in range(len(su) - 1):
                for j in range(len(sv) - 1):
                    q = (grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])
                    for tri in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
                        if len(set(tri)) < 3:
                            continue
                        faces.append(_orient(verts, tri))
    return verts, faces


def _orient(verts, tri):
    a, b, c = (verts[i] for i in tri)
    n = _cross(_sub(b, a), _sub(c, a))
    cen = [(a[i] + b[i] + c[i]) / 3 for i in range(3)]
    return tri if _dot(n, cen) >= 0 else (tri[0], tri[2], tri[1])


def octahedron(s):
    v = [[s, 0, 0], [-s, 0, 0], [0, s, 0], [0, -s, 0], [0, 0, s], [0, 0, -s]]
    f = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
    return v, [_orient(v, t) for t in f]


def _sub(a, b): return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def _rotate(p, rot):
    rx, ry, rz = (math.radians(d) for d in rot)
    x, y, z = p
    y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
    x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
    x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
    return [x, y, z]


def add_mesh(name, verts, faces):
    obj = objects[name]
    base = len(obj["v"])
    obj["v"].extend(verts)
    # area-weighted smooth normals per piece (soft bevel highlights)
    normals = [[0.0, 0.0, 0.0] for _ in verts]
    for t in faces:
        a, b, c = (verts[i] for i in t)
        n = _cross(_sub(b, a), _sub(c, a))
        for i in t:
            normals[i] = [normals[i][k] + n[k] for k in range(3)]
    for n in normals:
        L = math.sqrt(_dot(n, n)) or 1.0
        obj["n"].append([n[0] / L, n[1] / L, n[2] / L])
    obj["f"].extend((t[0] + base, t[1] + base, t[2] + base) for t in faces)


def plate(seg, mat, center, size, r=0.12, rot=(0, 0, 0), taper=(1, 1), taperz=(1, 1),
          bulge=0.0, shear=(0, 0), bevel_steps=None, mid_steps=None):
    """A sculpted armour plate: rounded box + taper/bulge/shear, then rotated."""
    # density scales with the piece: small details stay cheap, big plates stay smooth
    if bevel_steps is None:
        bevel_steps = 1 if r < 0.1 else 2
    if mid_steps is None:
        mid_steps = 2 if bulge and max(size) > 0.7 else 1
    verts, faces = rounded_box(size, r, bevel_steps, mid_steps)
    hx, hy = size[0] / 2, size[1] / 2
    out = []
    for x, y, z in verts:
        t = (y + hy) / (2 * hy)
        x *= taper[0] + (taper[1] - taper[0]) * t
        z *= taperz[0] + (taperz[1] - taperz[0]) * t
        if bulge and z < 0:
            fy = max(0.0, 1 - (y / hy) ** 2)
            fx = max(0.0, 1 - (x / hx) ** 2)
            z -= bulge * fy * fx
        x += shear[0] * y
        z += shear[1] * y
        p = _rotate([x, y, z], rot)
        out.append([p[0] + center[0], p[1] + center[1], p[2] + center[2]])
    add_mesh(f"{seg}__{mat}", out, faces)


def joint(name, pos, parent, child):
    JOINTS[name] = (pos, parent, child)
    v, f = octahedron(0.06)
    add_mesh(f"Pivot_{name}", [[a + pos[i] for i, a in enumerate(p)] for p in v], f)


# --------------------------------------------------------------------------
# Brick Fist
# --------------------------------------------------------------------------
def build_head():
    S = "Head"
    # helm: tapered, forward-bulged mass with stepped masonry crown
    plate(S, "Clay", (0, 6.22, 0.02), (0.98, 1.0, 1.02), r=0.2, taper=(1.0, 0.86), taperz=(1.0, 0.9), bulge=0.06)
    plate(S, "ClayLight", (0, 6.72, 0.06), (0.66, 0.86, 0.16), r=0.07, rot=(84, 0, 0), bulge=0.08)
    plate(S, "Trim", (0, 6.84, 0.12), (0.34, 0.12, 0.6), r=0.05, rot=(-6, 0, 0))
    # heavy brow + visor recess + angry eye slits
    plate(S, "Trim", (0, 6.38, -0.5), (1.02, 0.2, 0.22), r=0.07, taper=(1.0, 1.08), bulge=0.03)
    plate(S, "Core", (0, 6.22, -0.46), (0.82, 0.2, 0.14), r=0.06)
    for sg in (1, -1):
        plate(S, "Glow", (0.2 * sg, 6.23, -0.53), (0.24, 0.075, 0.06), r=0.03, rot=(0, 0, -9 * sg), taper=(0.75, 1.0))
    # jaw plate with mortar grille
    plate(S, "Clay", (0, 5.95, -0.42), (0.74, 0.38, 0.2), r=0.08, taper=(0.74, 1.0), bulge=0.04)
    for y in (5.9, 5.98):
        plate(S, "Core", (0, y, -0.54), (0.36, 0.035, 0.04), r=0.015)
    # cheek guards + rear plate
    for sg in (1, -1):
        plate(S, "ClayLight", (0.5 * sg, 6.08, -0.12), (0.16, 0.56, 0.64), r=0.06, rot=(0, 10 * sg, 4 * sg), taper=(0.85, 1.0))
    plate(S, "Trim", (0, 6.2, 0.48), (0.86, 0.82, 0.16), r=0.07, taper=(0.9, 0.8))
    plate(S, "Core", (0, 5.68, 0.02), (0.52, 0.36, 0.52), r=0.16)


def build_upper_torso():
    S = "UpperTorso"
    # mortar body under-layer: broad V-taper chest
    plate(S, "Core", (0, 4.72, 0.06), (2.0, 1.86, 1.16), r=0.3, taper=(0.66, 1.0), taperz=(0.85, 1.0), bulge=0.05)
    # chiseled pec bricks
    for sg in (1, -1):
        plate(S, "Clay", (0.42 * sg, 5.06, -0.48), (0.8, 0.64, 0.3), r=0.12, rot=(-6, 8 * sg, 0), taper=(0.86, 1.0), bulge=0.06)
    # keystone at the sternum (masonry motif)
    plate(S, "ClayLight", (0, 5.12, -0.62), (0.3, 0.36, 0.14), r=0.04, taper=(0.62, 1.0))
    # ab bricks: 2 x 3, narrowing downward, staggered like a wall
    rows = [(4.56, 0.36, 0.0), (4.24, 0.34, 0.02), (3.94, 0.31, 0.0)]
    for y, w, stagger in rows:
        for sg in (1, -1):
            plate(S, "Clay", (0.2 * sg + stagger, y, -0.46), (w, 0.27, 0.22), r=0.07, taper=(0.92, 1.0), bulge=0.03)
    # V collar plates framing the chest
    for sg in (1, -1):
        plate(S, "Trim", (0.6 * sg, 4.78, -0.5), (0.22, 1.5, 0.24), r=0.08, rot=(-4, 0, -18 * sg), taper=(0.7, 1.0))
    plate(S, "Trim", (0, 5.5, 0.0), (1.2, 0.26, 1.02), r=0.1, taper=(1.0, 0.9))
    # trapezius yoke
    for sg in (1, -1):
        plate(S, "Clay", (0.76 * sg, 5.44, 0.06), (0.62, 0.3, 0.92), r=0.12, rot=(0, 0, -15 * sg), taper=(1.0, 0.8))
    # back plate + spine bricks
    plate(S, "Clay", (0, 4.86, 0.52), (1.62, 1.42, 0.3), r=0.15, taper=(0.72, 1.0))
    for i, y in enumerate((5.12, 4.74, 4.36)):
        plate(S, "ClayLight", (0, y, 0.7), (0.5 - i * 0.06, 0.28, 0.12), r=0.05)


def build_lower_torso():
    S = "LowerTorso"
    plate(S, "Core", (0, 3.4, 0.05), (1.24, 0.72, 0.86), r=0.22, taper=(1.05, 0.95))
    plate(S, "Trim", (0, 3.56, 0.0), (1.46, 0.3, 1.02), r=0.1, taperz=(1.0, 0.96))
    # keystone buckle with glowing kiln core
    plate(S, "ClayLight", (0, 3.55, -0.53), (0.48, 0.44, 0.16), r=0.06, taper=(0.7, 1.0))
    plate(S, "Glow", (0, 3.56, -0.62), (0.22, 0.16, 0.05), r=0.025, taper=(0.65, 1.0))
    # tassets flaring forward and out
    for sg in (1, -1):
        plate(S, "Clay", (0.56 * sg, 3.14, -0.38), (0.46, 0.5, 0.15), r=0.06, rot=(12, 0, 8 * sg), taper=(1.12, 1.0))
        plate(S, "Clay", (0.72 * sg, 3.16, 0.06), (0.15, 0.5, 0.62), r=0.06, rot=(0, 0, 10 * sg), taper=(1.1, 1.0))
    plate(S, "Trim", (0, 3.14, -0.44), (0.4, 0.46, 0.12), r=0.05, rot=(8, 0, 0), taper=(0.75, 1.0))
    plate(S, "Clay", (0, 3.2, 0.46), (0.92, 0.5, 0.15), r=0.06, rot=(-10, 0, 0))


def build_arm(sg, side):
    up, lo, hand = f"{side}UpperArm", f"{side}LowerArm", f"{side}Hand"
    x = 1.56 * sg
    # upper arm
    plate(up, "Core", (x, 4.6, 0.02), (0.56, 1.12, 0.6), r=0.2, taper=(0.86, 1.0))
    plate(up, "Clay", (x + 0.02 * sg, 4.58, -0.12), (0.5, 0.8, 0.44), r=0.14, taper=(0.88, 1.0), bulge=0.05)
    # three-tier masonry pauldron, each tier sloping further out; top tier is domed
    plate(up, "Clay", (1.68 * sg, 5.26, 0.0), (1.12, 1.16, 0.46), r=0.2, rot=(90, 0, -14 * sg), bulge=0.2, taper=(0.9, 0.9))
    plate(up, "ClayLight", (1.6 * sg, 5.62, 0.0), (0.38, 0.12, 0.52), r=0.05, rot=(0, 0, -14 * sg))
    plate(up, "Trim", (1.8 * sg, 5.02, 0.0), (1.06, 0.24, 1.12), r=0.08, rot=(0, 0, -20 * sg))
    plate(up, "Clay", (1.88 * sg, 4.82, 0.0), (0.86, 0.22, 0.96), r=0.08, rot=(0, 0, -26 * sg), taper=(0.9, 1.0))
    # forearm / gauntlet
    plate(lo, "Core", (1.68 * sg, 3.55, 0.0), (0.5, 0.96, 0.52), r=0.18)
    plate(lo, "Clay", (1.7 * sg, 3.46, 0.0), (0.72, 0.82, 0.74), r=0.16, taper=(1.0, 0.84), taperz=(1.0, 0.86), bulge=0.04)
    plate(lo, "Trim", (1.7 * sg, 3.86, 0.0), (0.66, 0.12, 0.68), r=0.05)
    plate(lo, "Trim", (1.7 * sg, 3.12, 0.0), (0.82, 0.15, 0.84), r=0.06)
    plate(lo, "ClayLight", (1.7 * sg, 4.0, 0.28), (0.44, 0.4, 0.3), r=0.1, rot=(-15, 0, 0))
    # oversized fist — right glove is the signature "Brick Fist"
    s = 1.3 if sg > 0 else 1.05
    wx, wy = 1.7 * sg, 3.02

    def hp(mat, off, size, **kw):
        c = (wx + off[0] * sg * s, wy + off[1] * s, off[2] * s)
        rot = kw.pop("rot", (0, 0, 0))
        plate(hand, mat, c, tuple(d * s for d in size), rot=(rot[0], rot[1] * sg, rot[2] * sg), **kw)

    hp("Trim", (0, -0.04, -0.02), (0.84, 0.18, 0.84), r=0.07)
    hp("Clay", (0, -0.46, -0.04), (0.78, 0.78, 0.82), r=0.2, taper=(1.05, 0.92), bulge=0.04)
    hp("ClayLight", (0.38, -0.44, -0.04), (0.14, 0.56, 0.66), r=0.05)          # back-of-hand plate
    hp("Trim", (0, -0.86, -0.04), (0.74, 0.18, 0.84), r=0.07)                 # knuckle plate
    for z in (-0.3, -0.1, 0.1, 0.3):
        hp("ClayLight", (0.04, -0.97, z - 0.04), (0.24, 0.12, 0.17), r=0.05, taper=(0.85, 1.0))  # knuckle studs
        hp("Clay", (-0.3, -0.7, z - 0.04), (0.24, 0.34, 0.18), r=0.07, rot=(0, 0, 12))           # curled fingers
    hp("Clay", (-0.22, -0.26, -0.44), (0.22, 0.4, 0.2), r=0.07, rot=(20, 0, -10))  # thumb
    if sg > 0:
        hp("Glow", (0.46, -0.44, -0.04), (0.04, 0.2, 0.3), r=0.015)  # kiln vent on the signature fist


def build_leg(sg, side):
    up, lo, ft = f"{side}UpperLeg", f"{side}LowerLeg", f"{side}Foot"
    plate(up, "Core", (0.58 * sg, 2.4, 0.02), (0.64, 1.26, 0.68), r=0.22, taper=(0.84, 1.0))
    plate(up, "Clay", (0.6 * sg, 2.46, -0.16), (0.6, 1.0, 0.46), r=0.14, taper=(0.86, 1.0), bulge=0.05)
    plate(up, "Trim", (0.87 * sg, 2.56, 0.0), (0.15, 0.82, 0.56), r=0.06, rot=(0, 0, 4 * sg), taper=(0.85, 1.0))
    plate(lo, "Core", (0.6 * sg, 1.15, 0.04), (0.56, 1.12, 0.6), r=0.2)
    plate(lo, "Clay", (0.6 * sg, 1.14, -0.17), (0.62, 1.06, 0.42), r=0.14, taper=(1.16, 0.9), bulge=0.05)
    plate(lo, "Clay", (0.6 * sg, 1.26, 0.3), (0.5, 0.8, 0.2), r=0.08, taper=(0.85, 1.0))
    plate(lo, "ClayLight", (0.6 * sg, 1.78, -0.34), (0.52, 0.5, 0.26), r=0.1, rot=(-8, 0, 0), bulge=0.03)
    plate(lo, "Glow", (0.6 * sg, 1.78, -0.48), (0.16, 0.12, 0.05), r=0.02, taper=(0.65, 1.0))
    plate(ft, "Trim", (0.62 * sg, 0.55, 0.0), (0.66, 0.18, 0.7), r=0.07)
    plate(ft, "Clay", (0.62 * sg, 0.26, -0.15), (0.76, 0.5, 1.16), r=0.14, taper=(1.0, 0.86), taperz=(1.0, 0.8))
    plate(ft, "Trim", (0.62 * sg, 0.19, -0.64), (0.72, 0.36, 0.3), r=0.1, taper=(1.0, 0.85))
    plate(ft, "Core", (0.62 * sg, 0.05, -0.12), (0.8, 0.1, 1.22), r=0.04)


def build_joints():
    joint("Root", (0, 3.2, 0), "HumanoidRootPart", "LowerTorso")
    joint("Waist", (0, 3.75, 0), "LowerTorso", "UpperTorso")
    joint("Neck", (0, 5.62, 0), "UpperTorso", "Head")
    for sg, side in ((1, "Right"), (-1, "Left")):
        joint(f"{side}Shoulder", (1.5 * sg, 5.15, 0), "UpperTorso", f"{side}UpperArm")
        joint(f"{side}Elbow", (1.68 * sg, 4.02, 0), f"{side}UpperArm", f"{side}LowerArm")
        joint(f"{side}Wrist", (1.7 * sg, 3.02, 0), f"{side}LowerArm", f"{side}Hand")
        joint(f"{side}Hip", (0.55 * sg, 3.05, 0), "LowerTorso", f"{side}UpperLeg")
        joint(f"{side}Knee", (0.6 * sg, 1.75, 0), f"{side}UpperLeg", f"{side}LowerLeg")
        joint(f"{side}Ankle", (0.62 * sg, 0.45, 0), f"{side}LowerLeg", f"{side}Foot")
    # orientation marker: a point straight in front of the root
    v, f = octahedron(0.06)
    add_mesh("Pivot_Forward", [[p[0], p[1] + 3.2, p[2] - 3.0] for p in v], f)


def write_obj():
    os.makedirs(OUT_DIR, exist_ok=True)
    obj_path = os.path.join(OUT_DIR, "BrickFist.obj")
    with open(os.path.join(OUT_DIR, "BrickFist.mtl"), "w") as m:
        for name, (r, g, b) in MATERIALS.items():
            m.write(f"newmtl {name}\nKd {r:.4f} {g:.4f} {b:.4f}\nKa 0 0 0\nKs 0.15 0.15 0.15\nNs 40\n\n")
    total = 0
    vo = 1
    with open(obj_path, "w") as o:
        o.write("# Brick Fist Stand — generated by tools/build_brickfist.py\nmtllib BrickFist.mtl\n")
        for name in sorted(objects):
            obj = objects[name]
            mat = name.split("__")[1] if "__" in name else "Pivot"
            # Studio's importer splits OBJ files on groups (g), not objects (o)
            o.write(f"o {name}\ng {name}\nusemtl {mat}\n")
            for v in obj["v"]:
                o.write(f"v {v[0]:.5f} {v[1]:.5f} {v[2]:.5f}\n")
            for n in obj["n"]:
                o.write(f"vn {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}\n")
            for a, b, c in obj["f"]:
                o.write(f"f {a + vo}//{a + vo} {b + vo}//{b + vo} {c + vo}//{c + vo}\n")
            vo += len(obj["v"])
            total += len(obj["f"])
            if not name.startswith("Pivot_"):
                print(f"  {name:28s} {len(obj['f']):6d} tris")
    print(f"Wrote {obj_path}  ({len(objects)} objects, {total} triangles)")


def write_glb():
    """Same objects as the OBJ, as a binary glTF. Studio's importer keeps every
    glTF node as its own MeshPart, whereas it can merge OBJ objects together."""
    import json
    import struct

    mat_names = list(MATERIALS)
    gltf = {
        "asset": {"version": "2.0", "generator": "build_brickfist.py"},
        "scene": 0,
        "scenes": [{"name": "BrickFist", "nodes": []}],
        "nodes": [], "meshes": [], "accessors": [], "bufferViews": [], "buffers": [],
        "materials": [
            {"name": m, "pbrMetallicRoughness": {
                "baseColorFactor": [*MATERIALS[m], 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.8}}
            for m in mat_names
        ],
    }
    blob = bytearray()

    def add_view(data, target):
        while len(blob) % 4:
            blob.append(0)
        gltf["bufferViews"].append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), "target": target})
        blob.extend(data)
        return len(gltf["bufferViews"]) - 1

    for name in sorted(objects):
        obj = objects[name]
        mat = name.split("__")[1] if "__" in name else "Pivot"
        pos = b"".join(struct.pack("<3f", *v) for v in obj["v"])
        nrm = b"".join(struct.pack("<3f", *n) for n in obj["n"])
        idx = b"".join(struct.pack("<3I", *f) for f in obj["f"])
        acc = len(gltf["accessors"])
        xs, ys, zs = zip(*obj["v"])
        gltf["accessors"] += [
            {"bufferView": add_view(pos, 34962), "componentType": 5126, "count": len(obj["v"]), "type": "VEC3",
             "min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)]},
            {"bufferView": add_view(nrm, 34962), "componentType": 5126, "count": len(obj["n"]), "type": "VEC3"},
            {"bufferView": add_view(idx, 34963), "componentType": 5125, "count": len(obj["f"]) * 3, "type": "SCALAR"},
        ]
        gltf["meshes"].append({"name": name, "primitives": [{
            "attributes": {"POSITION": acc, "NORMAL": acc + 1}, "indices": acc + 2,
            "material": mat_names.index(mat)}]})
        gltf["nodes"].append({"name": name, "mesh": len(gltf["meshes"]) - 1})
        gltf["scenes"][0]["nodes"].append(len(gltf["nodes"]) - 1)

    while len(blob) % 4:
        blob.append(0)
    gltf["buffers"].append({"byteLength": len(blob)})
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    path = os.path.join(OUT_DIR, "BrickFist.glb")
    with open(path, "wb") as g:
        g.write(struct.pack("<3I", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        g.write(struct.pack("<2I", len(js), 0x4E4F534A) + js)
        g.write(struct.pack("<2I", len(blob), 0x004E4942) + blob)
    print(f"Wrote {path}  ({len(gltf['nodes'])} nodes)")


if __name__ == "__main__":
    build_head()
    build_upper_torso()
    build_lower_torso()
    for sg, side in ((1, "Right"), (-1, "Left")):
        build_arm(sg, side)
        build_leg(sg, side)
    build_joints()
    write_obj()
    write_glb()
