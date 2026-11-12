"""Build all gameplay props -> public/models/props.glb (+ contact sheet preview)."""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix, Euler
sys.path.insert(0, os.path.dirname(__file__))
import importlib, lib_common as L, lib_mats as M
importlib.reload(L); importlib.reload(M)

FAST = '--fast' in sys.argv
ATLAS = 1024 if FAST else 2048
random.seed(11)
L.reset_scene()

PROPS = {}        # name -> top object
BAKE_GROUPS = {'StoneProps': [], 'WoodProps': [], 'ClayProps': []}
LATE = []         # (owner_name, obj) constant-material pieces joined after baking


def finish(ob, name, group):
    ob = L.apply_all(ob)
    ob.name = name
    ob.data.name = name + '_mesh'
    PROPS[name] = ob
    BAKE_GROUPS[group].append(ob)
    return ob


def J(objs, name):
    objs = [L.apply_all(o) for o in objs]
    return L.join(objs, name)


gold = M.gold('Gold')
brass = M.gold('Brass', (0.85, 0.58, 0.25), 0.38)
glow = L.emissive_mat('Glow', (0.15, 1.0, 0.85), 6.0, base=(0.05, 0.3, 0.25))
flame_m = L.emissive_mat('Flame', (1.0, 0.55, 0.15), 12.0, base=(1.0, 0.7, 0.3))

# ===================================================================== TILES
def slab(name, seed, chip=None):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=28, y_segments=28, size=0.485)
    top = list(bm.faces)
    # extrude down
    ret = bmesh.ops.extrude_face_region(bm, geom=top)
    vv = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=vv, vec=(0, 0, -0.2))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = L.mesh_from_bm(bm, name)
    L.bevel_mod(ob, 0.03, 3, 60)
    L.apply_all(ob, transforms=False)
    rnd = random.Random(seed)
    # worn, slightly dished top + uneven edges
    from mathutils import noise
    off = Vector((rnd.random() * 50, rnd.random() * 50, 0))
    for v in ob.data.vertices:
        if v.co.z > -0.05:
            r = max(abs(v.co.x), abs(v.co.y))
            dish = -0.006 * (1 - min(1, r / 0.45) ** 2)
            n = noise.noise(v.co * 3.0 + off) * 0.008 + noise.noise(v.co * 11 + off) * 0.0025
            v.co.z += (dish + n) * (1.0 if v.co.z > -0.001 else 0.5)
        v.co.x += noise.noise(v.co * 4 + off + Vector((3, 0, 0))) * 0.004
        v.co.y += noise.noise(v.co * 4 + off + Vector((0, 3, 0))) * 0.004
    # clamp top to 0 max so the top face sits at y=0
    mz = max(v.co.z for v in ob.data.vertices)
    for v in ob.data.vertices:
        v.co.z -= mz
    if chip:
        k = L.uv_sphere('chip', 1.0, loc=chip[0], seg=8, rings=6, scale=chip[1])
        k.rotation_euler = (0.4, 0.7, 0.2)
        b = ob.modifiers.new('chip', 'BOOLEAN'); b.object = k; b.operation = 'DIFFERENCE'; b.solver = 'EXACT'
        L.apply_all(ob, transforms=False)
        bpy.data.objects.remove(k)
    L.shade_smooth(ob, 35)
    return ob


tile_cols = {'Tile_A': ((0.27, 0.215, 0.16), 1.0), 'Tile_B': ((0.24, 0.205, 0.165), 7.3), 'Tile_C': ((0.285, 0.22, 0.155), 13.1),
             'TileGoal': ((0.20, 0.20, 0.215), 21.7)}
chips = {'Tile_A': ((0.47, 0.47, -0.02), (0.06, 0.05, 0.05)), 'Tile_B': ((-0.47, 0.2, -0.01), (0.05, 0.08, 0.04)),
         'Tile_C': None, 'TileGoal': ((0.48, -0.47, -0.01), (0.04, 0.04, 0.03))}
for i, (nm, (c, seed)) in enumerate(tile_cols.items()):
    ob = slab(nm, int(seed * 10), chips[nm])
    mat = M.stone('st_' + nm, base=c, dark=tuple(x * 0.62 for x in c), warm=tuple(min(1, x * 1.12) for x in c),
                  scale=1.4, crack_seed=seed, moss=0.45 if nm != 'TileGoal' else 0.15, crack_amt=1.0 if nm != 'TileGoal' else 0.4)
    L.assign(ob, mat)
    finish(ob, nm, 'StoneProps')

# engraved ring on goal tile
tg = PROPS['TileGoal']
for rr, w in ((0.33, 0.035), (0.20, 0.022)):
    bpy.ops.mesh.primitive_torus_add(major_radius=rr, minor_radius=w, major_segments=72, minor_segments=10, location=(0, 0, 0.0))
    cut = bpy.context.active_object
    cut.scale = (1, 1, 0.8)
    b = tg.modifiers.new('ring', 'BOOLEAN'); b.object = cut; b.operation = 'DIFFERENCE'; b.solver = 'EXACT'
    L.apply_all(tg, transforms=False)
    bpy.data.objects.remove(cut)
    bpy.ops.mesh.primitive_torus_add(major_radius=rr, minor_radius=w * 0.62, major_segments=72, minor_segments=8, location=(0, 0, -0.012))
    ring = bpy.context.active_object
    ring.scale = (1, 1, 0.7)
    L.apply_all(ring)
    L.assign(ring, glow)
    LATE.append(('TileGoal', ring))
# small rune ticks between rings
for k in range(8):
    a = k * math.pi / 4 + math.pi / 8
    p = Vector((math.cos(a) * 0.265, math.sin(a) * 0.265, -0.004))
    d = L.box('tick', (0.018, 0.05, 0.012), loc=p, bevel=0.005, rot=(0, 0, a + math.pi / 2))
    L.apply_all(d)
    L.assign(d, glow)
    LATE.append(('TileGoal', d))

