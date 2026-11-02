# Brick Fist — high-detail stone guardian Stand, built procedurally in Blender 5.x.
#
#   blender --background --factory-startup --python build_brickfist_sculpt.py -- <out_dir> [preview|final]
#
# Every body part is a lofted, subdivision-friendly quad mesh (superellipse cross-sections with
# support loops), finished with Bevel / Subdivision / Displace modifiers and procedural materials.
# Centre-line details are modelled on the right side and mirrored with a Mirror modifier, which is
# applied at the end. Parts are segmented per R15 limb (one collection per bone) and bone-parented to
# an armature, so poses are stored as keyframes and the parts map 1:1 onto the Roblox Motor6D rig.
# Units: 1 Blender unit = 1 Roblox stud. Character faces -Y; its right side is -X.

import bpy
import bmesh
import math
import os
import sys
from mathutils import Euler, Matrix, Vector

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT_DIR = os.path.abspath(ARGS[0] if ARGS else os.getcwd())
MODE = ARGS[1] if len(ARGS) > 1 else "preview"
os.makedirs(OUT_DIR, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))
rad = math.radians

# ------------------------------------------------------------------ skeleton (≈4 studs tall)
SH_X, SH_Z, ELB_Z, WR_Z = 0.80, 3.08, 2.46, 1.80
HIP_X, HIP_Z, KNEE_Z, ANK_Z = 0.27, 1.88, 1.06, 0.20
ROOT_Z, WAIST_Z, NECK_Z = 1.95, 2.20, 3.30

BONES = {  # name: (head, tail, parent)
    "LowerTorso": ((0, 0, ROOT_Z), (0, 0, WAIST_Z), None),
    "UpperTorso": ((0, 0, WAIST_Z), (0, 0, NECK_Z), "LowerTorso"),
    "Head": ((0, 0, NECK_Z), (0, 0, 3.85), "UpperTorso"),
}
for side, sx in (("Right", -1), ("Left", 1)):
    BONES.update({
        side + "UpperArm": ((sx * SH_X, 0, SH_Z), (sx * SH_X, 0, ELB_Z), "UpperTorso"),
        side + "LowerArm": ((sx * SH_X, 0, ELB_Z), (sx * SH_X, 0, WR_Z), side + "UpperArm"),
        side + "Hand": ((sx * SH_X, 0, WR_Z), (sx * SH_X, 0, 1.32), side + "LowerArm"),
        side + "UpperLeg": ((sx * HIP_X, 0, HIP_Z), (sx * HIP_X, 0, KNEE_Z), "LowerTorso"),
        side + "LowerLeg": ((sx * HIP_X, 0, KNEE_Z), (sx * HIP_X, 0, ANK_Z), side + "UpperLeg"),
        side + "Foot": ((sx * HIP_X, 0, ANK_Z), (sx * HIP_X, -0.25, ANK_Z), side + "LowerLeg"),
    })


def joint(bone):
    return Vector(BONES[bone][0])


# ------------------------------------------------------------------ materials
def srgb(r, g, b):
    return tuple(((c / 255) ** 2.2) for c in (r, g, b)) + (1.0,)


def node(nt, kind, loc, **props):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in props.items():
        setattr(n, k, v)
    return n


def ramp(nt, loc, stops):
    r = node(nt, "ShaderNodeValToRGB", loc)
    els = r.color_ramp.elements
    while len(els) < len(stops):
        els.new(0.5)
    for el, (pos, col) in zip(els, stops):
        el.position = pos
        el.color = col if len(col) == 4 else (col[0], col[1], col[2], 1.0)
    return r


def math_node(nt, op, loc, a=None, b=None):
    m = node(nt, "ShaderNodeMath", loc, operation=op)
    if a is not None:
        m.inputs[0].default_value = a
    if b is not None:
        m.inputs[1].default_value = b
    return m


def mix_rgb(nt, loc, blend="MIX"):
    m = node(nt, "ShaderNodeMix", loc, data_type="RGBA", blend_type=blend)
    return m  # inputs: 0 factor, 6 A, 7 B ; output 2


