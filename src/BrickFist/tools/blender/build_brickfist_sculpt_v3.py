# Brick Fist v3 (head redesign) — high-detail stone guardian Stand, built procedurally in Blender 5.x.
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
from mathutils import noise as mnoise

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
    "beige": stone_material("BeigeStone", srgb(182, 156, 122), srgb(214, 190, 154), srgb(234, 218, 190), 1.9, 0.6),
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
        w.strength = 0.0022
    collection_for(bone).objects.link(obj)
    PARTS.append((obj, bone))
    return obj


def quad_cap(bm, ring, dome, offset=0):
    """Close a ring with an all-quad domed patch (Coons patch over the ring split into four sides),
    instead of a triangle fan with a pole. Falls back to a fan when the ring can't be split evenly."""
    n = len(ring)
    m = n // 4
    if n % 4 or m < 2:
        cv = bm.verts.new(sum((v.co for v in ring), Vector()) / n + dome)
        for k in range(n):
            bm.faces.new((ring[k], ring[(k + 1) % n], cv))
        return
    ring = ring[offset:] + ring[:offset]

    def edge_v(a, b):
        if b == 0:
            return ring[a]
        if a == m:
            return ring[m + b]
        if b == m:
            return ring[3 * m - a]
        if a == 0:
            return ring[(4 * m - b) % n]
        return None

    P00, P10, P11, P01 = (ring[0].co, ring[m].co, ring[2 * m].co, ring[3 * m].co)
    grid = [[None] * (m + 1) for _ in range(m + 1)]
    for a in range(m + 1):
        for b in range(m + 1):
            v = edge_v(a, b)
            if v is None:
                u, w = a / m, b / m
                bottom, top = ring[a].co, ring[3 * m - a].co
                left, right = ring[(4 * m - b) % n].co, ring[m + b].co
                co = ((1 - w) * bottom + w * top + (1 - u) * left + u * right
                      - ((1 - u) * (1 - w) * P00 + u * (1 - w) * P10 + (1 - u) * w * P01 + u * w * P11))
                v = bm.verts.new(co + dome * (math.sin(math.pi * u) * math.sin(math.pi * w)))
            grid[a][b] = v
    for a in range(m):
        for b in range(m):
            bm.faces.new((grid[a][b], grid[a + 1][b], grid[a + 1][b + 1], grid[a][b + 1]))


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
        base = depth * 0.7 if inner_scale else 0.0
        dome = (tf(s["c"] + axis * depth) - tf(s["c"] + axis * base))
        quad_cap(bm, ring, dome, offset=0 if s["shape"] else n // 8)

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


def lens_shape(N=48, h=0.42):
    """Almond outline with sharp corners (two parabolic arcs)."""
    pts = []
    half = N // 2
    for k in range(half):
        u = 1 - 2 * k / half
        pts.append((u, h * (1 - u * u)))
    for k in range(half):
        u = -1 + 2 * k / half
        pts.append((u, -h * (1 - u * u)))
    return pts


def rounded_shape(N=48, n=4.0, trap=0.0):
    """Rounded-rectangle outline; trap > 0 widens the top (keystone), < 0 the bottom."""
    e = 2.0 / n
    pts = []
    for k in range(N):
        t = 2 * math.pi * k / N
        ct, st = math.cos(t), math.sin(t)
        y = math.copysign(abs(st) ** e, st)
        pts.append((math.copysign(abs(ct) ** e, ct) * (1 + trap * y), y))
    return pts


def shape_slab(name, center, shape, sx, sz, t, mat, bone, rot=(0, 0, 0), kind="plate", taper=0.88,
               back=0.92, mirror=False):
    """Extrude an outline (in X/Z, facing -Y) into a bevelled slab with a domed front."""
    R = Euler((rad(rot[0]), rad(rot[1]), rad(rot[2])), "XYZ").to_matrix()
    C = Vector(center)
    secs = [S((0, y, 0), X, Z, sx, sz, shape=shape) for y in (t / 2, t / 4, -t / 4, -t / 2)]
    for sec, sc in zip(secs, (back, 1.0, 1.0, taper)):
        sec["a"] *= sc
        sec["b"] *= sc
    return loft(name, secs, mat, kind, bone, N=len(shape), cap=(0.0, t * 0.12), inner=(0.6, 0.6),
                xform=lambda q: C + R @ q, mirror=mirror)


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


def _smooth(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def shell(name, body, z0, z1, t0, t1, mat, bone, off=0.012, thick=0.05, bulge=0.0, flare=(0.0, 0.0),
          R=None, M=None, mirror=False, kind="plate", edge=(0.0, 0.0), rock=0.0, round_=0.32, roll=0.014,
          groove=0.0045, inset=0.032, chip=0.007, crack=0.006):
    """Carved armour plate wrapping a Body surface between heights z0..z1 and angles t0..t1 (degrees;
    -90 = front, -180 = character's right / -X, -270 = back).
      bulge  pushes the middle out like the muscle underneath
      flare  offsets the bottom/top edge so plates overlap like layered armour
      edge   bends the bottom/top border (rises toward t1) for anatomical outlines
      round_ rounds the plate corners; roll bevels the border down into the body
      groove/inset cut an engraved seam that follows the plate outline
      chip   breaks the border with small noise-driven chips
      crack  carves hairline fractures (Voronoi cell borders) in random patches of the surface"""
    origin = joint(bone)
    rx_mid = body.at((z0 + z1) / 2)[0]
    arc = abs(rad(t1 - t0)) * (rx_mid + off)
    hgt = abs(z1 - z0) + abs(edge[0]) * 0.5 + abs(edge[1]) * 0.5
    M = M or max(12, min(110, int(arc / 0.0075)))
    R = R or max(8, min(110, int(hgt / 0.0075)))
    tm = (t0 + t1) / 2
    seed = Vector((sum(map(ord, name)) * 0.37, len(name) * 1.91, 0.0))
    bm = bmesh.new()
    O, I = [], []
    for j in range(R + 1):
        zz = j / R
        u = 2 * zz - 1
        span = max(1 - round_, (1 - abs(u) ** 4) ** 0.25)
        ro, ri = [], []
        for i in range(M + 1):
            ti = i / M
            lo, hi = z0 + edge[0] * ti * ti, z1 + edge[1] * ti * ti
            z = lo + (hi - lo) * zz
            t = tm + (t1 - t0) * (ti - 0.5) * span
            d = min(ti * arc * span, (1 - ti) * arc * span, zz * (hi - lo), (1 - zz) * (hi - lo))
            o = off + bulge * math.sin(math.pi * zz) * math.sin(math.pi * ti) + flare[0] * (1 - zz) + flare[1] * zz
            outer = o - roll * (1 - _smooth(0.0, 0.035, d))
            if groove:
                outer -= groove * math.exp(-(((d - inset) / 0.0055) ** 2))
            base = body.point(z, t, 0.0)
            if chip and d < 0.03:
                nz = mnoise.noise(base * 26.0 + seed)
                if nz > 0.12:
                    outer -= chip * (nz - 0.12) / 0.88 * (1 - d / 0.03) * 2.0
            outer += 0.0008 * mnoise.noise(base * 40.0 + seed)
            if crack:
                dist, _ = mnoise.voronoi(base * 4.2 + seed, distance_metric="DISTANCE")
                cw = dist[1] - dist[0]
                if cw < 0.06:
                    patch = mnoise.noise(base * 1.6 + seed * 1.7)
                    if patch > 0.3:
                        outer -= crack * (1 - cw / 0.06) ** 1.6 * min(1.0, (patch - 0.3) / 0.2)
            ro.append(bm.verts.new(body.point(z, t, outer) - origin))
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
    obj = finish(obj, mat, kind, bone, mirror)
    # the base mesh is already dense, one subdivision level keeps seams and chips crisp
    obj.modifiers["Subdivision"].render_levels = 1
    # chips, cracks and wear are sculpted into the plate itself; generic displacement would only add grain
    for mname in ("Chips", "Weathering"):
        if mname in obj.modifiers:
            obj.modifiers.remove(obj.modifiers[mname])
    return rockify(obj, rock)


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
shell("Pec", TORSO, 2.70, 3.10, -92, -162, "beige", B, off=0.01, thick=0.07, bulge=0.085, edge=(0.12, 0.02),
      round_=0.22, mirror=True)
# layered abdominals
for i, (z0, z1) in enumerate(((2.58, 2.705), (2.445, 2.575), (2.31, 2.44))):
    shell("Abs%d" % i, TORSO, z0, z1, -92, -129, "beige", B, off=0.006, thick=0.05, bulge=0.04, round_=0.35,
          inset=0.024,
          mirror=True)
shell("Oblique", TORSO, 2.25, 2.66, -125, -174, "sand", B, off=0.004, thick=0.05, bulge=0.03,
      flare=(0.0, 0.008), edge=(0.0, 0.16), round_=0.25, mirror=True)
shell("SideRib", TORSO, 2.84, 2.99, -169, -212, "dark", B, off=0.008, thick=0.05, bulge=0.02, mirror=True)
shell("ShoulderBlade", TORSO, 2.72, 3.03, -214, -262, "sand", B, off=0.012, thick=0.06, bulge=0.05,
      edge=(-0.06, 0.0), flare=(0.012, 0.0), round_=0.45, mirror=True)
shell("Lat", TORSO, 2.36, 2.74, -206, -262, "sand", B, off=0.006, thick=0.055, bulge=0.035, edge=(0.0, -0.08),
      round_=0.4, mirror=True)
for i, z in enumerate((2.60, 2.69, 2.78)):
    shell("Serratus%d" % i, TORSO, z, z + 0.075, -152, -170, "sand", B, off=0.004, thick=0.045, bulge=0.012,
          round_=0.6, roll=0.01, groove=0.0, mirror=True)
shell("Shoulder", TORSO, 3.03, 3.21, -97, -262, "sand", B, off=0.012, thick=0.05, bulge=0.02,
      flare=(0.012, 0.0), mirror=True)
for i in range(6):
    z1 = 3.03 - i * 0.12
    shell("Spine%d" % i, TORSO, z1 - 0.1, z1, -258, -282, "dark" if i % 2 else "sand", B, off=0.03,
          thick=0.06, bulge=0.025)
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
shell("TassetFront", PELVIS, 1.66, 2.04, -80, -100, "dark", B, off=0.02, thick=0.05, flare=(0.05, 0.0))
shell("Tasset", PELVIS, 1.64, 2.04, -103, -150, "sand", B, off=0.02, thick=0.05, flare=(0.07, 0.0), mirror=True)
shell("TassetSide", PELVIS, 1.62, 2.04, -153, -208, "sand", B, off=0.02, thick=0.05, flare=(0.08, 0.0),
      mirror=True)
shell("TassetBack", PELVIS, 1.66, 2.04, -211, -268, "dark", B, off=0.02, thick=0.05, flare=(0.06, 0.0),
      mirror=True)

# ================================================================== HEAD
# Identity: calm, overwhelming. A level, heavy brow over narrow almond eyes sunk deep in the stone;
# a carved keystone on the forehead that continues as a stepped ridge over the crown; layered muzzle
# plates where a mouth would be; rock-crystal growths behind the temples.
B = "Head"
NECK = Body([(3.14, 0.145, 0.135, 0.135, 2.4), (3.30, 0.13, 0.12, 0.13, 2.4), (3.46, 0.125, 0.115, 0.125, 2.4)])
core("Neck", NECK, "dark", B)
# protective neck rings, each flaring over the one below
for k, (z0, z1, off) in enumerate(((3.165, 3.235, 0.03), (3.225, 3.295, 0.024), (3.285, 3.355, 0.018),
                                   (3.345, 3.41, 0.012))):
    # near-full ring with its split at the back of the neck
    shell("NeckRing%d" % k, NECK, z0, z1, -265, 85, "sand" if k % 2 == 0 else "dark", B, off=off, thick=0.05,
          flare=(0.012, 0.0), round_=0.2, roll=0.01, inset=0.02, groove=0.003, crack=0.0)

HEAD = Body([
    (3.355, 0.09, 0.12, 0.095, 3.6),
    (3.40, 0.15, 0.17, 0.13, 4.2),
    (3.48, 0.19, 0.195, 0.165, 4.4),
    (3.58, 0.195, 0.20, 0.182, 4.0),
    (3.68, 0.198, 0.196, 0.19, 3.8),
    (3.78, 0.185, 0.178, 0.178, 3.5),
    (3.86, 0.15, 0.14, 0.14, 3.0),
    (3.905, 0.095, 0.085, 0.085, 2.6),
])
helmet = vloft("Helmet", HEAD.rows, "sand", "plate", B, cap=(0.01, 0.015))

# deep almond sockets (wider at the mouth of the socket so the walls catch the eye glow)
EYE = lens_shape(h=0.4)
cutter = shape_slab("EyeSocketCutter", (-0.083, -0.205, 3.645), EYE, 0.072, 0.072, 0.13, "dark", B,
                    rot=(0, 5, 0), kind="cutter", taper=1.3, back=0.75, mirror=True)
cutter.hide_render = True
cutter.display_type = "WIRE"
cutter.modifiers.remove(cutter.modifiers["Subdivision"])
boolean = helmet.modifiers.new("EyeSockets", "BOOLEAN")
boolean.operation = "DIFFERENCE"
boolean.object = cutter
boolean.solver = "EXACT"
helmet.modifiers.move(len(helmet.modifiers) - 1, 2)  # after Bevel+Subdivision, before Displace
shape_slab("Eye", (-0.083, -0.152, 3.645), EYE, 0.05, 0.05, 0.03, "eye", B, rot=(0, 5, 0), kind="eye",
           taper=0.8, mirror=True)

# heavy, level brow: calm rather than angry, lifted a touch at the outer edge
shell("Brow", HEAD, 3.682, 3.748, -90.3, -146, "sand", B, off=0.058, thick=0.09, edge=(0.012, 0.016),
      round_=0.18, roll=0.022, inset=0.02, groove=0.003, chip=0.004, crack=0.0, mirror=True)
shell("BrowUnder", HEAD, 3.668, 3.70, -96, -146, "dark", B, off=0.03, thick=0.05, round_=0.4, roll=0.01,
      groove=0.0, crack=0.0, chip=0.0, mirror=True)
# subtle carved nose ridge
shape_slab("Nose", (0, -0.207, 3.588), rounded_shape(n=3.4, trap=-0.35), 0.024, 0.05, 0.05, "sand", B,
           rot=(10, 0, 0), taper=0.7)
# layered muzzle plates where a mouth would be (each upper plate laps over the next)
for k, (z0, z1, half, off) in enumerate(((3.50, 3.565, 30, 0.014), (3.435, 3.51, 27, 0.011),
                                         (3.37, 3.445, 23, 0.008))):
    shell("Muzzle%d" % k, HEAD, z0, z1, -90 + half, -90 - half, "sand" if k != 1 else "beige", B, off=off,
          thick=0.045, flare=(0.009, 0.0), round_=0.16, roll=0.009, inset=0.014, groove=0.0024, crack=0.003,
          chip=0.003)
# squared jaw and overlapping cheek segments
shell("Jaw", HEAD, 3.365, 3.525, -116, -168, "sand", B, off=0.016, thick=0.05, flare=(0.014, 0.0),
      edge=(0.0, 0.05), round_=0.15, roll=0.016, inset=0.02, mirror=True)
shell("CheekLow", HEAD, 3.515, 3.605, -122, -160, "dark", B, off=0.014, thick=0.045, flare=(0.01, 0.0),
      edge=(0.0, 0.02), round_=0.3, inset=0.018, mirror=True)
shell("CheekHigh", HEAD, 3.56, 3.66, -140, -186, "sand", B, off=0.022, thick=0.045, flare=(0.012, 0.0),
      edge=(0.0, 0.02), round_=0.3, inset=0.018, mirror=True)
# layered ear guards
shell("EarGuard", HEAD, 3.52, 3.73, -168, -214, "sand", B, off=0.03, thick=0.055, bulge=0.012, round_=0.5,
      inset=0.02, rock=0.004, mirror=True)
shell("EarGuardCap", HEAD, 3.575, 3.675, -176, -206, "dark", B, off=0.06, thick=0.05, bulge=0.01, round_=0.55,
      roll=0.012, groove=0.0, crack=0.0, mirror=True)
shell("Temple", HEAD, 3.70, 3.83, -140, -210, "sand", B, off=0.016, thick=0.045, round_=0.35, inset=0.02,
      mirror=True)
# crown plates either side of the ridge
shell("Crown", HEAD, 3.80, 3.905, -96, -170, "dark", B, off=0.01, thick=0.04, round_=0.3, inset=0.018,
      groove=0.003, mirror=True)
shell("CrownRear", HEAD, 3.79, 3.90, -196, -344, "sand", B, off=0.012, thick=0.04, round_=0.3, inset=0.018,
      groove=0.003)
# back of the head: tiers overlapping down toward the neck
for k, (z0, z1, off, fl) in enumerate(((3.70, 3.81, 0.02, 0.012), (3.58, 3.715, 0.018, 0.016),
                                        (3.45, 3.595, 0.016, 0.02), (3.36, 3.465, 0.014, 0.026))):
    shell("Nape%d" % k, HEAD, z0, z1, -214 + k * 4, -326 - k * 4, "sand" if k % 2 == 0 else "dark", B, off=off,
          thick=0.045, flare=(fl, 0.0), round_=0.3, inset=0.018, groove=0.003)

# iconic forehead: carved keystone with an engraved diamond, continuing as a stepped ridge over the crown
keystone = shape_slab("Keystone", (0, -0.192, 3.80), rounded_shape(n=4.5, trap=0.32), 0.05, 0.068, 0.06,
                      "sand", B, rot=(-14, 0, 0), taper=0.9)
gem_cut = shape_slab("EmblemCutter", (0, -0.226, 3.805), rounded_shape(n=1.6), 0.02, 0.03, 0.03, "dark", B,
                     rot=(-14, 0, 0), kind="cutter")
gem_cut.hide_render = True
gem_cut.display_type = "WIRE"
gem_cut.modifiers.remove(gem_cut.modifiers["Subdivision"])
eb = keystone.modifiers.new("Emblem", "BOOLEAN")
eb.operation = "DIFFERENCE"
eb.object = gem_cut
eb.solver = "EXACT"
keystone.modifiers.move(len(keystone.modifiers) - 1, 2)
# one continuous carved ridge running back over the crown from the keystone
rockify(tube("CrestRidge", [(0, -0.16, 3.855), (0, -0.07, 3.93), (0, 0.03, 3.945), (0, 0.12, 3.922),
                            (0, 0.195, 3.865)],
             [(0.015, 0.02), (0.026, 0.044), (0.026, 0.042), (0.02, 0.03), (0.011, 0.014)], "sand", B, side=X,
             n=3.6), 0.003)

# rock-crystal growths behind the temples (faceted, not curved demon horns)
for k, (base, tip, r) in enumerate((((-0.18, 0.06, 3.75), (-0.235, 0.15, 3.82), 0.042),
                                     ((-0.185, 0.11, 3.70), (-0.23, 0.19, 3.735), 0.03))):
    b, t = Vector(base), Vector(tip)
    pts = [b, b.lerp(t, 0.5), b.lerp(t, 0.85), t]
    rockify(tube("RockGrowth%d" % k, pts, [(r, r * 0.85), (r * 0.82, r * 0.7), (r * 0.5, r * 0.44),
                                            (r * 0.22, r * 0.2)], "dark", B, side=Z, n=1.8, mirror=True,
                 N=16), 0.004)

# the head is small: keep its carved planes crisp rather than lumpy
for obj, bone in PARTS:
    if bone == "Head":
        for mname, strength in (("Chips", 0.0015), ("Weathering", 0.0015), ("Rock", 0.004)):
            if mname in obj.modifiers:
                obj.modifiers[mname].strength = strength

# ================================================================== RIGHT ARM (left is mirrored)
ax = -SH_X
B = "RightUpperArm"
UARM = Body([
    (3.18, 0.165, 0.165, 0.165, 2.3),
    (3.02, 0.185, 0.185, 0.175, 2.4),
    (2.85, 0.18, 0.2, 0.175, 2.4),
    (2.65, 0.158, 0.165, 0.155, 2.3),
    (2.50, 0.13, 0.13, 0.13, 2.3),
    (2.42, 0.12, 0.12, 0.12, 2.3),
], cx=ax)
core("UpperArm_Core", UARM, "dark", B)
shell("Bicep", UARM, 2.56, 2.96, -55, -125, "sand", B, off=0.006, thick=0.05, bulge=0.06, round_=0.5)
shell("Deltoid", UARM, 2.52, 3.0, -130, -230, "sand", B, off=0.01, thick=0.05, bulge=0.025, flare=(0.0, 0.015))
shell("Tricep", UARM, 2.55, 2.98, -235, -305, "sand", B, off=0.008, thick=0.05, bulge=0.05, round_=0.45)
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
    rockify(PARTS[-1][0], 0.008)
    slab("FingerPlate%d" % i, H(-0.122, y, (pz - 0.28) / 2 + 0.005), 0.118, 0.13, 0.045, "sand", B, rot=(0, 0, -90),
         n=3.6, curve=2.2, taper=0.88)
    rockify(PARTS[-1][0], 0.008)
    slab("PIPPlate%d" % i, H(-0.06, y, pz - 0.06), 0.11, 0.1, 0.045, "dark", B, rot=(-90, 0, -90), n=3.4,
         curve=2.0, taper=0.88)
tube("Thumb_Meta", [H(0.0, -0.21, -0.04), H(0.05, -0.29, -0.15), H(0.09, -0.31, -0.26)],
     [(0.088, 0.082), (0.09, 0.085), (0.082, 0.078)], "sand", B, side=X, n=3.0)
ellipsoid("Thumb_Joint", H(0.1, -0.305, -0.275), (0.082, 0.08, 0.08), "sand", B, n=2.8)
tube("Thumb_Tip", [H(0.12, -0.3, -0.3), H(0.2, -0.24, -0.37), H(0.255, -0.15, -0.385), H(0.27, -0.06, -0.38)],
     [(0.074, 0.072), (0.072, 0.07), (0.066, 0.064), (0.052, 0.052)], "sand", B, side=Z, n=3.0)

for obj, bone in PARTS:
    if bone == "RightHand":
        obj.data.transform(Matrix.Scale(1.12, 4))

# ================================================================== RIGHT LEG
lx = -HIP_X
B = "RightUpperLeg"
THIGH = Body([
    (1.96, 0.22, 0.24, 0.24, 2.4),
    (1.80, 0.25, 0.27, 0.25, 2.5),
    (1.55, 0.235, 0.26, 0.23, 2.5),
    (1.30, 0.19, 0.205, 0.19, 2.4),
    (1.12, 0.148, 0.158, 0.155, 2.3),
    (1.03, 0.14, 0.145, 0.145, 2.3),
], cx=lx)
core("Thigh_Core", THIGH, "dark", B)
shell("Quad", THIGH, 1.18, 1.80, -52, -128, "sand", B, off=0.008, thick=0.055, bulge=0.06, flare=(0, 0.012),
      round_=0.42)
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
shell("CalfUpper", SHIN, 0.68, 1.01, -212, -328, "sand", B, off=0.012, thick=0.055, bulge=0.05,
      flare=(0.018, 0.0), round_=0.45)
shell("CalfLower", SHIN, 0.42, 0.72, -220, -320, "dark", B, off=0.008, thick=0.05, bulge=0.02, round_=0.35)
shell("KneeSide", SHIN, 0.96, 1.12, -128, -205, "dark", B, off=0.012, thick=0.045, round_=0.4)
shell("AnkleGuard", SHIN, 0.21, 0.37, -35, -145, "sand", B, off=0.012, thick=0.05, flare=(0.035, 0.0),
      round_=0.3)
shell("ShinOuter", SHIN, 0.42, 0.92, -145, -210, "dark", B, off=0.008, thick=0.045)
band("AnkleRing", (lx, 0, 0.31), 0.135, 0.148, 3.0, 0.022, 0.03, B)

B = "RightFoot"
foot_secs = [S((lx, y, zc), X, Z, a, b, 3.6) for y, a, b, zc in (
    (0.165, 0.115, 0.10, 0.12),
    (0.07, 0.14, 0.15, 0.16),
    (-0.08, 0.15, 0.125, 0.135),
    (-0.23, 0.145, 0.095, 0.105),
    (-0.335, 0.125, 0.07, 0.08),
)]
rockify(loft("Boot", foot_secs, "sand", "plate", B, cap=(0.01, 0.03)), 0.02)
slab("Sole", (lx, -0.075, 0.028), 0.31, 0.53, 0.055, "dark", B, rot=(90, 0, 0), n=4.0, taper=0.92)
rockify(PARTS[-1][0], 0.012)
slab("ToePlate", (lx, -0.255, 0.165), 0.27, 0.15, 0.05, "sand", B, rot=(-62, 0, 0), n=3.6, curve=1.6, taper=0.88)
rockify(PARTS[-1][0], 0.01)
slab("InstepPlate", (lx, -0.13, 0.255), 0.28, 0.14, 0.05, "dark", B, rot=(-42, 0, 0), n=3.6, curve=1.6, taper=0.88)
slab("Heel", (lx, 0.185, 0.13), 0.24, 0.17, 0.05, "dark", B, rot=(8, 0, 180), n=3.6, curve=1.6, taper=0.88)

# ------------------------------------------------------------------ symmetry (modelling stage)
# Every off-centre part keeps a live Mirror modifier until the model is signed off. Rigging and
# poses belong to a later phase (see build_brickfist_sculpt_v1.py for the earlier rigged version).
# relaxed modelling stance (no rig yet): bend the elbow, then open the arm and leg away from the body
def swing(bones, pivot, rot):
    R = Euler(tuple(rad(a) for a in rot), "XYZ").to_matrix()
    for obj, bone in PARTS:
        if bone in bones:
            obj.data.transform(R.to_4x4())
            obj.location = pivot + R @ (obj.location - pivot)


swing({"RightLowerArm", "RightHand"}, joint("RightLowerArm"), (-8, 0, 0))
swing({"RightUpperArm", "RightLowerArm", "RightHand"}, joint("RightUpperArm"), (0, 13, 0))
swing({"RightUpperLeg", "RightLowerLeg", "RightFoot"}, joint("RightUpperLeg"), (0, 4, 0))
swing({"RightFoot"}, joint("RightUpperLeg") + Euler((0, rad(4), 0)).to_matrix() @ (joint("RightFoot") - joint("RightUpperLeg")),
      (0, -4, 0))

ROOT = bpy.data.objects.new("BrickFist", None)
ROOT.empty_display_type = "ARROWS"
scene.collection.objects.link(ROOT)
for obj, bone in PARTS:
    if bone.startswith("Right") and "Mirror" not in obj.modifiers:
        mm = obj.modifiers.new("Mirror", "MIRROR")
        mm.mirror_object = SYM
        mm.use_clip = False
        obj.modifiers.move(len(obj.modifiers) - 1, 0)
for bone, col in COLLECTIONS.items():
    if bone.startswith("Right"):
        col.name = bone[5:]  # e.g. "Hand": one collection holds the mirrored pair
for obj in [o for o, _ in PARTS] + [SYM]:
    obj.parent = ROOT
for sx in (-1, 1):
    ld = bpy.data.lights.new("SocketGlow", "POINT")
    ld.energy = 0.12
    ld.color = (1.0, 0.78, 0.22)
    ld.shadow_soft_size = 0.01
    lo = bpy.data.objects.new("SocketGlow", ld)
    lo.location = (sx * 0.083, -0.185, 3.645)
    lo.parent = ROOT
    collection_for("Head").objects.link(lo)

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

VIEWS = [  # (filename, yaw, framing)
    ("01_head_front", 0, "head"),
    ("02_head_left", -90, "head"),
    ("03_head_right", 90, "head"),
    ("04_head_back", 180, "head"),
    ("05_head_top", 0, "headtop"),
    ("06_head_bottom", 0, "headbottom"),
    ("07_head_three_quarter_front", 35, "head"),
    ("08_head_three_quarter_rear", 215, "head"),
    ("09_face_extreme_closeup", 12, "face"),
    ("10_wireframe_head_front", 0, "wirehead"),
    ("11_wireframe_head_three_quarter", 35, "wirehead"),
    ("12_context_full_three_quarter", 35, "full"),
]
ONLY = ARGS[2].split(",") if len(ARGS) > 2 else None  # optional: re-render a subset by filename
if ONLY:
    VIEWS = [v for v in VIEWS if v[0] in ONLY]
elif not final:
    VIEWS = [v for v in VIEWS if v[0] in ("01_head_front", "07_head_three_quarter_front", "02_head_left",
                                         "04_head_back", "09_face_extreme_closeup")]

# clay: every stone/gold slot is swapped for one neutral material while rendering (eyes keep their glow)
CLAY = bpy.data.materials.new("Clay")
CLAY.use_nodes = True
CLAY.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.42, 0.4, 0.38, 1)
CLAY.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.55
WIRE = bpy.data.materials.new("Wire")
WIRE.use_nodes = True
WIRE.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.004, 0.004, 0.005, 1)
WIRE.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
SAVED_MATS = {}