# ===================================================================== BLOCK STONE
bs = L.box('Block_Stone', (0.86, 0.86, 0.86), loc=(0, 0, 0.43), bevel=0.0)
L.apply_all(bs)
L.subsurf(bs, 2)
bs.modifiers[-1].subdivision_type = 'SIMPLE'
L.apply_all(bs)
L.bevel_mod(bs, 0.05, 3, 30)
L.apply_all(bs)
L.remesh(bs, 0.012)
sm = bs.modifiers.new('sm', 'SMOOTH'); sm.iterations = 4; sm.factor = 0.6
L.displace_noise(bs, 0.035, 0.25, depth=3)
L.apply_all(bs)
for c in [((0.43, -0.43, 0.8), (0.12, 0.1, 0.09)), ((-0.44, -0.3, 0.2), (0.08, 0.12, 0.1)), ((0.2, 0.44, 0.86), (0.15, 0.08, 0.06))]:
    k = L.uv_sphere('chip', 1.0, loc=c[0], seg=7, rings=5, scale=c[1]); k.rotation_euler = (0.5, 0.3, 0.8)
    b = bs.modifiers.new('c', 'BOOLEAN'); b.object = k; b.operation = 'DIFFERENCE'; b.solver = 'EXACT'
    L.apply_all(bs, transforms=False); bpy.data.objects.remove(k)
# flatten base
for v in bs.data.vertices:
    v.co.z = max(v.co.z, 0.0)
L.decimate(bs, 8000)
L.shade_smooth(bs, 50)
L.assign(bs, M.stone('st_block', base=(0.17, 0.18, 0.20), dark=(0.08, 0.085, 0.10), warm=(0.24, 0.23, 0.21), scale=2.0,
                     crack_seed=31.0, moss=0.6))
finish(bs, 'Block_Stone', 'StoneProps')

# ===================================================================== PEDESTAL
ped_parts = []
for z0, h, w in ((0.0, 0.07, 0.48), (0.07, 0.04, 0.42), (0.11, 0.18, 0.32), (0.29, 0.03, 0.40), (0.32, 0.03, 0.44)):
    ped_parts.append(L.box('pp', (w, w, h), loc=(0, 0, z0 + h / 2), bevel=0.012, segs=2))
ped = J(ped_parts, 'Pedestal')
L.subsurf(ped, 1); ped.modifiers[-1].subdivision_type = 'SIMPLE'
L.displace_noise(ped, 0.006, 0.08)
L.apply_all(ped)
L.shade_smooth(ped, 40)
L.assign(ped, M.stone('st_ped', base=(0.27, 0.25, 0.22), dark=(0.15, 0.14, 0.13), warm=(0.33, 0.29, 0.24), scale=3, crack_seed=41, moss=0.3))
finish(ped, 'Pedestal', 'StoneProps')

# ===================================================================== BOOKS
cover_cols = [(0.45, 0.08, 0.07), (0.06, 0.28, 0.30), (0.33, 0.18, 0.08), (0.24, 0.10, 0.28), (0.10, 0.20, 0.10), (0.50, 0.30, 0.08)]
mats_cover = [M.cloth(f'cover{i}', c, scale=2) for i, c in enumerate(cover_cols)]
mat_pages = M.pages('pages')


def book(name, w, d, h, loc, rotz, cmat, open_gap=0.0):
    """Hardcover book lying flat: w (x), d (y spine depth), h thickness."""
    parts = []
    ct = 0.022  # cover thickness
    top = L.box('cvt', (w, d, ct), loc=(0, 0, h - ct / 2), bevel=0.008)
    bot = L.box('cvb', (w, d, ct), loc=(0, 0, ct / 2), bevel=0.008)
    spine = L.cylinder('sp', h / 2, d, loc=(-w / 2 + 0.01, d / 2, h / 2), verts=16, bevel=0.0, rot=(math.pi / 2, 0, 0))
    spine.scale = (1, 1, 1)
    sp_s = L.box('sps', (0.05, d, h), loc=(-w / 2 + 0.02, 0, h / 2), bevel=0.012)
    for o in (top, bot, sp_s):
        L.assign(o, cmat)
    pg = L.box('pg', (w - 0.04, d - 0.03, h - 2 * ct + 0.004), loc=(0.01, 0, h / 2), bevel=0.006)
    L.assign(pg, mat_pages)
    # raised spine bands
    bands = []
    for k in range(3):
        yy = -d / 2 + d * (k + 1) / 4
        bnd = L.box('bd', (0.06, 0.03, h + 0.012), loc=(-w / 2 + 0.018, yy, h / 2), bevel=0.01)
        L.assign(bnd, cmat)
        bands.append(bnd)
    bpy.data.objects.remove(spine)
    b = J([top, bot, sp_s, pg] + bands, name)
    # brass corners (late, constant material)
    corners = []
    for sx in (1,):
        for sy in (-1, 1):
            for z in (0.0, h):
                c = L.box('corner', (0.07, 0.07, 0.03), loc=(sx * (w / 2 - 0.03), sy * (d / 2 - 0.03), 0.016 if z == 0 else z - 0.016),
                          bevel=0.01)
                corners.append(c)
    cn = J(corners, name + '_brass')
    L.assign(cn, brass)
    for o in (b, cn):
        o.location = loc
        o.rotation_euler = (0, 0, rotz)
    return b, cn


stack = [(0.86, 0.70, 0.21, 0.05), (0.80, 0.66, 0.17, -0.12), (0.84, 0.64, 0.20, 0.1), (0.74, 0.58, 0.16, -0.06), (0.70, 0.52, 0.14, 0.18)]
z = 0.0
books, brs = [], []
for i, (w, d, h, rz) in enumerate(stack):
    b, cn = book(f'bk{i}', w, d, h, (random.uniform(-0.02, 0.02), random.uniform(-0.02, 0.02), z), rz, mats_cover[i % len(mats_cover)])
    z += h
    books.append(b)
    brs.append(cn)
print('book stack height', z)
bb = J(books, 'Block_Books')
# scale to exactly 0.9 tall, fit in 0.9 footprint
L.set_active(bb)
bbx = J(brs, 'Block_Books_brass')
for o in (bb, bbx):
    for v in o.data.vertices:
        v.co.z *= 0.9 / z
L.shade_smooth(bb, 35)
finish(bb, 'Block_Books', 'WoodProps')
LATE.append(('Block_Books', bbx))