def stone_material(name, dark, base, light, crack_scale=2.2, crack_amount=0.85):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    L = nt.links.new
    out = node(nt, "ShaderNodeOutputMaterial", (1600, 0))
    bsdf = node(nt, "ShaderNodeBsdfPrincipled", (1300, 0))
    bsdf.inputs["Roughness"].default_value = 0.86
    L(bsdf.outputs[0], out.inputs[0])

    tc = node(nt, "ShaderNodeTexCoord", (-1400, 0))
    mp = node(nt, "ShaderNodeMapping", (-1200, 0))
    L(tc.outputs["Object"], mp.inputs["Vector"])

    # domain-warped coordinates so cracks wander like real fractures
    warp = node(nt, "ShaderNodeTexNoise", (-1000, 300))
    warp.inputs["Scale"].default_value = 2.5
    warp.inputs["Detail"].default_value = 3.0
    L(mp.outputs[0], warp.inputs["Vector"])
    wv = node(nt, "ShaderNodeVectorMath", (-800, 200), operation="MULTIPLY_ADD")
    wv.inputs[1].default_value = (0.35, 0.35, 0.35)
    L(warp.outputs["Color"], wv.inputs[0])
    L(mp.outputs[0], wv.inputs[2])

    crack1 = node(nt, "ShaderNodeTexVoronoi", (-600, 300), feature="DISTANCE_TO_EDGE")
    crack1.inputs["Scale"].default_value = crack_scale
    L(wv.outputs[0], crack1.inputs["Vector"])
    c1 = ramp(nt, (-400, 300), [(0.0, (1, 1, 1)), (0.022, (0, 0, 0))])
    L(crack1.outputs["Distance"], c1.inputs[0])

    crack2 = node(nt, "ShaderNodeTexVoronoi", (-600, 50), feature="DISTANCE_TO_EDGE")
    crack2.inputs["Scale"].default_value = crack_scale * 3.4
    L(wv.outputs[0], crack2.inputs["Vector"])
    c2 = ramp(nt, (-400, 50), [(0.0, (0.55, 0.55, 0.55)), (0.012, (0, 0, 0))])
    L(crack2.outputs["Distance"], c2.inputs[0])

    # cracks only appear in patches, so the stone isn't uniformly shattered
    patch = node(nt, "ShaderNodeTexNoise", (-600, 550))
    patch.inputs["Scale"].default_value = 1.6
    L(mp.outputs[0], patch.inputs["Vector"])
    pr = ramp(nt, (-400, 550), [(0.45, (0, 0, 0)), (0.62, (1, 1, 1))])
    L(patch.outputs["Fac"], pr.inputs[0])

    cmax = math_node(nt, "MAXIMUM", (-200, 200))
    L(c1.outputs[0], cmax.inputs[0])
    L(c2.outputs[0], cmax.inputs[1])
    crack = math_node(nt, "MULTIPLY", (0, 200))
    L(cmax.outputs[0], crack.inputs[0])
    patch_floor = math_node(nt, "MAXIMUM", (-200, 450), b=0.25)
    L(pr.outputs[0], patch_floor.inputs[0])
    L(patch_floor.outputs[0], crack.inputs[1])

    # colour: layered noise through a dark/base/light ramp + speckle
    var = node(nt, "ShaderNodeTexNoise", (-600, -250))
    var.inputs["Scale"].default_value = 4.0
    var.inputs["Detail"].default_value = 10.0
    var.inputs["Roughness"].default_value = 0.62
    L(mp.outputs[0], var.inputs["Vector"])
    vr = ramp(nt, (-400, -250), [(0.30, dark), (0.52, base), (0.72, light)])
    L(var.outputs["Fac"], vr.inputs[0])

    speck = node(nt, "ShaderNodeTexNoise", (-600, -500))
    speck.inputs["Scale"].default_value = 60.0
    speck.inputs["Detail"].default_value = 2.0
    L(mp.outputs[0], speck.inputs["Vector"])
    sr = ramp(nt, (-400, -500), [(0.62, (0, 0, 0)), (0.75, (1, 1, 1))])
    L(speck.outputs["Fac"], sr.inputs[0])
    sm = mix_rgb(nt, (-150, -350), "MULTIPLY")
    sm.inputs[0].default_value = 0.0
    L(sr.outputs[0], sm.inputs[0])
    L(vr.outputs[0], sm.inputs[6])
    sm.inputs[7].default_value = (0.55, 0.5, 0.45, 1)

    cm = mix_rgb(nt, (150, 0))
    fac = math_node(nt, "MULTIPLY", (0, 50), b=crack_amount)
    L(crack.outputs[0], fac.inputs[0])
    L(fac.outputs[0], cm.inputs[0])
    L(sm.outputs[2], cm.inputs[6])
    cm.inputs[7].default_value = (0.025, 0.016, 0.01, 1)

    # stone dust settles in crevices (ambient occlusion mask)
    ao = node(nt, "ShaderNodeAmbientOcclusion", (150, -300))
    ao.inputs["Distance"].default_value = 0.12
    inv = math_node(nt, "SUBTRACT", (350, -300), a=1.0)
    L(ao.outputs["AO"], inv.inputs[1])
    dust_fac = math_node(nt, "MULTIPLY", (520, -300), b=0.75)
    L(inv.outputs[0], dust_fac.inputs[0])
    dm = mix_rgb(nt, (700, 0))
    L(dust_fac.outputs[0], dm.inputs[0])
    L(cm.outputs[2], dm.inputs[6])
    dm.inputs[7].default_value = srgb(186, 160, 124)
    L(dm.outputs[2], bsdf.inputs["Base Color"])

    # bump: fine grain + broad variation - cracks
    grain = node(nt, "ShaderNodeTexNoise", (-600, -750))
    grain.inputs["Scale"].default_value = 22.0
    grain.inputs["Detail"].default_value = 8.0
    grain.inputs["Roughness"].default_value = 0.7
    L(mp.outputs[0], grain.inputs["Vector"])
    h1 = math_node(nt, "MULTIPLY_ADD", (400, -600))
    L(grain.outputs["Fac"], h1.inputs[0])
    h1.inputs[1].default_value = 0.5
    L(var.outputs["Fac"], h1.inputs[2])
    h2 = math_node(nt, "SUBTRACT", (600, -600))
    L(h1.outputs[0], h2.inputs[0])
    L(crack.outputs[0], h2.inputs[1])
    bump = node(nt, "ShaderNodeBump", (1000, -400))
    bump.inputs["Strength"].default_value = 0.55
    bump.inputs["Distance"].default_value = 0.012
    L(h2.outputs[0], bump.inputs["Height"])
    L(bump.outputs[0], bsdf.inputs["Normal"])
    return mat