def set_clay(on):
    for obj, _ in PARTS:
        mats = obj.data.materials
        if on:
            SAVED_MATS[obj.name] = list(mats)
            for i, m in enumerate(mats):
                if m is not MAT["eye"]:
                    mats[i] = CLAY
        else:
            for i, m in enumerate(SAVED_MATS[obj.name]):
                mats[i] = m


def set_wireframe(on):
    for obj, _ in PARTS:
        if (on and obj.hide_render) or (not on and "WireOverlay" not in obj.modifiers):
            continue
        sub = obj.modifiers.get("Subdivision")
        if on:
            obj["_sub"] = sub.render_levels if sub else 0
            if sub:
                sub.render_levels = 0
            obj.data.materials.append(WIRE)
            wm = obj.modifiers.new("WireOverlay", "WIREFRAME")
            wm.thickness = 0.0016
            wm.use_replace = False
            wm.use_even_offset = True
            wm.material_offset = len(obj.data.materials) - 1
        else:
            obj.modifiers.remove(obj.modifiers["WireOverlay"])
            obj.data.materials.pop()
            if sub:
                sub.render_levels = obj["_sub"]
            del obj["_sub"]


HEAD_TARGET = Vector((0, 0, 3.66))
HEAD_PARTS = {o.name for o, b in PARTS if b == "Head"}