# ===================================================================== CRATE
cw = 0.88
wood_light = M.wood('wood_crate', base=(0.42, 0.25, 0.12), dark=(0.20, 0.11, 0.05), light=(0.58, 0.40, 0.22), axis='X', space='world')
wood_frame = M.wood('wood_crate_dark', base=(0.28, 0.15, 0.07), dark=(0.12, 0.06, 0.03), light=(0.40, 0.25, 0.12), axis='Z', space='world')
cparts = []
core = L.box('core', (cw - 0.04, cw - 0.04, cw - 0.04), loc=(0, 0, cw / 2), bevel=0.0)
L.assign(core, M.flat('crate_gap', (0.05, 0.03, 0.02), 0.9, 0.1))
cparts.append(core)


def onface(o, face):
    L.apply_all(o)
    o.data.transform(Matrix.Rotation(face * math.pi / 2, 4, 'Z'))
    return o


pl = 0.2
for face in range(4):
    for k in range(4):
        zz = 0.05 + pl / 2 + k * (pl + 0.01)
        p = L.box('pl', (cw - 0.1, 0.03, pl), loc=(0, -cw / 2 + 0.015, zz), bevel=0.007)
        L.assign(p, wood_light)
        cparts.append(onface(p, face))
    for sx in (-1, 1):
        f = L.box('fr', (0.1, 0.06, cw), loc=(sx * (cw / 2 - 0.05), -cw / 2 + 0.01, cw / 2), bevel=0.014)
        L.assign(f, wood_frame)
        cparts.append(onface(f, face))
    for zz in (0.05, cw - 0.05):
        rim = L.box('rim', (cw - 0.18, 0.06, 0.1), loc=(0, -cw / 2 + 0.005, zz), bevel=0.014)
        L.assign(rim, wood_frame)
        cparts.append(onface(rim, face))
    ln = (cw - 0.2) * 1.36
    br = L.box('br', (ln, 0.045, 0.09), loc=(0, -cw / 2 - 0.005, cw / 2), bevel=0.012, rot=(0, math.radians(45 if face % 2 else -45), 0))
    L.assign(br, wood_frame)
    cparts.append(onface(br, face))
for z0 in (cw - 0.02, ):
    for k in range(4):
        p = L.box('lidp', (cw - 0.04, (cw - 0.04) / 4 - 0.008, 0.04), loc=(0, -cw / 2 + 0.02 + (k + 0.5) * (cw - 0.04) / 4, z0), bevel=0.008)
        L.assign(p, wood_light)
        cparts.append(p)
    for sx in (-1, 1):
        p = L.box('lidb', (0.09, cw - 0.02, 0.05), loc=(sx * (cw / 2 - 0.12), 0, z0 + 0.03), bevel=0.012)
        L.assign(p, wood_frame)
        cparts.append(p)
crate = J(cparts, 'Block_Crate')
mz = max(v.co.z for v in crate.data.vertices)
crate.data.transform(Matrix.Scale(0.9 / mz, 4))
L.shade_smooth(crate, 35)
nails = []
for face in range(4):
    for sx in (-1, 1):
        for zz in (0.1, 0.33, 0.56, 0.79):
            n = L.cylinder('nail', 0.012, 0.012, loc=(sx * (cw / 2 - 0.05), -cw / 2 - 0.02, zz), verts=8, bevel=0.003, rot=(math.pi / 2, 0, 0))
            nails.append(onface(n, face))
nl = J(nails, 'crate_nails')
nl.data.transform(Matrix.Scale(0.9 / mz, 4))
L.assign(nl, M.gold('Iron', (0.22, 0.21, 0.21), 0.5))
finish(crate, 'Block_Crate', 'WoodProps')
LATE.append(('Block_Crate', nl))

# ===================================================================== CANDLE
holder = L.lathe('holder', [(0.0, 0.0), (0.11, 0.0), (0.12, 0.012), (0.115, 0.03), (0.06, 0.04), (0.035, 0.06), (0.03, 0.12),
                            (0.045, 0.135), (0.03, 0.15), (0.03, 0.2), (0.075, 0.215), (0.08, 0.235), (0.05, 0.24), (0.0, 0.24)], steps=40)
L.apply_all(holder)
handle = L.curve_tube('handle', [(0.11, 0, 0.02), (0.18, 0, 0.05), (0.2, 0, 0.12), (0.16, 0, 0.14)], radius=0.012)
L.apply_all(handle)
hold = J([holder, handle], 'Candle_holder')
L.assign(hold, brass)
wax_prof = [(0.0, 0.23), (0.045, 0.23), (0.046, 0.30), (0.044, 0.40), (0.045, 0.44), (0.04, 0.455), (0.02, 0.452), (0.0, 0.448)]
wax = L.lathe('wax', wax_prof, steps=32)
L.apply_all(wax)
drips = []
for k in range(5):
    a = random.uniform(0, 2 * math.pi)
    ln = random.uniform(0.04, 0.12)
    p0 = Vector((math.cos(a) * 0.044, math.sin(a) * 0.044, 0.445))
    d = L.curve_tube('drip', [p0, p0 + Vector((math.cos(a) * 0.006, math.sin(a) * 0.006, -ln * 0.5)), p0 + Vector((math.cos(a) * 0.004, math.sin(a) * 0.004, -ln))],
                     radius=0.011, radii=[1.0, 0.9, 1.2])
    L.apply_all(d)
    drips.append(d)
wick = L.cylinder('wick', 0.004, 0.025, loc=(0, 0, 0.447), verts=6, bevel=0)
L.apply_all(wick)
wk = L.simple_mat('wickmat', (0.02, 0.015, 0.01), 0.9)
L.assign(wick, wk)
waxo = J([wax] + drips, 'Candle')
L.assign(waxo, M.flat('wax', (0.92, 0.85, 0.66), 0.55, 0.08, 30, 0.2))
waxo.data.materials.append(wk)
L.set_active(waxo)
wick_ob = wick
for p in wick_ob.data.polygons:
    p.material_index = 0