def gold_material():
    mat = bpy.data.materials.new("Gold")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (1.0, 0.66, 0.24, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    L = nt.links.new
    tc = node(nt, "ShaderNodeTexCoord", (-900, 0))
    wear = node(nt, "ShaderNodeTexNoise", (-700, 0))
    wear.inputs["Scale"].default_value = 18.0
    wear.inputs["Detail"].default_value = 6.0
    L(tc.outputs["Object"], wear.inputs["Vector"])
    rr = ramp(nt, (-450, 100), [(0.35, (0.18, 0.18, 0.18)), (0.7, (0.42, 0.42, 0.42))])
    L(wear.outputs["Fac"], rr.inputs[0])
    L(rr.outputs[0], bsdf.inputs["Roughness"])
    bump = node(nt, "ShaderNodeBump", (-200, -200))
    bump.inputs["Strength"].default_value = 0.15
    L(wear.outputs["Fac"], bump.inputs["Height"])
    L(bump.outputs[0], bsdf.inputs["Normal"])
    return mat


def emissive_material(name, color, strength):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Emission Color"].default_value = color
    bsdf.inputs["Emission Strength"].default_value = strength
    return mat


MAT = {
    "sand": stone_material("Sandstone", srgb(146, 96, 52), srgb(190, 136, 82), srgb(214, 168, 112)),
    "dark": stone_material("DarkStone", srgb(60, 38, 24), srgb(92, 60, 38), srgb(122, 84, 56), 2.6, 0.7),
    "beige": stone_material("BeigeStone", srgb(196, 172, 140), srgb(226, 206, 176), srgb(242, 230, 208), 1.9, 0.6),
    "gold": gold_material(),
    "eye": emissive_material("EyeGlow", (1.0, 0.78, 0.12, 1), 40.0),
}

# displacement textures for chips / weathering (geometry, not just shading)
TEX_CHIPS = bpy.data.textures.new("StoneChips", "VORONOI")
TEX_CHIPS.noise_scale = 0.11
TEX_CHIPS.distance_metric = "DISTANCE"
TEX_CHIPS.color_mode = "INTENSITY"
TEX_ROCK = bpy.data.textures.new("RockFacets", "VORONOI")
TEX_ROCK.noise_scale = 0.28
TEX_ROCK.distance_metric = "DISTANCE"
TEX_ROCK.color_mode = "INTENSITY"
TEX_WEATHER = bpy.data.textures.new("StoneWeathering", "CLOUDS")
TEX_WEATHER.noise_scale = 0.09
TEX_WEATHER.noise_depth = 3

# ------------------------------------------------------------------ mesh construction
PARTS = []  # (obj, bone)
SYM = bpy.data.objects.new("SymmetryCenter", None)
scene.collection.objects.link(SYM)
COLLECTIONS = {}


def collection_for(bone):
    if bone not in COLLECTIONS:
        c = bpy.data.collections.new(bone)
        scene.collection.children.link(c)
        COLLECTIONS[bone] = c
    return COLLECTIONS[bone]


def S(c, u, v, a, b, n=2.5, a2=None, b2=None, shape=None):
    u = Vector(u).normalized()
    v = Vector(v).normalized()
    return {"c": Vector(c), "u": u, "v": v, "a": a, "a2": a if a2 is None else a2,
            "b": b, "b2": b if b2 is None else b2, "n": n, "shape": shape}


def ring_points(s, N, scale=1.0):
    c, u, v = s["c"], s["u"], s["v"]
    pts = []
    if s["shape"]:
        for x, y in s["shape"]:
            pts.append(c + u * (x * s["a"] * scale) + v * (y * s["b"] * scale))
        return pts
    e = 2.0 / s["n"]
    for k in range(N):
        t = 2 * math.pi * k / N
        ct, st = math.cos(t), math.sin(t)
        px = math.copysign(abs(ct) ** e, ct)
        py = math.copysign(abs(st) ** e, st)
        a = s["a"] if px >= 0 else s["a2"]
        b = s["b"] if py >= 0 else s["b2"]
        pts.append(c + u * (px * a * scale) + v * (py * b * scale))
    return pts


def finish(obj, mat, kind, bone, mirror):
    obj.data.materials.append(MAT[mat])
    m = obj.modifiers
    if mirror:
        mm = m.new("Mirror", "MIRROR")
        mm.mirror_object = SYM
        mm.use_clip = False
    if kind == "plate":
        bv = m.new("Bevel", "BEVEL")
        bv.width = 0.007
        bv.segments = 2
        bv.limit_method = "ANGLE"
        bv.angle_limit = rad(35)
    sub = m.new("Subdivision", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 2
    if kind in ("plate", "core"):
        if kind == "plate":
            d = m.new("Chips", "DISPLACE")
            d.texture = TEX_CHIPS
            d.strength = 0.008
            d.mid_level = 0.6
        w = m.new("Weathering", "DISPLACE")
        w.texture = TEX_WEATHER
        w.strength = 0.006
    collection_for(bone).objects.link(obj)
    PARTS.append((obj, bone))
    return obj


def loft(name, secs, mat, kind, bone, N=32, cap=(0.02, 0.02), inner=(0.55, 0.55), xform=None, mirror=False):
    origin = joint(bone)
    tf = xform or (lambda p: p)
    bm = bmesh.new()
    rings_world = [[tf(p) for p in ring_points(s, N)] for s in secs]
    n = len(rings_world[0])
    rings = [[bm.verts.new(p - origin) for p in r] for r in rings_world]
    for i in range(len(rings) - 1):
        r0, r1 = rings[i], rings[i + 1]
        for k in range(n):
            bm.faces.new((r0[k], r0[(k + 1) % n], r1[(k + 1) % n], r1[k]))

    def cap_end(idx, nbr, depth, inner_scale):
        s = secs[idx]
        axis = (s["c"] - secs[nbr]["c"]).normalized()
        ring = rings[idx]
        if inner_scale:
            ip = [tf(s["c"] + axis * depth * 0.7 + (p - s["c"]) * inner_scale) for p in ring_points(s, N)]
            iv = [bm.verts.new(p - origin) for p in ip]
            for k in range(n):
                bm.faces.new((ring[k], ring[(k + 1) % n], iv[(k + 1) % n], iv[k]))
            ring = iv
        cv = bm.verts.new(tf(s["c"] + axis * depth) - origin)
        for k in range(n):
            bm.faces.new((ring[k], ring[(k + 1) % n], cv))

    cap_end(0, 1, cap[0], inner[0])
    cap_end(len(secs) - 1, len(secs) - 2, cap[1], inner[1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name, me)
    obj.location = origin
    return finish(obj, mat, kind, bone, mirror)


def vloft(name, rows, mat, kind, bone, cx=0.0, cy=0.0, **kw):
    """Vertical loft. rows: (z, half_width, half_depth_front, half_depth_back, exponent)."""
    secs = [S((cx, cy, z), X, Y, rx, ryb, n, b2=ryf) for z, rx, ryf, ryb, n in rows]
    return loft(name, secs, mat, kind, bone, **kw)


def slab(name, center, w, h, t, mat, bone, rot=(0, 0, 0), n=4.0, taper=0.9, curve=0.0, trap=0.0,
         kind="plate", mirror=False, N=36):
    """Carved stone plate: pillow-bevelled slab whose front faces -Y before rotation."""
    R = Euler((rad(rot[0]), rad(rot[1]), rad(rot[2])), "XYZ").to_matrix()
    C = Vector(center)

    def xf(p):
        q = Vector((p.x * (1 + trap * p.z / max(h, 1e-6)), p.y + curve * p.x * p.x, p.z))
        return C + R @ q

    secs = []
    for y, sc in ((t / 2, 0.9), (t * 0.28, 1.0), (-t * 0.22, 1.0), (-t / 2, taper)):
        secs.append(S((0, y, 0), X, Z, w / 2 * sc, h / 2 * sc, n))
    return loft(name, secs, mat, kind, bone, N=N, cap=(0.0, t * 0.12), inner=(0.6, 0.62), xform=xf,
                mirror=mirror)


def tube(name, pts, radii, mat, bone, side=X, n=2.6, kind="plate", mirror=False, N=24):
    pts = [Vector(p) for p in pts]
    secs = []
    for i, p in enumerate(pts):
        a = pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]
        axis = a.normalized()
        u = (Vector(side) - axis * axis.dot(Vector(side))).normalized()
        v = axis.cross(u)
        ra, rb = radii[i]
        secs.append(S(p, u, v, ra, rb, n))
    r0, r1 = radii[0], radii[-1]
    return loft(name, secs, mat, kind, bone, N=N, cap=(min(r0) * 0.7, min(r1) * 0.8), inner=(0.6, 0.6),
                mirror=mirror)


def ellipsoid(name, center, r, mat, bone, rot=(0, 0, 0), n=2.0, kind="plate", mirror=False, rings=10, N=28):
    R = Euler((rad(rot[0]), rad(rot[1]), rad(rot[2])), "XYZ").to_matrix()
    C = Vector(center)
    secs = []
    for j in range(1, rings):
        phi = math.pi * j / rings
        s = math.sin(phi)
        secs.append(S((0, 0, -math.cos(phi) * r[2]), X, Y, r[0] * s, r[1] * s, n))
    d = r[2] * (1 - math.cos(math.pi / rings))
    return loft(name, secs, mat, kind, bone, N=N, cap=(d, d), inner=(None, None),
                xform=lambda p: C + R @ p, mirror=mirror)


def sweep(name, path, closed, w, h, mat, bone, up=Z, prof=10, kind="gold", mirror=False):
    origin = joint(bone)
    path = [Vector(p) for p in path]
    n = len(path)
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(path):
        if closed:
            t = path[(i + 1) % n] - path[i - 1]
        else:
            t = path[min(i + 1, n - 1)] - path[max(i - 1, 0)]
        t.normalize()
        side = t.cross(Vector(up)).normalized()
        upv = side.cross(t).normalized()
        rings.append([bm.verts.new(p + side * (math.cos(2 * math.pi * j / prof) * w)
                                   + upv * (math.sin(2 * math.pi * j / prof) * h) - origin) for j in range(prof)])
    segs = n if closed else n - 1
    for i in range(segs):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for j in range(prof):
            bm.faces.new((r0[j], r0[(j + 1) % prof], r1[(j + 1) % prof], r1[j]))
    if not closed:
        for r, p in ((rings[0], path[0]), (rings[-1], path[-1])):
            cv = bm.verts.new(p - origin)
            for j in range(prof):
                bm.faces.new((r[j], r[(j + 1) % prof], cv))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new(name, me)
    obj.location = origin
    return finish(obj, mat, kind, bone, mirror)


def band(name, center, a, b, n, w, h, bone, N=64, mat="gold", mirror=False):
    c = Vector(center)
    e = 2.0 / n
    path = []
    for k in range(N):
        t = 2 * math.pi * k / N
        ct, st = math.cos(t), math.sin(t)
        path.append(c + Vector((math.copysign(abs(ct) ** e, ct) * a, math.copysign(abs(st) ** e, st) * b, 0)))
    return sweep(name, path, True, w, h, mat, bone, mirror=mirror)


def heart_shape(N=72):
    pts = []
    for k in range(N):
        t = 2 * math.pi * k / N
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x / 17.0, (y + 2.5) / 17.0))
    return pts