def isolate_head(on):
    """Head turnaround renders show only the head and neck (the torso would block top/bottom views)."""
    for obj, _ in PARTS:
        if obj.name not in HEAD_PARTS and not obj.name.endswith("Cutter"):
            obj.hide_render = on
    floor.hide_render = on


render_dir = os.path.join(OUT_DIR, "renders_v3")
os.makedirs(render_dir, exist_ok=True)
set_clay(True)
wire_on = False
iso_on = False
for fname, yaw, framing in VIEWS:
    ROOT.rotation_euler = (0, 0, rad(yaw))
    bpy.context.view_layer.update()
    want_iso = framing.startswith("head") or framing == "wirehead"
    if want_iso != iso_on:
        isolate_head(want_iso)
        iso_on = want_iso
    want_wire = framing.startswith("wire")
    if want_wire != wire_on:
        set_wireframe(want_wire)
        wire_on = want_wire
    cam_d.lens = 70
    target = ROOT.matrix_world @ HEAD_TARGET
    if framing == "full":
        frame_camera(2.0, 10.5, 2.3)
    elif framing == "headtop":
        cam.location = target + Vector((0, 0, 2.0))
        cam.rotation_euler = (0, 0, 0)
    elif framing == "headbottom":
        cam.location = target - Vector((0, 0, 2.0))
        cam.rotation_euler = (math.pi, 0, 0)
    else:
        dist = 1.15 if framing == "face" else 2.0
        tgt = target + (Vector((0, 0, -0.01)) if framing == "face" else Vector())
        cam.location = tgt + Vector((0, -dist, 0.08 * dist))
        cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    r.filepath = os.path.join(render_dir, fname + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", r.filepath)
if wire_on:
    set_wireframe(False)
if iso_on:
    isolate_head(False)
set_clay(False)

# ------------------------------------------------------------------ save
ROOT.rotation_euler = (0, 0, 0)
tris = 0
for obj, _ in PARTS:
    if obj.hide_render:
        continue
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    tris += sum(len(p.vertices) - 2 for p in ev.data.polygons)
print("STATS objects=%d viewport_tris=%d" % (len(PARTS), tris))
blend_path = os.path.join(OUT_DIR, "BrickFist_v3.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)
print("SAVED", blend_path)