L.shade_smooth(waxo, 50)
finish(waxo, 'Candle', 'WoodProps')
LATE.append(('Candle', hold))
LATE.append(('Candle', wick_ob))
# flame child node: origin at wick top
fl = L.lathe('Flame', [(0.0, 0.0), (0.016, 0.012), (0.022, 0.03), (0.016, 0.055), (0.006, 0.075), (0.0, 0.085)], steps=20)
L.apply_all(fl)
L.assign(fl, flame_m)
fl.name = 'Flame'
FLAME_POS = (0, 0, 0.462)

# ===================================================================== JUG
jug_prof = [(0.0, 0.0), (0.09, 0.0), (0.105, 0.01), (0.14, 0.07), (0.155, 0.15), (0.145, 0.24), (0.10, 0.31), (0.065, 0.35),
            (0.06, 0.39), (0.075, 0.425), (0.085, 0.44), (0.078, 0.45), (0.06, 0.445), (0.055, 0.41), (0.055, 0.36)]
jug = L.lathe('Jug', jug_prof, steps=56, thickness=0.0)
L.apply_all(jug)
sol = jug.modifiers.new('s', 'SOLIDIFY'); sol.thickness = 0.012; sol.offset = -1
L.apply_all(jug)
spout = None
hd = L.curve_tube('jhandle', [(0.06, 0, 0.40), (0.15, 0, 0.40), (0.19, 0, 0.32), (0.16, 0, 0.22), (0.135, 0, 0.18)], radius=0.02, bevel_res=4)
hd.data.bevel_mode = 'ROUND'
L.apply_all(hd)
hd.data.transform(Matrix.Scale(1.0, 4))
for v in hd.data.vertices:  # flatten handle profile
    pass
jug = J([jug, hd], 'Jug')
L.shade_smooth(jug, 60)
L.assign(jug, M.terracotta('terracotta_jug', base=(0.66, 0.33, 0.17), band=(0.08, 0.45, 0.45), band_z=(0.2, 0.27), space='world'))
finish(jug, 'Jug', 'ClayProps')

# ===================================================================== PLANTS
pot_prof = [(0.0, 0.0), (0.075, 0.0), (0.085, 0.01), (0.1, 0.12), (0.112, 0.15), (0.125, 0.155), (0.128, 0.18), (0.118, 0.185),
            (0.108, 0.175), (0.098, 0.16)]


def pot(name):
    p = L.lathe(name, pot_prof, steps=40)
    L.apply_all(p)
    s = p.modifiers.new('s', 'SOLIDIFY'); s.thickness = 0.01; s.offset = -1
    L.apply_all(p)
    soil = L.cylinder(name + '_soil', 0.1, 0.01, loc=(0, 0, 0.15), verts=32, bevel=0.0)
    L.displace_noise(soil, 0.006, 0.02)
    L.apply_all(soil)
    L.assign(soil, M.flat('soil', (0.12, 0.08, 0.05), 0.95, 0.3, 60, 0.6))
    L.assign(p, M.terracotta('terracotta_pot', base=(0.64, 0.34, 0.2), band=(0.75, 0.62, 0.38), band_z=(0.12, 0.15), space='world', pattern=False))
    return [p, soil]


def leaf(name, length, width, pitch0, pitch1, yaw, base=(0, 0, 0.15), fold=0.3, twist=0.0, segs=12):
    bm = bmesh.new()
    rows = []
    pos = Vector(base)
    ang = pitch0
    for i in range(segs + 1):
        t = i / segs
        w = width * math.sin(math.pi * min(1, t * 0.95 + 0.05)) ** 0.8 * (1 - 0.3 * t)
        ang = pitch0 + (pitch1 - pitch0) * t * t
        if i > 0:
            pos = pos + Vector((math.cos(ang), 0, math.sin(ang))) * (length / segs)
        row = []
        for j in range(5):
            s = (j - 2) / 2
            off = Vector((0, s * w, abs(s) * fold * w))
            row.append(bm.verts.new(pos + off))
        rows.append(row)
    for a, b in zip(rows[:-1], rows[1:]):
        for j in range(4):
            bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    ob = L.mesh_from_bm(bm, name)
    s = ob.modifiers.new('s', 'SOLIDIFY'); s.thickness = 0.004
    L.apply_all(ob)
    ob.data.transform(Matrix.Rotation(yaw, 4, 'Z'))
    L.shade_smooth(ob)
    return ob


wilt_mat = M.flat('leaf_wilt', (0.36, 0.30, 0.10), 0.8, 0.3, 40, 0.2)
wilt_brown = M.flat('leaf_brown', (0.30, 0.18, 0.07), 0.85, 0.3, 40, 0.2)
leaf_mat = M.flat('leaf_green', (0.10, 0.42, 0.08), 0.55, 0.25, 40, 0.2)
leaf_mat2 = M.flat('leaf_green2', (0.20, 0.52, 0.12), 0.55, 0.25, 40, 0.2)
stem_mat = M.flat('stem', (0.22, 0.34, 0.08), 0.7, 0.1)
petal_mat = M.flat('petal', (0.95, 0.35, 0.50), 0.55, 0.1)
petal_mat2 = M.flat('petal2', (1.0, 0.75, 0.25), 0.55, 0.1)
centre_mat = M.flat('flowerc', (1.0, 0.85, 0.2), 0.6, 0.2)
deadpetal = M.flat('petal_dead', (0.45, 0.25, 0.2), 0.8, 0.2)


def flower(top, petals_m, size=1.0, droop=0.0, parts=None):
    up = Vector((0, math.sin(droop), math.cos(droop)))
    for p in range(6):
        a = p * math.pi / 3
        off = Vector((math.cos(a) * 0.03, math.sin(a) * 0.03, 0.0)) * size
        pt = L.uv_sphere('pt', 1.0, loc=(0, 0, 0), seg=12, rings=8, scale=(0.032 * size, 0.017 * size, 0.007 * size))
        pt.rotation_euler = (0, -0.35, a)
        L.apply_all(pt)
        pt.data.transform(Matrix.Translation(off))
        pt.data.transform(Matrix.Rotation(droop, 4, 'X'))
        pt.data.transform(Matrix.Translation(top))
        L.assign(pt, petals_m); parts.append(pt)
    c = L.uv_sphere('fc', 0.016 * size, loc=(0, 0, 0.006 * size), seg=12, rings=8)
    L.apply_all(c)
    c.data.transform(Matrix.Rotation(droop, 4, 'X'))
    c.data.transform(Matrix.Translation(top))
    L.assign(c, centre_mat); parts.append(c)