def heart(name, center, size, t, bone, rot=(0, 0, 0)):
    R = Euler((rad(rot[0]), rad(rot[1]), rad(rot[2])), "XYZ").to_matrix()
    C = Vector(center)
    shp = heart_shape()
    secs = [S((0, y, 0), X, Z, size, size, shape=shp) for y in (t / 2, t / 4, -t / 4, -t / 2)]
    for s, sc in zip(secs, (0.9, 1.0, 1.0, 0.84)):
        s["a"] *= sc
        s["b"] *= sc
    return loft(name, secs, "gold", "gold", bone, N=len(shp), cap=(0.0, t * 0.15), inner=(0.6, 0.6),
                xform=lambda p: C + R @ p)


class Body:
    """A limb/torso surface: rows (z, half_width, half_depth_front, half_depth_back, exponent) around (cx, cy)."""

    def __init__(self, rows, cx=0.0, cy=0.0):
        self.rows = sorted(rows)
        self.cx, self.cy = cx, cy

    def at(self, z):
        rows = self.rows
        if z <= rows[0][0]:
            return rows[0][1:]
        for (z0, *a), (z1, *b) in zip(rows, rows[1:]):
            if z <= z1:
                f = (z - z0) / (z1 - z0)
                return tuple(x + (y - x) * f for x, y in zip(a, b))
        return rows[-1][1:]

    def point(self, z, t_deg, off):
        rx, ryf, ryb, n = self.at(z)
        t = rad(t_deg)
        ct, st = math.cos(t), math.sin(t)
        e = 2.0 / n
        px = math.copysign(abs(ct) ** e, ct)
        py = math.copysign(abs(st) ** e, st)
        ry = ryb if py >= 0 else ryf
        return Vector((self.cx + px * (rx + off), self.cy + py * (ry + off), z))


def shell(name, body, z0, z1, t0, t1, mat, bone, off=0.012, thick=0.05, bulge=0.0, flare=(0.0, 0.0),
          R=10, M=16, mirror=False, kind="plate", edge=(0.0, 0.0), rock=0.0):
    """Armour plate that wraps a Body surface between heights z0..z1 and angles t0..t1 (degrees;
    -90 = front, -180 = character's right / -X, -270 = back). bulge pushes the middle out like muscle;
    flare offsets the bottom/top edge so plates overlap like layered armour."""
    origin = joint(bone)
    bm = bmesh.new()
    O, I = [], []
    for j in range(R + 1):
        zz = j / R
        ro, ri = [], []
        for i in range(M + 1):
            ti = i / M
            lo, hi = z0 + edge[0] * ti * ti, z1 + edge[1] * ti * ti
            z = lo + (hi - lo) * zz
            t = t0 + (t1 - t0) * ti
            o = off + bulge * math.sin(math.pi * zz) * math.sin(math.pi * ti) + flare[0] * (1 - zz) + flare[1] * zz
            ro.append(bm.verts.new(body.point(z, t, o) - origin))
            ri.append(bm.verts.new(body.point(z, t, o - thick) - origin))
        O.append(ro)
        I.append(ri)
    for j in range(R):
        for i in range(M):
            bm.faces.new((O[j][i], O[j][i + 1], O[j + 1][i + 1], O[j + 1][i]))
            bm.faces.new((I[j][i], I[j + 1][i], I[j + 1][i + 1], I[j][i + 1]))
    for i in range(M):
        bm.faces.new((O[0][i], I[0][i], I[0][i + 1], O[0][i + 1]))
        bm.faces.new((O[R][i], O[R][i + 1], I[R][i + 1], I[R][i]))
    for j in range(R):
        bm.faces.new((O[j][0], O[j + 1][0], I[j + 1][0], I[j][0]))
        bm.faces.new((O[j][M], I[j][M], I[j + 1][M], O[j + 1][M]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name, me)
    obj.location = origin
    return rockify(finish(obj, mat, kind, bone, mirror), rock)


def rockify(obj, strength):
    """Extra large-scale faceting so a part reads as rough-hewn rock rather than smooth stone."""
    if strength > 0:
        d = obj.modifiers.new("Rock", "DISPLACE")
        d.texture = TEX_ROCK
        d.strength = strength
        d.mid_level = 0.55
    return obj


def trim(name, body, z, t0, t1, off, bone, w=0.016, h=0.016, mirror=False, steps=24):
    """Gold trim that follows a Body surface along a horizontal line."""
    path = [body.point(z, t0 + (t1 - t0) * k / steps, off) for k in range(steps + 1)]
    return sweep(name, path, False, w, h, "gold", bone, up=Z, mirror=mirror)


def core(name, body, mat, bone, **kw):
    return vloft(name, body.rows, mat, "core", bone, cx=body.cx, cy=body.cy, **kw)


# ================================================================== TORSO
B = "UpperTorso"
TORSO = Body([
    (2.18, 0.29, 0.19, 0.19, 2.6),
    (2.32, 0.30, 0.20, 0.20, 2.6),
    (2.50, 0.39, 0.23, 0.22, 2.6),
    (2.68, 0.52, 0.27, 0.25, 2.8),
    (2.86, 0.585, 0.29, 0.27, 3.0),
    (3.02, 0.60, 0.27, 0.27, 3.0),
    (3.14, 0.52, 0.22, 0.24, 3.0),
    (3.25, 0.30, 0.16, 0.18, 2.5),
])
core("Torso_Core", TORSO, "dark", B, cap=(0.02, 0.04))
# carved pectorals, wrapping the chest
shell("Pec", TORSO, 2.72, 3.07, -95, -152, "beige", B, off=0.006, thick=0.065, bulge=0.07, edge=(0.13, 0.0),
      mirror=True)
trim("CollarTrim", TORSO, 3.075, -93, -156, 0.035, B, mirror=True)
# layered abdominals
for i, (z0, z1) in enumerate(((2.585, 2.70), (2.455, 2.57), (2.325, 2.44))):
    shell("Abs%d" % i, TORSO, z0, z1, -94, -124, "beige", B, off=0.004, thick=0.05, bulge=0.03, R=6, M=8,
          mirror=True)
shell("Oblique", TORSO, 2.27, 2.71, -127, -166, "sand", B, off=0.006, thick=0.05, bulge=0.025,
      flare=(0.0, 0.01), edge=(0.0, 0.12), mirror=True)
shell("SideRib", TORSO, 2.58, 2.98, -169, -214, "dark", B, off=0.008, thick=0.05, bulge=0.02, mirror=True)
shell("Lat", TORSO, 2.40, 3.01, -217, -263, "sand", B, off=0.008, thick=0.055, bulge=0.04, mirror=True)
shell("Shoulder", TORSO, 3.03, 3.21, -97, -262, "sand", B, off=0.012, thick=0.05, bulge=0.02,
      flare=(0.012, 0.0), M=24, mirror=True)
for i in range(6):
    z1 = 3.03 - i * 0.12
    shell("Spine%d" % i, TORSO, z1 - 0.1, z1, -258, -282, "dark" if i % 2 else "sand", B, off=0.03,
          thick=0.06, bulge=0.025, R=6, M=8)
# oversized rocky pauldrons ride on the torso so they stay put when the arm swings
for side_name, sx in (("R", -1),):
    px = sx * (SH_X + 0.05)
    vloft("Pauldron", [
        (3.39, 0.08, 0.08, 0.08, 2.5),
        (3.36, 0.20, 0.19, 0.19, 2.8),
        (3.28, 0.29, 0.26, 0.26, 3.2),
        (3.15, 0.335, 0.295, 0.295, 3.4),
        (3.03, 0.335, 0.295, 0.295, 3.4),
        (2.99, 0.315, 0.275, 0.275, 3.2),
    ], "sand", "plate", B, cx=px, cap=(0.02, 0.0), mirror=True)
    rockify(PARTS[-1][0], 0.035)
    vloft("PauldronTier", [
        (3.01, 0.305, 0.275, 0.275, 3.4),
        (2.98, 0.32, 0.285, 0.285, 3.4),
        (2.88, 0.30, 0.265, 0.265, 3.2),
        (2.83, 0.27, 0.24, 0.24, 3.0),
    ], "dark", "plate", B, cx=px - sx * -0.02, mirror=True)
    rockify(PARTS[-1][0], 0.025)
    for i, dy in enumerate((-0.15, 0.15)):
        slab("PauldronRidge%d" % i, (px - 0.08, dy, 3.32), 0.22, 0.1, 0.09, "sand", B,
             rot=(0, 0, -90 + (28 if dy < 0 else -28)), n=3.4, curve=1.5, mirror=True)
    slab("PauldronCrest", (px - 0.06, 0, 3.37), 0.12, 0.3, 0.07, "dark", B, rot=(90, 0, 90), n=3.4, mirror=True)
    band("ShoulderRing", (px, 0, 3.02), 0.35, 0.307, 3.4, 0.024, 0.03, B, mirror=True)

# ================================================================== PELVIS / BELT
B = "LowerTorso"
PELVIS = Body([
    (1.70, 0.31, 0.20, 0.22, 2.8),
    (1.80, 0.36, 0.23, 0.25, 3.0),
    (1.95, 0.37, 0.23, 0.24, 3.0),
    (2.10, 0.33, 0.21, 0.21, 2.8),
    (2.24, 0.29, 0.19, 0.19, 2.6),
])
core("Pelvis_Core", PELVIS, "dark", B)
vloft("Belt", [
    (2.05, 0.345, 0.228, 0.228, 3.0),
    (2.07, 0.36, 0.243, 0.243, 3.0),
    (2.18, 0.35, 0.236, 0.236, 3.0),
    (2.20, 0.335, 0.222, 0.222, 3.0),
], "gold", "gold", B)
heart("HeartEmblem", (0, -0.262, 2.13), 0.085, 0.05, B)
shell("TassetFront", PELVIS, 1.66, 2.04, -80, -100, "dark", B, off=0.02, thick=0.05, flare=(0.05, 0.0), R=8, M=6)
shell("Tasset", PELVIS, 1.64, 2.04, -103, -150, "sand", B, off=0.02, thick=0.05, flare=(0.07, 0.0), mirror=True)
shell("TassetSide", PELVIS, 1.62, 2.04, -153, -208, "sand", B, off=0.02, thick=0.05, flare=(0.08, 0.0),
      mirror=True)
shell("TassetBack", PELVIS, 1.66, 2.04, -211, -268, "dark", B, off=0.02, thick=0.05, flare=(0.06, 0.0),
      mirror=True)

# ================================================================== HEAD
B = "Head"
vloft("Neck", [(3.16, 0.14, 0.13, 0.13, 2.3), (3.32, 0.13, 0.12, 0.13, 2.3), (3.46, 0.13, 0.12, 0.13, 2.3)],
      "dark", "core", B)
HEAD = Body([
    (3.37, 0.11, 0.14, 0.11, 3.0),
    (3.43, 0.165, 0.185, 0.145, 3.0),
    (3.53, 0.19, 0.20, 0.17, 3.2),
    (3.64, 0.20, 0.20, 0.19, 3.2),
    (3.75, 0.20, 0.19, 0.19, 3.2),
    (3.84, 0.175, 0.165, 0.165, 3.0),
    (3.90, 0.13, 0.12, 0.12, 2.8),
])
helmet = vloft("Helmet", HEAD.rows, "sand", "plate", B, cap=(0.01, 0.02))
cutter = ellipsoid("EyeSocketCutter", (-0.085, -0.212, 3.645), (0.06, 0.072, 0.033), "dark", B, rot=(0, 15, 0),
                   kind="cutter", mirror=True)
cutter.hide_render = True
cutter.display_type = "WIRE"
cutter.modifiers.remove(cutter.modifiers["Subdivision"])
boolean = helmet.modifiers.new("EyeSockets", "BOOLEAN")
boolean.operation = "DIFFERENCE"
boolean.object = cutter
boolean.solver = "EXACT"
helmet.modifiers.move(len(helmet.modifiers) - 1, 2)  # after Bevel+Subdivision, before Displace
ellipsoid("Eye", (-0.085, -0.163, 3.645), (0.038, 0.024, 0.018), "eye", B, rot=(0, 15, 0), kind="eye",
          mirror=True)
slab("BrowRidge", (0, -0.208, 3.728), 0.4, 0.06, 0.085, "sand", B, rot=(22, 0, 0), n=3.6, curve=1.5)
shell("FacePlate", HEAD, 3.40, 3.58, -72, -108, "sand", B, off=0.008, thick=0.045, bulge=0.012, R=6, M=8)
shell("Jaw", HEAD, 3.39, 3.56, -110, -160, "sand", B, off=0.012, thick=0.045, flare=(0.012, 0), mirror=True)
shell("Cheek", HEAD, 3.52, 3.66, -150, -200, "dark", B, off=0.014, thick=0.045, flare=(0.0, 0.01), mirror=True)
shell("Temple", HEAD, 3.66, 3.80, -165, -215, "sand", B, off=0.012, thick=0.045, mirror=True)
tube("Horn", [(-0.17, 0.03, 3.77), (-0.215, 0.09, 3.845), (-0.235, 0.16, 3.9), (-0.225, 0.235, 3.93)],
     [(0.052, 0.044), (0.038, 0.031), (0.023, 0.02), (0.009, 0.008)], "dark", B, side=X, n=3.0, mirror=True)
tube("Crest", [(0, -0.14, 3.86), (0, -0.04, 3.91), (0, 0.07, 3.915), (0, 0.16, 3.87)],
     [(0.024, 0.033), (0.033, 0.044), (0.033, 0.044), (0.022, 0.028)], "sand", B, side=X, n=3.2)
band("Circlet", (0, 0.0, 3.785), 0.2, 0.19, 3.2, 0.012, 0.012, B)

# ================================================================== RIGHT ARM (left is mirrored)
ax = -SH_X
B = "RightUpperArm"
UARM = Body([
    (3.18, 0.15, 0.15, 0.15, 2.3),
    (3.02, 0.17, 0.17, 0.16, 2.4),
    (2.85, 0.165, 0.185, 0.16, 2.4),
    (2.65, 0.145, 0.15, 0.14, 2.3),
    (2.50, 0.13, 0.13, 0.13, 2.3),
    (2.42, 0.12, 0.12, 0.12, 2.3),
], cx=ax)
core("UpperArm_Core", UARM, "dark", B)
shell("Bicep", UARM, 2.56, 2.96, -55, -125, "sand", B, off=0.006, thick=0.05, bulge=0.04)
shell("Deltoid", UARM, 2.52, 3.0, -130, -230, "sand", B, off=0.01, thick=0.05, bulge=0.025, flare=(0.0, 0.015))
shell("Tricep", UARM, 2.55, 2.98, -235, -305, "sand", B, off=0.008, thick=0.05, bulge=0.035)
shell("InnerArm", UARM, 2.6, 2.9, -310, -405, "dark", B, off=0.004, thick=0.04)

B = "RightLowerArm"
FARM = Body([
    (2.52, 0.13, 0.13, 0.13, 2.4),
    (2.40, 0.15, 0.155, 0.155, 2.6),
    (2.22, 0.172, 0.19, 0.19, 3.0),
    (2.02, 0.185, 0.235, 0.235, 3.2),
    (1.88, 0.195, 0.262, 0.262, 3.4),
    (1.79, 0.19, 0.265, 0.265, 3.4),
], cx=ax)
core("Forearm_Core", FARM, "dark", B)
rockify(ellipsoid("ElbowCap", (ax, 0.12, 2.47), (0.11, 0.085, 0.11), "sand", B, n=2.6), 0.02)
shell("GauntletFront", FARM, 1.86, 2.36, -52, -128, "sand", B, off=0.01, thick=0.055, bulge=0.02, flare=(0.015, 0))
shell("GauntletOuter", FARM, 1.86, 2.40, -133, -227, "sand", B, off=0.012, thick=0.055, bulge=0.025,
      flare=(0.015, 0))
shell("GauntletBack", FARM, 1.86, 2.36, -232, -308, "sand", B, off=0.01, thick=0.055, bulge=0.02, flare=(0.015, 0))
shell("GauntletInner", FARM, 1.86, 2.30, -313, -407, "dark", B, off=0.008, thick=0.05, flare=(0.012, 0))
band("WristRing", (ax, 0, 1.84), 0.215, 0.282, 3.4, 0.026, 0.036, B)
band("ForearmRing", (ax, 0, 2.39), 0.17, 0.172, 2.8, 0.018, 0.022, B)

# ------------------------------------------------------------------ fist (palm faces +X / inward)
B = "RightHand"
w = joint(B)


def H(x, y, z):
    return (w.x + x, w.y + y, w.z + z)


vloft("Palm", [
    (w.z + 0.02, 0.15, 0.22, 0.22, 3.0),
    (w.z - 0.05, 0.165, 0.26, 0.26, 3.2),
    (w.z - 0.20, 0.175, 0.29, 0.29, 3.4),
    (w.z - 0.30, 0.165, 0.29, 0.29, 3.4),
], "sand", "plate", B, cx=w.x)
slab("HandBack", H(-0.165, 0, -0.15), 0.52, 0.27, 0.07, "sand", B, rot=(0, 0, -90), n=3.6, curve=0.8, taper=0.92)
for i, L in enumerate((1.0, 1.05, 1.0, 0.86)):
    y = -0.21 + i * 0.14
    pz = -0.30 - 0.17 * L
    tube("Finger%d_Prox" % i, [H(-0.04, y, -0.27), H(-0.04, y, (pz - 0.27) / 2), H(-0.04, y, pz)],
         [(0.078, 0.067), (0.081, 0.069), (0.077, 0.066)], "sand", B, side=X, n=3.4)
    tube("Finger%d_Mid" % i, [H(-0.02, y, pz - 0.005), H(0.08, y, pz + 0.005), H(0.17, y, pz + 0.02)],
         [(0.067, 0.072), (0.067, 0.072), (0.064, 0.068)], "sand", B, side=Y, n=3.4)
    tube("Finger%d_Dist" % i, [H(0.205, y, pz + 0.03), H(0.21, y, pz + 0.1), H(0.2, y, -0.31)],
         [(0.062, 0.06), (0.06, 0.058), (0.052, 0.052)], "sand", B, side=X, n=3.4)
    ellipsoid("Finger%d_PIP" % i, H(-0.035, y, pz), (0.084, 0.073, 0.077), "sand", B, n=2.8)
    ellipsoid("Finger%d_DIP" % i, H(0.19, y, pz + 0.02), (0.072, 0.067, 0.07), "sand", B, n=2.8)
    slab("Knuckle%d" % i, H(-0.118, y, -0.33), 0.112, 0.105, 0.06, "dark", B, rot=(0, 0, -90), n=3.4, taper=0.9)
tube("Thumb_Meta", [H(0.0, -0.21, -0.04), H(0.05, -0.29, -0.15), H(0.09, -0.31, -0.26)],
     [(0.088, 0.082), (0.09, 0.085), (0.082, 0.078)], "sand", B, side=X, n=3.0)
ellipsoid("Thumb_Joint", H(0.1, -0.305, -0.275), (0.082, 0.08, 0.08), "sand", B, n=2.8)
tube("Thumb_Tip", [H(0.12, -0.3, -0.3), H(0.2, -0.24, -0.37), H(0.255, -0.15, -0.385), H(0.27, -0.06, -0.38)],
     [(0.074, 0.072), (0.072, 0.07), (0.066, 0.064), (0.052, 0.052)], "sand", B, side=Z, n=3.0)

# ================================================================== RIGHT LEG
lx = -HIP_X
B = "RightUpperLeg"
THIGH = Body([
    (1.96, 0.21, 0.23, 0.23, 2.4),
    (1.80, 0.235, 0.255, 0.235, 2.5),
    (1.55, 0.22, 0.245, 0.215, 2.5),
    (1.30, 0.178, 0.195, 0.18, 2.4),
    (1.12, 0.148, 0.158, 0.155, 2.3),
    (1.03, 0.14, 0.145, 0.145, 2.3),
], cx=lx)
core("Thigh_Core", THIGH, "dark", B)
shell("Quad", THIGH, 1.18, 1.80, -52, -128, "sand", B, off=0.008, thick=0.055, bulge=0.045, flare=(0, 0.012))
shell("ThighOuter", THIGH, 1.14, 1.84, -132, -226, "sand", B, off=0.01, thick=0.055, bulge=0.03,
      flare=(0, 0.015))
shell("Hamstring", THIGH, 1.18, 1.76, -230, -310, "sand", B, off=0.008, thick=0.05, bulge=0.035)
shell("ThighInner", THIGH, 1.22, 1.66, -314, -406, "dark", B, off=0.005, thick=0.045)

B = "RightLowerLeg"
SHIN = Body([
    (1.10, 0.14, 0.15, 0.15, 2.3),
    (0.95, 0.158, 0.165, 0.195, 2.4),
    (0.70, 0.138, 0.145, 0.165, 2.4),
    (0.45, 0.112, 0.122, 0.122, 2.3),
    (0.28, 0.10, 0.11, 0.11, 2.3),
    (0.19, 0.10, 0.10, 0.10, 2.3),
], cx=lx)
core("Shin_Core", SHIN, "dark", B)
rockify(slab("KneeCap", (lx, -0.155, 1.07), 0.22, 0.21, 0.11, "sand", B, n=3.4, curve=2.0, taper=0.9), 0.02)
shell("ShinGuard", SHIN, 0.36, 0.98, -40, -140, "sand", B, off=0.012, thick=0.055, bulge=0.02, flare=(0, 0.02))
shell("Calf", SHIN, 0.48, 1.0, -215, -325, "sand", B, off=0.01, thick=0.05, bulge=0.04)
shell("ShinOuter", SHIN, 0.42, 0.92, -145, -210, "dark", B, off=0.008, thick=0.045)
band("AnkleRing", (lx, 0, 0.31), 0.135, 0.148, 3.0, 0.022, 0.03, B)

B = "RightFoot"
foot_secs = [S((lx, y, zc), X, Z, a, b, 3.4) for y, a, b, zc in (
    (0.14, 0.10, 0.09, 0.105),
    (0.06, 0.125, 0.135, 0.145),
    (-0.08, 0.135, 0.115, 0.125),
    (-0.22, 0.13, 0.085, 0.095),
    (-0.31, 0.115, 0.062, 0.072),
)]
rockify(loft("Boot", foot_secs, "sand", "plate", B, cap=(0.01, 0.03)), 0.02)
slab("ToeCap", (lx, -0.2, 0.16), 0.24, 0.16, 0.055, "dark", B, rot=(-70, 0, 0), n=3.4, curve=1.5, taper=0.9)

# ------------------------------------------------------------------ mirror limbs to the left side
for obj, bone in list(PARTS):
    if not bone.startswith("Right"):
        continue
    lb = "Left" + bone[5:]
    me = obj.data.copy()
    bm = bmesh.new()
    bm.from_mesh(me)
    for v in bm.verts:
        v.co.x = -(v.co.x + obj.location.x) - joint(lb).x
    bmesh.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    twin = obj.copy()
    twin.data = me
    twin.name = obj.name.replace("Right", "Left") if "Right" in obj.name else obj.name + ".L"
    twin.location = joint(lb)
    collection_for(lb).objects.link(twin)
    PARTS.append((twin, lb))
for obj, bone in PARTS:
    if bone.startswith("Right") and not obj.name.endswith(".R"):
        obj.name = obj.name + ".R"

# ------------------------------------------------------------------ apply symmetry (end of modelling)
bpy.context.view_layer.update()
for obj, bone in PARTS:
    if "Mirror" in obj.modifiers:
        with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
            bpy.ops.object.modifier_apply(modifier="Mirror")
bpy.data.objects.remove(SYM)

# ------------------------------------------------------------------ armature + bone parenting
arm_data = bpy.data.armatures.new("BrickFistRig")
arm = bpy.data.objects.new("BrickFistRig", arm_data)
scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
for name, (h, t, _) in BONES.items():
    eb = arm_data.edit_bones.new(name)
    eb.head, eb.tail = h, t
for name, (_, _, parent) in BONES.items():
    if parent:
        arm_data.edit_bones[name].parent = arm_data.edit_bones[parent]
bpy.ops.object.mode_set(mode="OBJECT")
arm.show_in_front = True

for obj, bone in PARTS:
    world = obj.matrix_world.copy()
    b = arm_data.bones[bone]
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = bone
    obj.matrix_parent_inverse = (arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))).inverted()
    obj.matrix_basis = world