# wilted: limp leaves hanging over the rim, one sad flower bowed down
wparts = pot('pw')
stem = L.curve_tube('wstem', [(0, 0, 0.15), (0.0, 0.0, 0.27), (0.02, -0.03, 0.33), (0.04, -0.09, 0.32), (0.05, -0.12, 0.27)], radius=0.007)
L.apply_all(stem); L.assign(stem, wilt_mat); wparts.append(stem)
flower(Vector((0.05, -0.125, 0.255)), deadpetal, 0.8, droop=2.6, parts=wparts)
for k in range(7):
    yaw = k * 2 * math.pi / 7 + random.uniform(-0.3, 0.3)
    lf = leaf('wl', random.uniform(0.17, 0.22), 0.04, math.radians(random.uniform(40, 65)), math.radians(-95), yaw,
              base=(0.0, 0.0, 0.15 + random.uniform(0, 0.04)), fold=0.6)
    L.assign(lf, wilt_mat if k % 3 else wilt_brown)
    wparts.append(lf)
fallen = leaf('fallen', 0.12, 0.035, 0.0, 0.05, 0.6, base=(0.12, -0.02, 0.002), fold=0.4)
L.assign(fallen, wilt_brown); wparts.append(fallen)
wp = J(wparts, 'Plant_Wilted')
finish(wp, 'Plant_Wilted', 'ClayProps')

# bloom: lush arching leaves and four bright flowers
bparts = pot('pb')
for k in range(14):
    yaw = k * 2 * math.pi / 14 + random.uniform(-0.2, 0.2)
    lf = leaf('bl', random.uniform(0.15, 0.2), 0.05, math.radians(random.uniform(60, 82)), math.radians(random.uniform(-10, 20)), yaw,
              base=(0, 0, 0.15), fold=0.35)
    L.assign(lf, leaf_mat if k % 2 else leaf_mat2)
    bparts.append(lf)
for k in range(4):
    yaw = k * 2 * math.pi / 4 + 0.4
    h = random.uniform(0.29, 0.33)
    top = Vector((math.cos(yaw) * 0.06, math.sin(yaw) * 0.06, h))
    st = L.curve_tube('st', [(0, 0, 0.15), (math.cos(yaw) * 0.025, math.sin(yaw) * 0.025, 0.15 + (h - 0.15) * 0.6), top], radius=0.005)
    L.apply_all(st); L.assign(st, stem_mat); bparts.append(st)
    flower(top, petal_mat if k % 2 else petal_mat2, 1.0, droop=0.25 * (1 if k % 2 else -1), parts=bparts)
bpl = J(bparts, 'Plant_Bloom')
finish(bpl, 'Plant_Bloom', 'ClayProps')

# ===================================================================== CATS
def blob(name, prims, voxel=0.006, smooth=6):
    objs = []
    for c, r, rot in prims:
        o = L.uv_sphere('cp', 1.0, loc=c, seg=32, rings=20, scale=r)
        o.rotation_euler = rot
        L.apply_all(o)
        objs.append(o)
    ob = L.join(objs, name)
    L.remesh(ob, voxel)
    sm = ob.modifiers.new('sm', 'SMOOTH'); sm.factor = 0.6; sm.iterations = smooth
    L.apply_all(ob)
    L.shade_smooth(ob)
    return ob


def ear(loc, rot, size=0.05):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=size * 0.6, radius2=0.0, depth=size)
    ob = L.mesh_from_bm(bm, 'ear')
    ob.scale = (1.0, 0.45, 1.0)
    ob.location = loc
    ob.rotation_euler = rot
    L.bevel_mod(ob, 0.006, 2, 30)
    L.subsurf(ob, 1)
    L.apply_all(ob)
    return ob


fur_m = M.fur('fur', space='world')
dark_m = L.simple_mat('CatDark', (0.03, 0.02, 0.02), 0.6)
pink_m = L.simple_mat('CatPink', (0.85, 0.45, 0.45), 0.6)

# sleeping cat: coiled body (ellipsoids along an arc), head tucked on the tail
prims = []
for k in range(7):
    a = math.radians(-40 + k * 40)
    prims.append(((math.cos(a) * 0.1, math.sin(a) * 0.12, 0.075 - 0.004 * k), (0.105 - 0.004 * k, 0.1, 0.075 - 0.003 * k), (0, 0, a)))
head_c = Vector((0.15, -0.13, 0.085))
prims.append((tuple(head_c), (0.075, 0.068, 0.06), (0, 0, 0.6)))
prims.append((tuple(head_c + Vector((0.035, -0.04, -0.012))), (0.035, 0.03, 0.026), (0, 0, 0.6)))  # muzzle
cs = blob('Cat', prims)
# tail wraps around the front
tail = L.curve_tube('tail', [(-0.16, 0.08, 0.04), (-0.17, -0.08, 0.035), (-0.05, -0.2, 0.035), (0.1, -0.22, 0.035), (0.2, -0.17, 0.035)],
                    radius=0.033, radii=[1.0, 1.0, 0.95, 0.85, 0.6])
L.apply_all(tail)
# paws
paws = [L.uv_sphere('paw', 1.0, loc=(0.07, -0.19, 0.03), seg=16, rings=10, scale=(0.035, 0.03, 0.022))]
earsS = [ear(head_c + Vector((0.0, 0.035, 0.06)), (0.3, 0.3, 0.6)), ear(head_c + Vector((0.06, -0.02, 0.055)), (-0.1, 0.5, 0.6))]
cat = J([cs, tail] + paws + earsS, 'Cat')
L.assign(cat, fur_m)
# closed eyes: dark curved strokes on the face
eyes = []
fwd = Vector((math.cos(0.6 - math.pi / 2), math.sin(0.6 - math.pi / 2), 0))  # head facing direction approx
for s in (-1, 1):
    side = Vector((math.cos(0.6), math.sin(0.6), 0)) * 0.03 * s
    c = head_c + fwd * 0.062 + side + Vector((0, 0, 0.012))
    e = L.curve_tube('ceye', [c - Vector((math.cos(0.6), math.sin(0.6), 0)) * 0.014, c + Vector((0, 0, -0.005)) + fwd * 0.004,
                              c + Vector((math.cos(0.6), math.sin(0.6), 0)) * 0.014], radius=0.0035)
    L.apply_all(e)
    eyes.append(e)