# eye glow spill
for sx in (-1, 1):
    ld = bpy.data.lights.new("EyeLight", "POINT")
    ld.energy = 2.5
    ld.color = (1.0, 0.8, 0.25)
    ld.shadow_soft_size = 0.02
    lo = bpy.data.objects.new("EyeLight", ld)
    collection_for("Head").objects.link(lo)
    b = arm_data.bones["Head"]
    lo.parent = arm
    lo.parent_type = "BONE"
    lo.parent_bone = "Head"
    lo.matrix_parent_inverse = (b.matrix_local @ Matrix.Translation((0, b.length, 0))).inverted()
    lo.location = (sx * 0.075, -0.2, 3.625)


# ------------------------------------------------------------------ poses (world-axis joint rotations, degrees)
def mirror_rot(r):
    return (r[0], -r[1], -r[2])


def sym(spec):
    """Fill Left* entries from Right* ones where not given explicitly."""
    out = dict(spec)
    for k, v in spec.items():
        if k.startswith("Right") and ("Left" + k[5:]) not in spec:
            out["Left" + k[5:]] = mirror_rot(v)
    return out


POSES = {
    "neutral": sym({"RightUpperArm": (0, 13, 0), "RightLowerArm": (-8, 0, 0), "RightUpperLeg": (0, 4, 0),
                    "RightFoot": (0, -4, 0)}),
    "tpose": sym({"RightUpperArm": (0, 90, 0)}),
    "idle": {"_lift": 0.35, "UpperTorso": (-6, 0, 4), "Head": (10, 0, -4),
             "RightUpperArm": (-30, 16, 0), "RightLowerArm": (-75, 0, 10), "RightHand": (0, 0, 20),
             "LeftUpperArm": (8, -18, 0), "LeftLowerArm": (-25, 0, 0),
             "RightUpperLeg": (-22, 4, 0), "RightLowerLeg": (38, 0, 0), "RightFoot": (28, 0, 0),
             "LeftUpperLeg": (4, -4, 0), "LeftLowerLeg": (22, 0, 0), "LeftFoot": (30, 0, 0)},
    "combat": {"_lift": 0.2, "LowerTorso": (0, 0, 18), "UpperTorso": (8, 0, -8), "Head": (4, 0, -10),
               "RightUpperArm": (-30, 34, -18), "RightLowerArm": (-92, 0, 0), "RightHand": (0, 0, 30),
               "LeftUpperArm": (-48, -22, 10), "LeftLowerArm": (-88, 0, 0), "LeftHand": (0, 0, -30),
               "RightUpperLeg": (-28, 10, 0), "RightLowerLeg": (42, 0, 0), "RightFoot": (20, 0, 0),
               "LeftUpperLeg": (22, -10, 0), "LeftLowerLeg": (28, 0, 0), "LeftFoot": (25, 0, 0)},
    "punch": {"_lift": 0.2, "LowerTorso": (6, 0, 12), "UpperTorso": (10, 0, 22), "Head": (0, 0, -24),
              "RightUpperArm": (-88, 0, -24), "RightLowerArm": (-4, 0, 0), "RightHand": (0, 0, 80),
              "LeftUpperArm": (22, -18, 0), "LeftLowerArm": (-105, 0, 0), "LeftHand": (0, 0, -20),
              "RightUpperLeg": (-35, 6, 0), "RightLowerLeg": (45, 0, 0), "RightFoot": (15, 0, 0),
              "LeftUpperLeg": (28, -8, 0), "LeftLowerLeg": (18, 0, 0), "LeftFoot": (30, 0, 0)},
    "heavy_punch": {"_lift": 0.1, "LowerTorso": (12, 0, 22), "UpperTorso": (18, 0, 32), "Head": (-6, 0, -34),
                    "RightUpperArm": (-96, -6, -30), "RightLowerArm": (0, 0, 0), "RightHand": (0, 0, 85),
                    "LeftUpperArm": (48, -32, 0), "LeftLowerArm": (-65, 0, 0), "LeftHand": (0, 0, -20),
                    "RightUpperLeg": (-55, 8, 0), "RightLowerLeg": (70, 0, 0), "RightFoot": (10, 0, 0),
                    "LeftUpperLeg": (40, -10, 0), "LeftLowerLeg": (15, 0, 0), "LeftFoot": (35, 0, 0)},
    "summon": {"_lift": 0.45, "UpperTorso": (-14, 0, 0), "Head": (-16, 0, 0),
               "RightUpperArm": (-18, 118, 0), "RightLowerArm": (-38, 0, 0),
               "LeftUpperArm": (-18, -118, 0), "LeftLowerArm": (-38, 0, 0),
               "RightUpperLeg": (-4, 3, 0), "RightLowerLeg": (10, 0, 0), "RightFoot": (40, 0, 0),
               "LeftUpperLeg": (2, -3, 0), "LeftLowerLeg": (6, 0, 0), "LeftFoot": (40, 0, 0)},
}


def apply_pose(spec):
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    for name, r in spec.items():
        if name.startswith("_"):
            continue
        pb = arm.pose.bones[name]
        Bq = pb.bone.matrix_local.to_quaternion()
        R = Euler((rad(r[0]), rad(r[1]), rad(r[2])), "XYZ").to_quaternion()
        pb.rotation_quaternion = Bq.inverted() @ R @ Bq
    lift = spec.get("_lift", 0.0)
    root = arm.pose.bones["LowerTorso"]
    root.location = root.bone.matrix_local.to_quaternion().inverted() @ Vector((0, 0, lift))
    bpy.context.view_layer.update()


# store every pose as a keyframe so the .blend doubles as a pose library
POSE_ORDER = ["neutral", "tpose", "idle", "combat", "punch", "heavy_punch", "summon"]
arm.animation_data_create()
for f, name in enumerate(POSE_ORDER, start=1):
    apply_pose(POSES[name])
    for pb in arm.pose.bones:
        pb.keyframe_insert("rotation_quaternion", frame=f)
        pb.keyframe_insert("location", frame=f)
    scene.timeline_markers.new(name, frame=f)
if arm.animation_data.action:
    arm.animation_data.action.name = "BrickFist_Poses"
    for fc in getattr(arm.animation_data.action, "fcurves", []):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