nose = L.uv_sphere('nose', 1.0, loc=head_c + fwd * 0.1 + Vector((0, 0, -0.005)), seg=10, rings=8, scale=(0.009, 0.006, 0.006))
L.apply_all(nose)
ce = J(eyes, 'cat_eyes'); L.assign(ce, dark_m)
L.assign(nose, pink_m)
cat = J([cat, ce, nose], 'Cat')
cat.data.transform(Matrix.Translation((-0.02, 0.04, 0)))
for v in cat.data.vertices:
    v.co.z = max(v.co.z, 0.0)
L.decimate(cat, 10000)
finish(cat, 'Cat', 'ClayProps')

# awake, sitting, annoyed
hc = Vector((0, -0.04, 0.33))
prims = [((0, 0.03, 0.09), (0.12, 0.13, 0.095), (0, 0, 0)),          # haunches
         ((0, -0.01, 0.19), (0.09, 0.085, 0.12), (0.25, 0, 0)),      # chest
         (tuple(hc), (0.085, 0.075, 0.07), (0, 0, 0)),               # head
         (tuple(hc + Vector((0, -0.06, -0.022))), (0.04, 0.03, 0.03), (0, 0, 0)),   # muzzle
         ((0.035, -0.08, 0.06), (0.025, 0.03, 0.06), (0, 0, 0)), ((-0.035, -0.08, 0.06), (0.025, 0.03, 0.06), (0, 0, 0)),  # forelegs
         ((0.035, -0.1, 0.018), (0.028, 0.035, 0.02), (0, 0, 0)), ((-0.035, -0.1, 0.018), (0.028, 0.035, 0.02), (0, 0, 0)),  # front paws
         ((0.09, -0.03, 0.03), (0.04, 0.07, 0.03), (0, 0, 0)), ((-0.09, -0.03, 0.03), (0.04, 0.07, 0.03), (0, 0, 0))]  # hind feet
ca = blob('Cat_Awake', prims, voxel=0.005)
tail = L.curve_tube('tail2', [(0.0, 0.14, 0.03), (0.1, 0.1, 0.025), (0.13, -0.04, 0.025), (0.07, -0.13, 0.025), (-0.02, -0.15, 0.03)],
                    radius=0.03, radii=[1.0, 1.0, 0.9, 0.8, 0.6])
L.apply_all(tail)
# ears flattened sideways (annoyed "airplane ears")
earsA = [ear(hc + Vector((0.065, 0.0, 0.045)), (0.0, math.radians(70), 0.1), 0.06), ear(hc + Vector((-0.065, 0.0, 0.045)), (0.0, math.radians(-70), -0.1), 0.06)]
cat2 = J([ca, tail] + earsA, 'Cat_Awake')
L.assign(cat2, fur_m)
eye_m = L.simple_mat('CatEye', (0.75, 0.85, 0.12), 0.25)
parts = []
for s in (-1, 1):
    ec = hc + Vector((s * 0.033, -0.062, 0.012))
    e = L.uv_sphere('eye', 1.0, loc=ec, seg=20, rings=12, scale=(0.02, 0.012, 0.016))
    L.apply_all(e); L.assign(e, eye_m); parts.append(e)
    pu = L.uv_sphere('pupil', 1.0, loc=ec + Vector((0, -0.0105, -0.002)), seg=12, rings=8, scale=(0.004, 0.003, 0.011))
    L.apply_all(pu); L.assign(pu, dark_m); parts.append(pu)
    # heavy, slanted upper eyelid (annoyed), fur coloured
    lid = L.uv_sphere('lid', 1.0, loc=ec + Vector((0, -0.002, 0.009)), seg=20, rings=12, scale=(0.024, 0.016, 0.012))
    lid.rotation_euler = (0, s * 0.35, 0)
    L.apply_all(lid); L.assign(lid, fur_m); parts.append(lid)
nose = L.uv_sphere('nose', 1.0, loc=hc + Vector((0, -0.093, -0.012)), seg=10, rings=8, scale=(0.01, 0.006, 0.007))
L.apply_all(nose); L.assign(nose, pink_m); parts.append(nose)
cat2 = J([cat2] + parts, 'Cat_Awake')
for v in cat2.data.vertices:
    v.co.z = max(v.co.z, 0.0)
L.decimate(cat2, 10000)
finish(cat2, 'Cat_Awake', 'ClayProps')

# ===================================================================== BROOM
stick = L.cylinder('stick', 0.018, 1.05, loc=(0, 0, 0.2), verts=12, bevel=0.006)
L.displace_noise(stick, 0.004, 0.1)
L.apply_all(stick)
L.assign(stick, M.wood('wood_stick', base=(0.42, 0.26, 0.12), axis='Z', space='world', ring_scale=12))
bristle = L.lathe('bristle', [(0.0, 0.0), (0.11, 0.0), (0.09, 0.08), (0.055, 0.18), (0.03, 0.26), (0.0, 0.27)], steps=36)
L.apply_all(bristle)
bristle.scale = (1.0, 0.55, 1.0)
L.apply_all(bristle)
L.displace_noise(bristle, 0.01, 0.03)
L.apply_all(bristle)
straw = L.new_mat('straw')[0]
_, t = straw, L.NT(straw)
P = t.geom().outputs['Position']
wv = t.node('ShaderNodeTexWave'); wv.wave_type = 'BANDS'; wv.bands_direction = 'X'
t.set_in(wv, 'Vector', t.vmath('MULTIPLY', P, (1, 2, 0.05))); t.set_in(wv, 'Scale', 60); t.set_in(wv, 'Distortion', 3)
colr = t.ramp(wv.outputs['Fac'], [(0.2, (0.45, 0.32, 0.1)), (0.8, (0.85, 0.68, 0.3))])
t.principled(color=colr, rough=0.8, normal=t.bump(wv.outputs['Fac'], 0.5, 0.004))
L.assign(bristle, straw)
band = L.cylinder('band', 0.045, 0.04, loc=(0, 0, 0.23), verts=20, bevel=0.008)
band.scale = (1, 0.7, 1)
L.apply_all(band)
L.assign(band, M.cloth('rope', (0.55, 0.12, 0.08), scale=3))
broom = J([stick, bristle, band], 'Broom')
finish(broom, 'Broom', 'WoodProps')