scene.frame_start, scene.frame_end = 1, len(POSE_ORDER)

# ------------------------------------------------------------------ stage: lights, floor, camera
world = bpy.data.worlds.new("Studio")
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.018, 0.017, 0.022, 1)
bg.inputs["Strength"].default_value = 1.0
scene.world = world

stage = bpy.data.collections.new("Stage")
scene.collection.children.link(stage)


def add_light(name, kind, loc, target, energy, color, size):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.size = size
    else:
        ld.shadow_soft_size = size
    lo = bpy.data.objects.new(name, ld)
    lo.location = loc
    lo.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    stage.objects.link(lo)
    return lo


add_light("Key", "AREA", (-5.5, -6.5, 7.0), (0, 0, 2.2), 2600, (1.0, 0.92, 0.82), 4.0)
add_light("Fill", "AREA", (6.5, -5.0, 3.0), (0, 0, 2.0), 700, (0.85, 0.9, 1.0), 5.0)
add_light("Rim", "AREA", (3.5, 6.5, 6.0), (0, 0, 2.6), 2400, (1.0, 0.85, 0.6), 3.0)
add_light("RimL", "AREA", (-4.5, 6.0, 4.0), (0, 0, 2.0), 1200, (0.75, 0.82, 1.0), 3.0)

floor_me = bpy.data.meshes.new("Floor")
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, radius=14, segments=64)
bm.to_mesh(floor_me)
bm.free()
floor = bpy.data.objects.new("Floor", floor_me)
fm = bpy.data.materials.new("Floor")
fm.use_nodes = True
fb = fm.node_tree.nodes["Principled BSDF"]
fb.inputs["Base Color"].default_value = (0.012, 0.011, 0.013, 1)
fb.inputs["Roughness"].default_value = 0.7
floor_me.materials.append(fm)
stage.objects.link(floor)

cam_d = bpy.data.cameras.new("Camera")
cam_d.lens = 70
cam = bpy.data.objects.new("Camera", cam_d)
stage.objects.link(cam)
scene.camera = cam


def frame_camera(target_z, dist, height):
    cam.location = (0, -dist, height)
    cam.rotation_euler = (Vector((0, 0, target_z)) - cam.location).to_track_quat("-Z", "Y").to_euler()


# ------------------------------------------------------------------ render settings
r = scene.render
try:
    r.engine = "BLENDER_EEVEE"
except TypeError:
    r.engine = "BLENDER_EEVEE_NEXT"
ee = scene.eevee
final = MODE == "final"
ee.taa_render_samples = 96 if final else 24
for attr, val in (("use_raytracing", True), ("use_shadows", True), ("shadow_ray_count", 2),
                  ("use_gtao", True), ("gtao_distance", 0.4)):
    if hasattr(ee, attr):
        try:
            setattr(ee, attr, val)
        except Exception:
            pass
r.resolution_x = r.resolution_y = 2048 if final else 900
r.film_transparent = False
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -0.55
except Exception:
    pass

VIEWS = [  # (filename, armature yaw, pose)
    ("01_front", 0, "neutral"),
    ("02_back", 180, "neutral"),
    ("03_left", -90, "neutral"),
    ("04_right", 90, "neutral"),
    ("05_three_quarter_front", 35, "neutral"),
    ("06_three_quarter_back", 215, "neutral"),
    ("07_tpose", 0, "tpose"),
    ("08_idle", 30, "idle"),
    ("09_combat", 30, "combat"),
    ("10_punch", 40, "punch"),
    ("11_heavy_punch", 40, "heavy_punch"),
    ("12_summoning", 20, "summon"),
]
ONLY = ARGS[2].split(",") if len(ARGS) > 2 else None  # optional: re-render a subset by filename
if ONLY:
    VIEWS = [v for v in VIEWS if v[0] in ONLY]
elif not final:
    VIEWS = [v for v in VIEWS if v[0] in ("01_front", "05_three_quarter_front", "02_back", "10_punch")]

render_dir = os.path.join(OUT_DIR, "renders")
os.makedirs(render_dir, exist_ok=True)
for fname, yaw, pose in VIEWS:
    scene.frame_set(POSE_ORDER.index(pose) + 1)
    arm.rotation_euler = (0, 0, rad(yaw))
    bpy.context.view_layer.update()
    wide = pose in ("tpose", "summon")
    frame_camera(2.0, 13.0 if wide else 10.5, 2.3)
    r.filepath = os.path.join(render_dir, fname + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", r.filepath)

# ------------------------------------------------------------------ save
arm.rotation_euler = (0, 0, 0)
scene.frame_set(1)
tris = 0
for obj, _ in PARTS:
    if obj.hide_render:
        continue
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    tris += sum(len(p.vertices) - 2 for p in ev.data.polygons)
print("STATS objects=%d viewport_tris=%d" % (len(PARTS), tris))
blend_path = os.path.join(OUT_DIR, "BrickFist.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)
print("SAVED", blend_path)