# ===================================================================== DUST PILE
dp = L.uv_sphere('DustPile', 1.0, loc=(0, 0, 0), seg=40, rings=20, scale=(0.22, 0.18, 0.08))
L.apply_all(dp)
L.displace_noise(dp, 0.03, 0.06, depth=3)
L.apply_all(dp)
bm = bmesh.new(); bm.from_mesh(dp.data)
bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0), plane_no=(0, 0, 1), clear_inner=True)
bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary])
bm.to_mesh(dp.data); bm.free()
fluff = [dp]
for k in range(7):
    a = random.uniform(0, 6.28); r = random.uniform(0.18, 0.3)
    f = L.uv_sphere('fl', 1.0, loc=(math.cos(a) * r, math.sin(a) * r * 0.9, 0.012), seg=10, rings=6, scale=(0.03, 0.025, 0.015))
    L.apply_all(f); fluff.append(f)
dpo = J(fluff, 'DustPile')
L.shade_smooth(dpo)
L.assign(dpo, M.flat('dust', (0.30, 0.28, 0.27), 0.95, 0.35, 70, 0.6))
finish(dpo, 'DustPile', 'WoodProps')

# ===================================================================== SCROLL
roll = L.lathe('roll', [(0.0, -0.17), (0.05, -0.17), (0.055, -0.16), (0.052, 0.0), (0.055, 0.16), (0.05, 0.17), (0.0, 0.17)], steps=32)
L.apply_all(roll)
spiral = L.curve_tube('spiral', [(0, 0, 0)], radius=0.001)
bpy.data.objects.remove(spiral)
L.assign(roll, M.pages('parchment', base=(0.86, 0.76, 0.55), axis='X'))
knobs = []
for s in (-1, 1):
    k = L.lathe('knob', [(0.0, 0.0), (0.02, 0.0), (0.03, 0.012), (0.02, 0.03), (0.026, 0.045), (0.0, 0.05)], steps=20)
    L.apply_all(k)
    if s < 0:
        k.data.transform(Matrix.Scale(-1, 4, (0, 0, 1)))
        k.data.flip_normals()
    k.location = (0, 0, s * 0.17)
    L.apply_all(k)
    L.assign(k, M.wood('wood_knob', base=(0.3, 0.15, 0.07), axis='Z', space='world'))
    knobs.append(k)
rib = L.lathe('ribbon', [(0.054, -0.02), (0.058, -0.018), (0.058, 0.018), (0.054, 0.02)], steps=32)
L.apply_all(rib)
tie = L.curve_tube('tie', [(0.0, -0.055, 0.0), (0.03, -0.08, -0.02), (0.06, -0.1, -0.05)], radius=0.008)
tie.data.bevel_depth = 0.0; tie.data.extrude = 0.012
L.apply_all(tie)
rmat = M.cloth('ribbon', (0.65, 0.08, 0.06), scale=3)
L.assign(rib, rmat); L.assign(tie, rmat)
scr = J([roll] + knobs + [rib, tie], 'Scroll')
scr.data.transform(Matrix.Rotation(math.pi / 2, 4, 'Y'))
scr.data.transform(Matrix.Translation((0, 0, 0.056)))
L.shade_smooth(scr, 50)
finish(scr, 'Scroll', 'WoodProps')

# ===================================================================== GOLD: letters + star
def gold_letter(name, ch):
    ob = L.text_mesh(name, ch, 1.0, 0.07, bevel=0.025, font=L.HEB_FONT, bevel_res=3, offset=0.012)
    # normalise to 0.45 tall, centre origin
    L.set_active(ob)
    bb = [Vector(c) for c in ob.bound_box]
    h = max(v.z for v in [] ) if False else (max(c.y for c in bb) - min(c.y for c in bb))
    s = 0.45 / h
    ob.data.transform(Matrix.Scale(s, 4))
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    ob.location = (0, 0, 0)
    # stand up, face -Y (glTF +Z)
    ob.data.transform(Matrix.Rotation(math.pi / 2, 4, 'X'))
    L.shade_smooth(ob, 35)
    L.assign(ob, gold)
    PROPS[name] = ob
    return ob


for nm, ch in (('Letter_Alef', 'א'), ('Letter_Mem', 'מ'), ('Letter_Tav', 'ת')):
    gold_letter(nm, ch)


def star(name, R=0.15, r=0.068, depth=0.06):
    bm = bmesh.new()
    pts = []
    for i in range(10):
        a = math.pi / 2 + i * math.pi / 5
        rr = R if i % 2 == 0 else r
        pts.append(bm.verts.new((math.cos(a) * rr, math.sin(a) * rr, 0)))
    f = bm.faces.new(pts)
    c = bmesh.ops.poke(bm, faces=[f])
    centre = c['verts'][0]
    centre.co.z = depth * 0.5   # pillow the face
    # mirror back side
    ob = L.mesh_from_bm(bm, name)
    mir = ob.modifiers.new('m', 'MIRROR'); mir.use_axis = (False, False, True); mir.use_clip = True
    L.apply_all(ob)
    L.bevel_mod(ob, 0.01, 3, 20)
    L.apply_all(ob)
    ob.data.transform(Matrix.Rotation(math.pi / 2, 4, 'X'))
    zmin = min(v.co.z for v in ob.data.vertices)
    ob.data.transform(Matrix.Translation((0, 0, -zmin)))
    L.shade_smooth(ob, 30)
    L.assign(ob, gold)
    PROPS[name] = ob
    return ob


star('Star', R=0.2, r=0.1, depth=0.11)

# ===================================================================== BAKE ATLASES
layout_names = list(PROPS.keys())
spacing = 1.6
for i, nm in enumerate(layout_names):
    PROPS[nm].location = ((i % 6) * spacing, (i // 6) * spacing, 0)
for owner, ob in LATE:
    ob.location = PROPS[owner].location
bpy.context.view_layer.update()

for grp, objs in BAKE_GROUPS.items():
    if not objs:
        continue
    L.smart_uv(objs, island_margin=0.004, angle=55)
    L.pack_uv(objs, margin=0.004)
    m = L.bake_pbr(objs, grp, ATLAS, 'props_' + grp.lower(), samples=24, ao_strength=0.45, aux_res=ATLAS // 2)
    L.rename_mat(m, grp)

# ===================================================================== SHATTER JUG (after bake: shards share the jug atlas)
jug = PROPS['Jug']
jug_loc = jug.location.copy()
seeds = [Vector((0.12, -0.1, 0.1)), Vector((-0.12, -0.08, 0.14)), Vector((0.02, 0.14, 0.12)), Vector((0.05, -0.05, 0.36)), Vector((-0.1, 0.1, 0.3))]
for i, sd in enumerate(seeds):
    sh = jug.copy(); sh.data = jug.data.copy(); L.link_obj(sh)
    bm = bmesh.new(); bm.from_mesh(sh.data)
    for j, o in enumerate(seeds):
        if j == i:
            continue
        mid = (sd + o) / 2
        n = (o - sd).normalized()
        res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=mid, plane_no=n, clear_outer=True)
        edges = [e for e in bm.edges if e.is_boundary]
        try:
            bmesh.ops.holes_fill(bm, edges=edges, sides=0)
        except Exception:
            pass
    bm.to_mesh(sh.data); bm.free()
    nm = f'JugShard_{i + 1}'
    sh.name = nm; sh.data.name = nm + '_mesh'
    # origin at own centre
    vs = [v.co for v in sh.data.vertices]
    if not vs:
        continue
    c = sum(vs, Vector()) / len(vs)
    sh.data.transform(Matrix.Translation(-c))
    sh.location = jug_loc + c
    sh['rest_offset'] = list(c)
    PROPS[nm] = sh

# ===================================================================== JOIN LATE PIECES, FLAME
for owner, ob in LATE:
    tgt = PROPS[owner]
    if ob.data.uv_layers.active is None:
        ob.data.uv_layers.new(name=tgt.data.uv_layers[0].name)
    L.select([tgt, ob]); bpy.context.view_layer.objects.active = tgt
    bpy.ops.object.join()
fl.location = PROPS['Candle'].location + Vector(FLAME_POS)
fl.parent = PROPS['Candle']
fl.matrix_parent_inverse = PROPS['Candle'].matrix_world.inverted()
bpy.context.view_layer.update()
L.set_active(fl)
fl.matrix_parent_inverse.identity()
fl.location = FLAME_POS

# report
names = ['Tile_A', 'Tile_B', 'Tile_C', 'TileGoal', 'Block_Books', 'Block_Crate', 'Block_Stone', 'Candle', 'Pedestal', 'Jug'] + \
        [f'JugShard_{i}' for i in range(1, 6)] + ['Plant_Wilted', 'Plant_Bloom', 'Letter_Alef', 'Letter_Mem', 'Letter_Tav', 'Cat', 'Cat_Awake',
                                                  'Broom', 'DustPile', 'Scroll', 'Star']
info = {}
for nm in names:
    ob = PROPS[nm]
    ws = [ob.matrix_world @ v.co for v in ob.data.vertices]
    mn = Vector([min(w[i] for w in ws) for i in range(3)]); mx = Vector([max(w[i] for w in ws) for i in range(3)])
    sz = mx - mn
    info[nm] = {'tris': L.tri_count(ob) + (L.tri_count(fl) if nm == 'Candle' else 0),
                'size_xyz_gltf': [round(sz.x, 3), round(sz.z, 3), round(sz.y, 3)],
                'materials': [s.material.name for s in ob.material_slots]}
    print('PROP', nm, info[nm])
import json
json.dump(info, open(os.path.join(L.BLEND_DIR, 'props_info.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(L.BLEND_DIR, 'props_layout.blend'))

# contact sheet render (layout positions)
L.ground(30, (0.06, 0.06, 0.07), z=-0.2)
L.studio_lights(scale=2.6)
cx = 2.5 * spacing; cy = 2 * spacing
for o in bpy.data.objects:
    if o.type == 'LIGHT':
        o.location.x += cx; o.location.y += cy - 1.0
for i in range(1, 6):
    sh = PROPS[f'JugShard_{i}']
    off = Vector(sh['rest_offset']); off.z = 0
    sh.location = sh.location + off.normalized() * 0.25 + Vector((0.0, -0.7, -sh.location.z + 0.08))
cam = L.camera('Sheet', (2.5 * spacing, -5.5, 8.5), (2.5 * spacing, 3.6, 0.0), lens=30)
L.render(os.path.join(L.PREVIEW_DIR, 'props_sheet.png'), (1600, 1000), 64 if FAST else 160, cam)

# close-up of the small character props
for nm, x in (('Cat', -3.3), ('Cat_Awake', -2.65), ('Plant_Wilted', -2.1), ('Plant_Bloom', -1.65), ('Candle', -1.2), ('Star', -0.8)):
    for o in L.descendants(PROPS[nm])[:1]:
        o.location = (x, -2.0, 0.0)
cam2 = L.camera('Close', (-2.2, -3.75, 0.85), (-2.2, -2.0, 0.17), lens=50)
L.render(os.path.join(L.PREVIEW_DIR, 'props_closeup.png'), (1400, 700), 64 if FAST else 160, cam2)

# move to origin for export (shards keep their rest offset relative to the jug)
for nm in names:
    ob = PROPS[nm]
    if nm.startswith('JugShard'):
        ob.location = Vector(ob['rest_offset'])
    else:
        ob.location = (0, 0, 0)
bpy.context.view_layer.update()
exp = []
for nm in names:
    exp += L.descendants(PROPS[nm])
L.export_glb(os.path.join(L.MODELS_DIR, 'props.glb'), exp)
