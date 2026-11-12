"""Build the static workshop environment (bake source) -> blender/workshop_src.blend + preview renders.
Blender coords: X right, Y = back (game -Z), Z up. Back wall at y=+7.5, side walls x=+-8, front wall y=-14."""
import bpy, bmesh, math, os, sys, random, json
from mathutils import Vector, Matrix, Euler
sys.path.insert(0, os.path.dirname(__file__))
import importlib, lib_common as L, lib_mats as M, lib_set as S
importlib.reload(L); importlib.reload(M); importlib.reload(S)

FAST = '--fast' in sys.argv
NORENDER = '--norender' in sys.argv
random.seed(3)
R = S.R
L.reset_scene()

BACK_Y, SIDE_X, FRONT_Y, CEIL = 7.5, 8.0, -14.0, 8.5
CLEAR_R = 5.5

STATIC = {'Dais': [], 'Room': [], 'Furn': [], 'Clutter': []}
WEIGHT = {}
EMIT = []          # objects (named Emit_*)
LIGHTS = []        # dicts
FLAMES = []        # small flame meshes -> joined into Emit_Flames_* groups
GLASS = []         # lantern glass


def add(objs, atlas, w=1.0):
    if not isinstance(objs, (list, tuple)):
        objs = [objs]
    for o in objs:
        if o is None:
            continue
        o = L.apply_all(o)
        STATIC[atlas].append(o)
        WEIGHT[o.name] = w


def light(name, kind, pos, color, power, radius=0.1, direction=None, size=None, export=True, angle=None):
    ob = L.light(name, kind, pos, power, color, size=(angle if kind == 'SUN' else (size if kind == 'AREA' and size else radius)))
    if direction is not None:
        d = Vector(direction).normalized()
        ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if export:
        LIGHTS.append({'name': name, 'type': kind, 'pos': list(pos), 'color': list(color), 'power': power,
                       'radius': radius, 'direction': list(Vector(direction).normalized()) if direction is not None else None})
    return ob


# =============================================================== MATERIALS (bake sources)
def wallstone():
    m, t = L.new_mat('wallstone')
    g = t.geom()
    P = g.outputs['Position']
    N = g.outputs['Normal']
    sp = t.node('ShaderNodeSeparateXYZ', i_Vector=P)
    sn = t.node('ShaderNodeSeparateXYZ', i_Vector=N)
    v_side = t.node('ShaderNodeCombineXYZ', i_X=sp.outputs['Y'], i_Y=sp.outputs['Z']).outputs[0]
    v_back = t.node('ShaderNodeCombineXYZ', i_X=sp.outputs['X'], i_Y=sp.outputs['Z']).outputs[0]
    v_top = t.node('ShaderNodeCombineXYZ', i_X=sp.outputs['X'], i_Y=sp.outputs['Y']).outputs[0]
    f1 = t.math('GREATER_THAN', t.math('ABSOLUTE', sn.outputs['X']), 0.6)
    f2 = t.math('GREATER_THAN', t.math('ABSOLUTE', sn.outputs['Z']), 0.6)
    mv = t.node('ShaderNodeMix'); mv.data_type = 'VECTOR'
    t.set_in(mv, 'Factor', f1)
    t.link(v_back, [s for s in mv.inputs if s.name == 'A' and s.type == 'VECTOR'][0])
    t.link(v_side, [s for s in mv.inputs if s.name == 'B' and s.type == 'VECTOR'][0])
    mv2 = t.node('ShaderNodeMix'); mv2.data_type = 'VECTOR'
    t.set_in(mv2, 'Factor', f2)
    t.link([s for s in mv.outputs if s.type == 'VECTOR'][0], [s for s in mv2.inputs if s.name == 'A' and s.type == 'VECTOR'][0])
    t.link(v_top, [s for s in mv2.inputs if s.name == 'B' and s.type == 'VECTOR'][0])
    uv = [s for s in mv2.outputs if s.type == 'VECTOR'][0]
    dn = t.noise(P, 1.2, 2, 0.5)
    sd = t.vmath('SCALE', dn.outputs['Color'], None); sd.node.inputs['Scale'].default_value = 0.06
    uvd = t.vmath('ADD', uv, sd)
    br = t.node('ShaderNodeTexBrick')
    t.set_in(br, 'Vector', uvd)
    br.offset = 0.5
    br.offset_frequency = 2
    t.set_in(br, 'Scale', 1.0)
    br.inputs['Brick Width'].default_value = 0.78
    br.inputs['Row Height'].default_value = 0.36
    br.inputs['Mortar Size'].default_value = 0.022
    br.inputs['Mortar Smooth'].default_value = 0.4
    br.inputs['Bias'].default_value = 0.0
    br.inputs['Color1'].default_value = (0.21, 0.18, 0.15, 1)
    br.inputs['Color2'].default_value = (0.14, 0.13, 0.125, 1)
    br.inputs['Mortar'].default_value = (0.07, 0.065, 0.06, 1)
    n2 = t.noise(P, 6, 6, 0.6)
    vary = t.maprange(n2.outputs['Fac'], 0.3, 0.7, 0.8, 1.15)
    col = t.mix(1.0, br.outputs['Color'], t.node('ShaderNodeCombineColor', i_Red=vary, i_Green=vary, i_Blue=vary).outputs[0], 'MULTIPLY')
    # plaster on the upper wall, flaking off in patches
    pn = t.noise(P, 0.9, 5, 0.6)
    plaster = t.math('MULTIPLY', t.maprange(sp.outputs['Z'], 3.2, 4.4, 0.0, 0.85), t.maprange(pn.outputs['Fac'], 0.38, 0.5, 0.0, 1.0))
    plaster = t.math('MULTIPLY', plaster, t.math('SUBTRACT', 1.0, f2))
    pcol = t.ramp(t.noise(P, 3, 4, 0.5).outputs['Fac'], [(0.3, (0.24, 0.22, 0.19)), (0.7, (0.30, 0.27, 0.22))])
    col = t.mix(plaster, col, pcol)
    # damp, darker base of the wall
    damp = t.maprange(sp.outputs['Z'], 0.0, 0.7, 0.45, 0.0)
    col = t.mix(damp, col, (0.10, 0.10, 0.09))
    h = t.math('ADD', t.math('MULTIPLY', br.outputs['Fac'], -0.8), t.math('MULTIPLY', n2.outputs['Fac'], 0.5))
    h = t.math('ADD', h, t.math('MULTIPLY', plaster, 0.6))
    t.principled(color=col, rough=0.9, normal=t.bump(h, 0.8, 0.02))
    return m


def flagstone(name='floorstone', bw=1.1, rh=0.85, c1=(0.18, 0.16, 0.14), c2=(0.125, 0.118, 0.11), polar=False):
    m, t = L.new_mat(name)
    g = t.geom()
    P = g.outputs['Position']
    sp = t.node('ShaderNodeSeparateXYZ', i_Vector=P)
    if polar:
        r = t.math('SQRT', t.math('ADD', t.math('MULTIPLY', sp.outputs['X'], sp.outputs['X']), t.math('MULTIPLY', sp.outputs['Y'], sp.outputs['Y'])))
        a = t.math('ARCTAN2', sp.outputs['X'], sp.outputs['Y'])
        ring = t.math('FLOOR', t.math('DIVIDE', r, rh))
        rr = t.math('MULTIPLY', t.math('ADD', ring, 0.5), rh)
        u = t.math('MULTIPLY', a, rr)
        uv = t.node('ShaderNodeCombineXYZ', i_X=u, i_Y=r).outputs[0]
    else:
        uv = t.node('ShaderNodeCombineXYZ', i_X=sp.outputs['X'], i_Y=sp.outputs['Y']).outputs[0]
    br = t.node('ShaderNodeTexBrick')
    t.set_in(br, 'Vector', uv)
    br.offset = 0.5
    t.set_in(br, 'Scale', 1.0)
    br.inputs['Brick Width'].default_value = bw
    br.inputs['Row Height'].default_value = rh
    br.inputs['Mortar Size'].default_value = 0.025
    br.inputs['Mortar Smooth'].default_value = 0.5
    br.inputs['Color1'].default_value = (*c1, 1)
    br.inputs['Color2'].default_value = (*c2, 1)
    br.inputs['Mortar'].default_value = (0.07, 0.065, 0.06, 1)
    n2 = t.noise(P, 4, 6, 0.6)
    vary = t.maprange(n2.outputs['Fac'], 0.3, 0.7, 0.8, 1.15)
    col = t.mix(1.0, br.outputs['Color'], t.node('ShaderNodeCombineColor', i_Red=vary, i_Green=vary, i_Blue=vary).outputs[0], 'MULTIPLY')
    cv = t.voronoi(P, 1.5, 'DISTANCE_TO_EDGE')
    crack = t.math('MULTIPLY', t.maprange(cv.outputs['Distance'], 0.0, 0.01, 1.0, 0.0),
                   t.maprange(t.noise(P, 1.1, 2, 0.5).outputs['Fac'], 0.55, 0.6, 0.0, 1.0))
    col = t.mix(crack, col, (0.05, 0.05, 0.05))
    wear = t.maprange(t.noise(P, 0.5, 3, 0.5).outputs['Fac'], 0.5, 0.7, 0.0, 0.25)
    col = t.mix(wear, col, (0.26, 0.23, 0.19))
    h = t.math('ADD', t.math('MULTIPLY', br.outputs['Fac'], -1.0), t.math('MULTIPLY', n2.outputs['Fac'], 0.3))
    h = t.math('SUBTRACT', h, crack)
    t.principled(color=col, rough=0.85, normal=t.bump(h, 0.7, 0.015))
    return m


WALL = wallstone()
FLOOR = flagstone()
DAIS = flagstone('daisstone', bw=1.0, rh=0.62, c1=(0.15, 0.16, 0.18), c2=(0.11, 0.12, 0.14), polar=True)
TRIM = M.stone('stoneTrim', base=(0.25, 0.22, 0.19), dark=(0.14, 0.13, 0.12), warm=(0.30, 0.26, 0.21), scale=1.5, moss=0.25)
S.MATS['stoneTrim'] = TRIM
CURB = M.stone('curbstone', base=(0.22, 0.21, 0.21), dark=(0.12, 0.12, 0.13), warm=(0.28, 0.26, 0.24), scale=1.8, moss=0.3)

# =============================================================== FLOOR, DAIS, CURB
bm = bmesh.new()
step = 0.25
nx, ny = int(2 * SIDE_X / step), int((BACK_Y - FRONT_Y) / step)
bmesh.ops.create_grid(bm, x_segments=nx, y_segments=ny, size=0.5)
for v in bm.verts:
    v.co.x = v.co.x * 2 * SIDE_X
    v.co.y = FRONT_Y + (v.co.y + 0.5) * (BACK_Y - FRONT_Y)
dead = [f for f in bm.faces if f.calc_center_median().to_2d().length < 5.25]
bmesh.ops.delete(bm, geom=dead, context='FACES')
for v in bm.verts:   # snap the hole rim to exactly r = 5.5 (hidden under the curb stones, nothing left inside the clear circle)
    r = v.co.to_2d().length
    if 1e-6 < r < 5.5:
        v.co.x *= 5.5 / r
        v.co.y *= 5.5 / r
floor = L.mesh_from_bm(bm, 'Floor')
L.assign(floor, FLOOR)
far = floor.copy(); far.data = floor.data.copy(); L.link_obj(far); far.name = 'FloorFar'
for ob, keep_far in ((floor, False), (far, True)):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    kill = [f for f in bm.faces if (f.calc_center_median().y < -3.0) != keep_far]
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    bm.to_mesh(ob.data); bm.free()
add(floor, 'Room', 1.0)
add(far, 'Room', 0.25)

# dais disc (top exactly at z = -0.2)
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, segments=128, radius=5.04)
bmesh.ops.triangulate(bm, faces=bm.faces)
for v in bm.verts:
    v.co.z = -0.2
dais = L.mesh_from_bm(bm, 'Dais')
L.assign(dais, DAIS)
add(dais, 'Dais', 1.0)

# curb ring of bevelled stones r 5.0..5.55, z -0.2..0.02
nseg = 40
for i in range(nseg):
    a0 = 2 * math.pi * i / nseg + 0.004
    a1 = 2 * math.pi * (i + 1) / nseg - 0.004
    bm = bmesh.new()
    ring = []
    for a in [a0 + (a1 - a0) * k / 4 for k in range(5)]:
        for r in (5.0, 5.56):
            for z in (-0.21, 0.02 + R.uniform(-0.006, 0.006)):
                ring.append(bm.verts.new((math.cos(a) * r, math.sin(a) * r, z)))
    bmesh.ops.convex_hull(bm, input=ring)
    o = L.mesh_from_bm(bm, 'curb')
    L.bevel_mod(o, 0.03, 2, 30)
    L.assign(o, CURB)
    add(o, 'Dais', 1.0)

# =============================================================== WALLS
WIN_X, WIN_W, WIN_SILL, WIN_SPRING = -4.62, 2.9, 0.85, 4.0
WIN_R = WIN_W / 2


def keep_faces(ob, keep_fn):
    bm = bmesh.new(); bm.from_mesh(ob.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if not keep_fn(f)], context='FACES')
    bm.to_mesh(ob.data); bm.free()


def split_z(ob, z, w_low, w_high, atlas='Room'):
    hi = ob.copy(); hi.data = ob.data.copy(); L.link_obj(hi)
    for o, low in ((ob, True), (hi, False)):
        bm = bmesh.new(); bm.from_mesh(o.data)
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, z), plane_no=(0, 0, 1),
                               clear_outer=low, clear_inner=not low)
        bm.to_mesh(o.data); bm.free()
    add(ob, atlas, w_low)
    add(hi, atlas, w_high)


def subdiv_box(name, xr, yr, zr, cuts=8):
    o = L.box(name, (xr[1] - xr[0], yr[1] - yr[0], zr[1] - zr[0]), loc=((xr[0] + xr[1]) / 2, (yr[0] + yr[1]) / 2, (zr[0] + zr[1]) / 2), bevel=0)
    L.apply_all(o)
    return o


back = subdiv_box('BackWall', (-SIDE_X - 0.8, SIDE_X + 0.8), (BACK_Y, BACK_Y + 0.8), (-0.3, CEIL + 0.3))
# arched window cutter
bm = bmesh.new()
pts = [(WIN_X - WIN_R, WIN_SILL), (WIN_X + WIN_R, WIN_SILL)]
for k in range(25):
    a = math.pi * k / 24
    pts.append((WIN_X + math.cos(a) * WIN_R, WIN_SPRING + math.sin(a) * WIN_R))
vs = [bm.verts.new((x, BACK_Y - 0.5, z)) for x, z in pts]
f = bm.faces.new(vs)
ext = bmesh.ops.extrude_face_region(bm, geom=[f])
bmesh.ops.translate(bm, verts=[e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)], vec=(0, 2.0, 0))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
cutter = L.mesh_from_bm(bm, 'wincut')
b = back.modifiers.new('win', 'BOOLEAN'); b.object = cutter; b.operation = 'DIFFERENCE'; b.solver = 'EXACT'
L.apply_all(back)
bpy.data.objects.remove(cutter)
keep_faces(back, lambda f: f.normal.y < -0.5 or (abs(f.normal.y) < 0.5 and f.calc_center_median().y < BACK_Y + 0.79
                                                   and abs(f.calc_center_median().x - WIN_X) < WIN_R + 0.05 and f.calc_center_median().z < CEIL))
L.assign(back, WALL)
split_z(back, 3.0, 1.0, 0.45)

for sx in (-1, 1):
    w = subdiv_box('SideWall', (sx * SIDE_X if sx > 0 else -SIDE_X - 0.8, SIDE_X + 0.8 if sx > 0 else -SIDE_X), (FRONT_Y - 0.5, BACK_Y + 0.5), (-0.3, CEIL + 0.3))
    keep_faces(w, lambda f, sx=sx: f.normal.x * sx < -0.5)
    L.assign(w, WALL)
    # front part of the side walls is rarely seen: separate it for lower texel density
    wf = w.copy(); wf.data = w.data.copy(); L.link_obj(wf)
    for o, keep_front in ((w, False), (wf, True)):
        bm = bmesh.new(); bm.from_mesh(o.data)
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, -2.0, 0), plane_no=(0, 1, 0),
                               clear_outer=keep_front, clear_inner=not keep_front)
        bm.to_mesh(o.data); bm.free()
    split_z(w, 3.0, 0.9, 0.4)
    add(wf, 'Room', 0.25)

fw = subdiv_box('FrontWall', (-SIDE_X - 0.5, SIDE_X + 0.5), (FRONT_Y - 0.8, FRONT_Y), (-0.3, CEIL + 0.3))
keep_faces(fw, lambda f: f.normal.y > 0.5)
L.assign(fw, WALL)
add(fw, 'Room', 0.15)

ceil = subdiv_box('Ceiling', (-SIDE_X - 0.5, SIDE_X + 0.5), (FRONT_Y - 0.5, BACK_Y + 0.5), (CEIL, CEIL + 0.3))
keep_faces(ceil, lambda f: f.normal.z < -0.5)
L.assign(ceil, S.mat('darkwoodY'))
add(ceil, 'Room', 0.15)

# ceiling beams (all above camera height: never block the view)
for y in (-11.5, -8.0, -4.5, -1.0, 2.5, 6.0):
    add(S.bx((2 * SIDE_X, 0.38, 0.45), (0, y, CEIL - 0.225), 'darkwood', bevel=0.03), 'Room', 0.3)
for x in (-4.0, 4.0):
    add(S.bx((0.3, BACK_Y - FRONT_Y, 0.3), (x, (BACK_Y + FRONT_Y) / 2, CEIL - 0.6), 'darkwoodY', bevel=0.03), 'Room', 0.2)

# pilasters with capitals, blind arches
def pilaster(x, y, axis, h=6.0, w=0.6, dep=0.32):
    parts = []
    if axis == 'back':
        parts.append(S.bx((w, dep, h), (x, y - dep / 2, h / 2), TRIM, bevel=0.04, segs=3))
        parts.append(S.bx((w + 0.16, dep + 0.1, 0.25), (x, y - (dep + 0.1) / 2, h + 0.12), TRIM, bevel=0.04))
        parts.append(S.bx((w + 0.12, dep + 0.08, 0.35), (x, y - (dep + 0.08) / 2, 0.17), TRIM, bevel=0.04))
    else:
        s = 1 if x > 0 else -1
        parts.append(S.bx((dep, w, h), (x - s * dep / 2, y, h / 2), TRIM, bevel=0.04, segs=3))
        parts.append(S.bx((dep + 0.1, w + 0.16, 0.25), (x - s * (dep + 0.1) / 2, y, h + 0.12), TRIM, bevel=0.04))
        parts.append(S.bx((dep + 0.08, w + 0.12, 0.35), (x - s * (dep + 0.08) / 2, y, 0.17), TRIM, bevel=0.04))
    return parts


for x in (-2.35, 2.35, -6.95):
    add(pilaster(x, BACK_Y, 'back', h=6.2), 'Room', 0.8)
for sx in (-1, 1):
    for y in (-8.5, -4.2, 0.2, 5.2):
        add(pilaster(sx * SIDE_X, y, 'side', h=6.2), 'Room', 0.6 if y > -2 else 0.25)
    # blind arches between side pilasters
    for y0, y1 in ((-8.5, -4.2), (-4.2, 0.2), (0.2, 5.2)):
        c = ((y0 + y1) / 2)
        r = (y1 - y0) / 2 - 0.3
        add(S.voussoir_arch((sx * SIDE_X, c, 6.2 - r * 0.0 + 0.0), r, 0.42, 0.18, 13, plane='YZ', facing=-sx, m='stoneTrim'),
            'Room', 0.5 if y1 > 0 else 0.2)
# arch over the back bookcase
add(S.voussoir_arch((0, BACK_Y, 4.75), 2.0, 0.42, 0.2, 13, plane='XZ', facing=-1, m='stoneTrim'), 'Room', 0.6)

# =============================================================== WINDOW
add(S.voussoir_arch((WIN_X, BACK_Y, WIN_SPRING), WIN_R + 0.02, 0.4, 0.2, 11, plane='XZ', facing=-1, m='stoneTrim'), 'Room', 0.9)
for sx in (-1, 1):  # jamb quoins
    z = WIN_SILL
    k = 0
    while z < WIN_SPRING - 0.05:
        hh = min(0.42, WIN_SPRING - z)
        ww = 0.42 if k % 2 == 0 else 0.3
        add(S.bx((ww, 0.2, hh - 0.025), (WIN_X + sx * (WIN_R + ww / 2), BACK_Y - 0.1, z + hh / 2), TRIM, bevel=0.03), 'Room', 0.9)
        z += hh
        k += 1
add(S.bx((WIN_W + 0.9, 0.55, 0.16), (WIN_X, BACK_Y - 0.05, WIN_SILL - 0.08), TRIM, bevel=0.035), 'Room', 1.0)    # sill
add(S.bx((WIN_W + 0.6, 0.12, 0.3), (WIN_X, BACK_Y - 0.28, WIN_SILL - 0.3), TRIM, bevel=0.03), 'Room', 1.0)
# leaded lattice: mullion, transom and thin bars, clipped to the arch
GY = BACK_Y + 0.42
bars = []


def arch_top(x):
    dx = abs(x - WIN_X)
    if dx >= WIN_R:
        return WIN_SPRING
    return WIN_SPRING + math.sqrt(WIN_R * WIN_R - dx * dx)


for k in range(-4, 5):
    x = WIN_X + k * WIN_R / 4.5
    th = 0.09 if k == 0 else 0.035
    top = arch_top(x)
    bars.append(S.bx((th, 0.06 if k == 0 else 0.04, top - WIN_SILL), (x, GY, (top + WIN_SILL) / 2), 'iron', bevel=0.008))
zz = WIN_SILL + 0.3
while zz < WIN_SPRING + WIN_R - 0.1:
    dz = zz - WIN_SPRING
    half = WIN_R if dz <= 0 else math.sqrt(max(0.0, WIN_R * WIN_R - dz * dz))
    th = 0.08 if abs(zz - (WIN_SPRING - 0.1)) < 0.16 else 0.035
    bars.append(S.bx((2 * half, 0.045, th), (WIN_X, GY, zz), 'iron', bevel=0.008))
    zz += 0.33
for o in bars:
    o.visible_shadow = True
add(bars, 'Room', 0.8)

# window glass: emissive night sky (moon, stars), does not cast shadows so moonlight passes
bm = bmesh.new()
vs = [bm.verts.new((x, GY + 0.05, z)) for x, z in pts]
bm.faces.new(vs)
glass = L.mesh_from_bm(bm, 'Emit_Window')
gm, t = L.new_mat('Emit_WindowSky')
P = t.geom().outputs['Position']
sp = t.node('ShaderNodeSeparateXYZ', i_Vector=P)
sky = t.ramp(t.maprange(sp.outputs['Z'], WIN_SILL, WIN_SPRING + WIN_R, 0, 1),
             [(0.0, (0.20, 0.36, 0.62)), (0.45, (0.08, 0.16, 0.42)), (1.0, (0.03, 0.06, 0.20))])
st = t.voronoi(t.vmath('MULTIPLY', P, (1, 1, 1)), 9.0, 'F1')
star = t.maprange(st.outputs['Distance'], 0.0, 0.06, 1.0, 0.0)
star = t.math('MULTIPLY', star, t.maprange(t.noise(P, 4, 2, 0.5).outputs['Fac'], 0.5, 0.6, 0.0, 1.0))
sky = t.mix(star, sky, (0.9, 0.95, 1.0))
moon_c = Vector((WIN_X + 0.45, GY, WIN_SPRING + 0.55))
dm = t.vmath('DISTANCE', P, tuple(moon_c))
moon = t.maprange(dm, 0.27, 0.29, 1.0, 0.0)
halo = t.maprange(dm, 0.28, 0.9, 0.35, 0.0)
mc = t.mix(t.maprange(t.noise(P, 14, 3, 0.5).outputs['Fac'], 0.4, 0.6, 0.0, 0.25), (1.0, 0.97, 0.88), (0.75, 0.78, 0.8))
sky = t.mix(halo, sky, (0.55, 0.7, 0.95))
sky = t.mix(moon, sky, mc)
t.principled(color=(0, 0, 0), rough=1.0, emit=sky, emit_strength=1.5)
L.assign(glass, gm)
glass.visible_shadow = False
EMIT.append(glass)

# moonlight + window sky fill
MOON_DIR = Vector((0.38, -0.86, -0.62)).normalized()
light('Light_Moon', 'SUN', (WIN_X, BACK_Y - 0.2, WIN_SPRING), (0.42, 0.6, 1.0), 9.0, direction=MOON_DIR, angle=math.radians(1.2))
wa = L.light('WindowFill', 'AREA', (WIN_X, BACK_Y + 0.2, (WIN_SILL + WIN_SPRING + WIN_R) / 2), 520, (0.28, 0.42, 1.0))
wa.data.shape = 'RECTANGLE'; wa.data.size = WIN_W; wa.data.size_y = WIN_SPRING + WIN_R - WIN_SILL
wa.rotation_euler = Vector((0.15, -1, -0.15)).to_track_quat('-Z', 'Y').to_euler()

# =============================================================== KILN (back right)
KC = Vector((5.35, 6.05, 0.0))
KROT = -math.radians(38)
kparts = []
plat = S.bx((3.0, 2.6, 0.38), (0, 0, 0.19), TRIM, bevel=0.05, segs=3)
kparts.append(plat)
dome = L.lathe('dome', [(0.0, 0.38), (1.25, 0.38), (1.3, 0.6), (1.28, 1.1), (1.15, 1.6), (0.9, 2.05), (0.55, 2.35), (0.42, 2.45), (0.0, 2.45)], steps=40)
L.apply_all(dome)
# mouth cutter (arched)
bm = bmesh.new()
mp = [(-0.45, 0.42), (0.45, 0.42)] + [(math.cos(math.pi * k / 16) * 0.45, 0.95 + math.sin(math.pi * k / 16) * 0.45) for k in range(17)]
vs = [bm.verts.new((x, -2.0, z)) for x, z in mp]
f = bm.faces.new(vs)
ext = bmesh.ops.extrude_face_region(bm, geom=[f])
bmesh.ops.translate(bm, verts=[e for e in ext['geom'] if isinstance(e, bmesh.types.BMVert)], vec=(0, 1.5, 0))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
mc_ob = L.mesh_from_bm(bm, 'mouthcut')
b = dome.modifiers.new('m', 'BOOLEAN'); b.object = mc_ob; b.operation = 'DIFFERENCE'; b.solver = 'EXACT'
L.apply_all(dome)
bpy.data.objects.remove(mc_ob)
L.assign(dome, S.mat('brick'))
kparts.append(dome)
kparts += S.voussoir_arch((0, -1.2, 0.95), 0.47, 0.22, 0.12, 9, plane='XZ', facing=-1, m='stoneTrim')
chim = S.cyl(0.42, CEIL - 2.3, (0, 0.25, 2.3), 'brick', verts=20, bevel=0.02, r2=0.34)
kparts.append(chim)
kparts.append(S.cyl(0.5, 0.18, (0, 0.25, 2.35), TRIM, verts=20, bevel=0.03))
# soot inside the mouth + ember bed
inner = S.bx((0.86, 0.9, 0.04), (0, -0.75, 0.42), 'soot', bevel=0.01)
kparts.append(inner)
for o in kparts:
    L.apply_all(o)
    o.data.transform(Matrix.Rotation(KROT, 4, 'Z'))
    o.data.transform(Matrix.Translation(KC))
add(kparts, 'Room', 0.9)
# emissive fire: ember bed + flame tongues (Emit_)
fire = []
eb = L.uv_sphere('ember', 1.0, loc=(0, -0.75, 0.45), seg=24, rings=10, scale=(0.4, 0.35, 0.08))
fire.append(eb)
for k in range(5):
    fx = R.uniform(-0.25, 0.25)
    fl = L.lathe('tongue', [(0, 0), (0.07, 0.05), (0.08, 0.15), (0.05, 0.3), (0.0, 0.42 + R.uniform(-0.1, 0.1))], loc=(fx, -0.7 + R.uniform(-0.1, 0.15), 0.46), steps=10)
    fire.append(fl)
for o in fire:
    L.apply_all(o)
    o.data.transform(Matrix.Rotation(KROT, 4, 'Z'))
    o.data.transform(Matrix.Translation(KC))
fire_ob = L.join(fire, 'Emit_KilnFire')
fm = L.emissive_mat('Emit_Fire', (1.0, 0.42, 0.08), 9.0, base=(1.0, 0.5, 0.1))
L.assign(fire_ob, fm)
fire_ob.visible_shadow = False
EMIT.append(fire_ob)
mouth_dir = Vector((0, -1, 0)); mouth_dir.rotate(Euler((0, 0, KROT)))
fire_pos = KC + Vector((0, -0.6, 0.75)).copy()
fp = Vector((0, -0.6, 0.75)); fp.rotate(Euler((0, 0, KROT))); fire_pos = KC + fp
light('Light_Fire', 'POINT', tuple(fire_pos), (1.0, 0.42, 0.12), 900, radius=0.35)
fo = Vector((0, -1.35, 0.85)); fo.rotate(Euler((0, 0, KROT)))
light('KilnGlowOut', 'POINT', tuple(KC + fo), (1.0, 0.45, 0.15), 260, radius=0.4, export=False)
# logs + tools near kiln
add(S.logs((3.25, 6.85, 0.0), 6, rotz=math.radians(90)), 'Clutter', 0.8)
add(S.barrel((3.45, 5.75, 0.0), h=0.55, r=0.24), 'Clutter', 0.8)   # water bucket-ish tub
for k, (dx, dy) in enumerate(((-0.6, -0.5), (0.5, -0.7), (0.9, 0.3))):
    p = Vector((dx, dy, 0)); p.rotate(Euler((0, 0, KROT)))
    for part in S.jar((KC.x + p.x, KC.y + p.y, 0.38), scale=1.3, m='clay'):
        add(part, 'Clutter', 0.7)
poker = L.curve_tube('poker', [(6.9, 4.9, 0.02), (6.95, 5.0, 0.8), (6.97, 5.05, 1.25)], radius=0.015)
L.assign(poker, S.mat('iron')); add(poker, 'Clutter', 0.5)

# =============================================================== WORKBENCH (back centre)
WB_Y, WB_H = 6.5, 0.95
wb = []
wb.append(S.bx((3.6, 1.0, 0.13), (0, WB_Y, WB_H - 0.065), 'wood', bevel=0.03, segs=3))
for sx in (-1, 1):
    for sy in (-1, 1):
        wb.append(S.bx((0.16, 0.16, WB_H - 0.13), (sx * 1.6, WB_Y + sy * 0.38, (WB_H - 0.13) / 2), 'darkwoodZ', bevel=0.025))
    wb.append(S.bx((0.12, 0.85, 0.1), (sx * 1.6, WB_Y, 0.25), 'darkwoodY', bevel=0.02))
wb.append(S.bx((3.2, 0.1, 0.1), (0, WB_Y, 0.25), 'darkwood', bevel=0.02))
wb.append(S.bx((3.3, 0.85, 0.05), (0, WB_Y, 0.32), 'wood', bevel=0.015))
wb.append(S.bx((0.5, 0.95, 0.22), (1.15, WB_Y, WB_H - 0.24), 'darkwood', bevel=0.02))   # drawer
wb.append(S.cyl(0.035, 0.04, (1.15, WB_Y - 0.5, WB_H - 0.24), 'brass', rot=(math.pi / 2, 0, 0), verts=10, bevel=0.005))
add(wb, 'Furn', 1.0)
T = WB_H
clut = []
# big lump of clay + half-finished figurine on a turntable
clut.append(S.cyl(0.32, 0.05, (-0.15, WB_Y - 0.05, T), 'darkwood', verts=24, bevel=0.012))
clut += S.clay_figure((-0.15, WB_Y - 0.05, T + 0.05), 1.6, wet=True)
lump = L.uv_sphere('lump', 1.0, loc=(-0.85, WB_Y + 0.15, T + 0.1), seg=24, rings=14, scale=(0.24, 0.2, 0.14))
L.displace_noise(lump, 0.03, 0.08); L.assign(lump, S.mat('claywet')); clut.append(lump)
# tools
for k in range(4):
    tl = S.bx((0.24, 0.025, 0.012), (-0.5 + k * 0.06, WB_Y - 0.35, T + 0.008), 'wood', rot=(0, 0, 0.3 + k * 0.2), bevel=0.005)
    clut.append(tl)
clut.append(S.bx((0.3, 0.04, 0.04), (0.35, WB_Y - 0.3, T + 0.02), 'darkwood', rot=(0, 0, -0.4), bevel=0.01))   # mallet handle
clut.append(S.cyl(0.06, 0.16, (0.25, WB_Y - 0.2, T + 0.06), 'darkwood', rot=(0, math.pi / 2, -0.4), verts=12, bevel=0.01))
# open book (two tilted page blocks) + quill + ink
for s in (-1, 1):
    pg = S.bx((0.34, 0.46, 0.035), (0.75 + s * 0.17, WB_Y - 0.1, T + 0.03), 'pages', rot=(0, s * -0.08, 0.1), bevel=0.01)
    clut.append(pg)
clut.append(S.bx((0.72, 0.5, 0.02), (0.75, WB_Y - 0.1, T + 0.01), 'cover0', rot=(0, 0, 0.1), bevel=0.006))
clut.append(S.cyl(0.04, 0.06, (1.25, WB_Y + 0.15, T), 'ink', verts=12, bevel=0.01))
quill = L.curve_tube('quill', [(1.25, WB_Y + 0.15, T + 0.05), (1.3, WB_Y + 0.2, T + 0.2), (1.38, WB_Y + 0.28, T + 0.35)], radius=0.02, radii=[0.2, 1.0, 0.4])
L.assign(quill, S.mat('white')); clut.append(quill)
# books, jars, scrolls, hourglass
for k in range(3):
    clut.append(S.bx((0.36 - k * 0.04, 0.28 - k * 0.02, 0.07), (1.45, WB_Y + 0.2, T + 0.035 + k * 0.07), 'cover%d' % (k + 3), rot=(0, 0, 0.2 * k), bevel=0.008))
for p in ((-1.3, WB_Y + 0.3), (-1.45, WB_Y + 0.05), (-1.15, WB_Y + 0.35)):
    clut += S.jar((p[0], p[1], T), scale=0.8)
clut += S.scroll((-0.4, WB_Y + 0.32, T + 0.04), 0.4, 0.04, rotz=0.4)
clut += S.scroll((-0.5, WB_Y + 0.4, T + 0.04), 0.35, 0.035, rotz=0.1)
hg = [S.cyl(0.07, 0.025, (0.45, WB_Y + 0.3, T), 'darkwood', verts=12), S.cyl(0.07, 0.025, (0.45, WB_Y + 0.3, T + 0.24), 'darkwood', verts=12)]
hg.append(S.lathe([(0.0, 0.0), (0.055, 0.02), (0.06, 0.06), (0.012, 0.11), (0.06, 0.16), (0.055, 0.2), (0.0, 0.215)], (0.45, WB_Y + 0.3, T + 0.025), 'glass_amber', steps=16))
clut += hg
add(clut, 'Clutter', 1.0)
# workbench candles + turquoise potion (accent)
wl = []
for p, h in (((-1.6, WB_Y - 0.25), 0.22), ((-1.45, WB_Y - 0.32), 0.14), ((1.6, WB_Y - 0.3), 0.18)):
    add(S.candle((p[0], p[1], T), h, 0.035, FLAMES, wl, 18), 'Clutter', 1.0)
for i, (p, pw) in enumerate(wl):
    light(f'Light_Candle_{i + 1}', 'POINT', p, (1.0, 0.6, 0.25), pw, radius=0.04)
potion = S.lathe([(0.0, 0.0), (0.09, 0.0), (0.11, 0.06), (0.1, 0.14), (0.04, 0.18), (0.03, 0.27), (0.0, 0.27)], (0.15, WB_Y + 0.3, T), 'glass_teal', steps=20)
L.apply_all(potion)
pot_glow = L.uv_sphere('Emit_Potion', 1.0, loc=(0.15, WB_Y + 0.3, T + 0.08), seg=16, rings=10, scale=(0.095, 0.095, 0.075))
L.apply_all(pot_glow)
L.assign(pot_glow, L.emissive_mat('Emit_Magic', (0.05, 1.0, 0.75), 5.0, base=(0.05, 0.5, 0.4)))
pot_glow.visible_shadow = False
EMIT.append(pot_glow)
light('Light_Magic_1', 'POINT', (0.15, WB_Y + 0.15, T + 0.25), (0.1, 1.0, 0.8), 25, radius=0.08)
cork = S.cyl(0.035, 0.04, (0.15, WB_Y + 0.3, T + 0.26), 'wood', verts=10)
add(cork, 'Clutter', 0.6)

# rug under the bench and stool
rug = S.bx((4.6, 1.5, 0.02), (0, 6.45, 0.01), 'rug', bevel=0.008)
add(rug, 'Furn', 1.0)
stool = [S.cyl(0.24, 0.07, (0.9, 5.82, 0.5), 'wood', verts=20, bevel=0.02)]
for k in range(3):
    a = k * 2 * math.pi / 3 + 0.3
    stool.append(S.bx((0.06, 0.06, 0.52), (0.9 + math.cos(a) * 0.15, 5.82 + math.sin(a) * 0.15, 0.25), 'darkwoodZ', bevel=0.012,
                      rot=(math.sin(a) * 0.12, -math.cos(a) * 0.12, 0)))
add(stool, 'Furn', 0.9)

# =============================================================== BOOKCASES
def bookcase(x0, x1, wall, depth, height, shelves, weight=1.0, kind='books', crown=True):
    """wall: ('back', y_face) or ('left'/'right', x_face). Fills shelves with books, jars, scrolls, figures."""
    side, face = wall
    parts = []

    def P(u, d, z):  # u along the wall, d distance from wall face, z
        if side == 'back':
            return (u, face - d, z)
        s = 1 if side == 'right' else -1
        return (face - s * d, u, z)

    def SZ(lu, ld, lz):
        return (lu, ld, lz) if side == 'back' else (ld, lu, lz)

    L_ = x1 - x0
    um = (x0 + x1) / 2
    parts.append(S.bx(SZ(L_, 0.04, height), P(um, 0.02, height / 2), 'darkwood' if side == 'back' else 'darkwoodY', bevel=0.01))
    for u in (x0 + 0.04, x1 - 0.04):
        parts.append(S.bx(SZ(0.08, depth, height), P(u, depth / 2, height / 2), 'darkwoodZ', bevel=0.02))
    zs = [0.0] + list(shelves) + [height]
    for z in shelves:
        parts.append(S.bx(SZ(L_ - 0.1, depth - 0.04, 0.05), P(um, depth / 2, z), 'wood' if side == 'back' else 'woodY', bevel=0.012))
    parts.append(S.bx(SZ(L_ + 0.1, depth + 0.1, 0.12), P(um, (depth + 0.1) / 2, height + 0.06), 'darkwood' if side == 'back' else 'darkwoodY', bevel=0.03))
    parts.append(S.bx(SZ(L_, depth, 0.12), P(um, depth / 2, 0.06), 'darkwood' if side == 'back' else 'darkwoodY', bevel=0.02))
    items = []
    for i, z in enumerate(shelves):
        top = zs[i + 2] - z - 0.06
        u = x0 + 0.1
        while u < x1 - 0.2:
            seg = R.uniform(0.35, 0.9)
            seg = min(seg, x1 - 0.1 - u)
            r = R.random()
            if kind == 'jars':
                r = r * 0.5 + 0.5 if R.random() < 0.7 else r
            if r < 0.55:
                if side == 'back':
                    items += S.book_row(u, u + seg, face - depth * 0.5, z + 0.025, depth * 0.8, top * 0.55, top * 0.92, axis='X', facing=-1)
                else:
                    sgn = 1 if side == 'right' else -1
                    items += S.book_row(u, u + seg, face - sgn * depth * 0.5, z + 0.025, depth * 0.8, top * 0.55, top * 0.92, axis='Y',
                                        facing=-sgn)
            elif r < 0.85:
                n = max(1, int(seg / 0.2))
                for k in range(n):
                    sc = min(top / 0.32, R.uniform(0.6, 1.2))
                    items += S.jar(P(u + (k + 0.5) * seg / n, depth * 0.45 + R.uniform(-0.05, 0.05), z + 0.025), scale=sc)
            elif r < 0.93:
                for k in range(R.randint(2, 4)):
                    items += S.scroll(P(u + seg / 2 + R.uniform(-0.1, 0.1), depth * 0.5, z + 0.07 + k * 0.07), min(seg, 0.4), 0.035,
                                      rotz=(0 if side == 'back' else math.pi / 2) + R.uniform(-0.2, 0.2))
            else:
                items += S.clay_figure(P(u + seg / 2, depth * 0.45, z + 0.025), min(1.4, top / 0.3), rotz=0)
            u += seg + 0.03
    return parts, items


bp, bi = bookcase(-1.95, 1.95, ('back', BACK_Y), 0.45, 4.3, [0.7, 1.45, 2.2, 2.95, 3.65])
add(bp, 'Furn', 0.9); add(bi, 'Clutter', 0.8)
lp, li = bookcase(0.6, 4.8, ('left', -SIDE_X), 0.45, 4.6, [0.6, 1.35, 2.1, 2.85, 3.6])
add(lp, 'Furn', 0.8); add(li, 'Clutter', 0.6)
rp, ri = bookcase(0.6, 4.2, ('right', SIDE_X), 0.45, 4.0, [0.55, 1.25, 1.95, 2.65, 3.35], kind='jars')
add(rp, 'Furn', 0.8); add(ri, 'Clutter', 0.6)
# front side walls: lower shelves (seen in env/orbit)
lp2, li2 = bookcase(-3.8, -0.4, ('left', -SIDE_X), 0.4, 2.2, [0.6, 1.3], weight=0.4)
add(lp2, 'Furn', 0.4); add(li2, 'Clutter', 0.3)
rp2, ri2 = bookcase(-3.8, -0.4, ('right', SIDE_X), 0.4, 1.4, [0.7], kind='jars')
add(rp2, 'Furn', 0.4); add(ri2, 'Clutter', 0.3)

# turquoise glowing potion jars on the shelves (accent colour)
MAGIC = L.emissive_mat('Emit_Magic', (0.05, 1.0, 0.75), 5.0, base=(0.05, 0.5, 0.4))
for i, (p, sc_) in enumerate((((-1.25, BACK_Y - 0.22, 1.475), 0.9), ((-SIDE_X + 0.22, 2.6, 2.125), 1.0), ((SIDE_X - 0.22, 1.6, 1.275), 0.9))):
    g = L.uv_sphere('Emit_MagicJar', 1.0, loc=(p[0], p[1], p[2] + 0.09 * sc_), seg=16, rings=10, scale=(0.09 * sc_, 0.09 * sc_, 0.09 * sc_))
    L.apply_all(g); L.assign(g, MAGIC); g.visible_shadow = False
    EMIT.append(g)
    add(S.cyl(0.04 * sc_, 0.06 * sc_, (p[0], p[1], p[2] + 0.17 * sc_), 'wood', verts=10, bevel=0.005), 'Clutter', 0.5)
    light(f'Light_Magic_{i + 2}', 'POINT', (p[0] + (0.25 if p[0] < -7 else -0.25 if p[0] > 7 else 0), p[1] - (0.25 if abs(p[0]) < 7 else 0), p[2] + 0.15),
          (0.1, 1.0, 0.8), 14, radius=0.08)

# wall chart above the left low shelves: parchment with the alef-bet and a golem sketch
chart = S.bx((0.03, 2.6, 1.6), (-SIDE_X + 0.03, -2.1, 3.3), 'parch', bevel=0.01)
add(chart, 'Furn', 0.5)
alefbet = 'אבגדהוזחטיכלמנסעפצקרשת'
ink = []
for i, ch in enumerate(alefbet):
    row, col = divmod(i, 11)
    tm = L.text_mesh('ab', ch, 0.17, 0.004, font=L.HEB_FONT)
    tm.rotation_euler = (math.pi / 2, 0, -math.pi / 2)
    tm.location = (-SIDE_X + 0.05, -2.1 + 1.1 - col * 0.22, 3.85 - row * 0.3)
    L.assign(tm, S.mat('ink'))
    ink.append(tm)
for k in range(3):   # circles of a sketched golem
    c = L.curve_tube('sk', [(-SIDE_X + 0.05, -2.1 + math.cos(a) * r, 2.95 + 0.1 * k + math.sin(a) * r * 1.2) for a, r in
                            [(t * 2 * math.pi / 24, 0.18 - 0.05 * k) for t in range(24)]], radius=0.006, closed=True)
    L.assign(c, S.mat('ink'))
    ink.append(c)
add(ink, 'Furn', 0.5)
# tool rack on the right front wall
rack = [S.bx((0.06, 2.6, 0.12), (SIDE_X - 0.03, -2.1, 2.6), 'darkwoodY', bevel=0.015)]
for k in range(7):
    y = -3.2 + k * 0.36
    rack.append(S.cyl(0.015, 0.12, (SIDE_X - 0.06, y, 2.62), 'darkwood', rot=(0, math.pi / 2, 0), verts=8, bevel=0))
    ln = R.uniform(0.35, 0.6)
    rack.append(S.bx((0.035, 0.035, ln), (SIDE_X - 0.1, y, 2.55 - ln / 2), 'woodZ', bevel=0.01))
    if k % 2:
        rack.append(S.bx((0.05, 0.14, 0.07), (SIDE_X - 0.1, y, 2.55 - ln), 'iron', bevel=0.012))
    else:
        rack.append(S.bx((0.03, 0.03, 0.16), (SIDE_X - 0.1, y, 2.55 - ln - 0.08), 'iron', bevel=0.006))
add(rack, 'Furn', 0.4)

# =============================================================== FLOOR CLUTTER (outside r=5.5)
# window corner: pottery wheel, amphorae, sacks of clay, old giant head
pw = [S.cyl(0.38, 0.07, (-6.0, 5.6, 0.5), 'darkwood', verts=28, bevel=0.02), S.cyl(0.08, 0.5, (-6.0, 5.6, 0.0), 'darkwoodZ', verts=12),
      S.cyl(0.45, 0.06, (-6.0, 5.6, 0.0), 'darkwood', verts=24, bevel=0.015)]
pw += S.clay_figure((-6.0, 5.6, 0.57), 1.2, wet=True)
add(pw, 'Furn', 0.9)
for p, sc in (((-7.35, 6.95), 2.6), ((-6.9, 7.1), 2.0), ((-7.45, 6.2), 2.2), ((-3.1, 7.05), 1.6), ((-5.6, 7.1), 1.8)):
    for part in S.jar((p[0], p[1], 0.0), scale=sc, kind=R.choice([0, 1, 4]), m=R.choice(['clay', 'glaze_teal', 'glaze_ochre', 'clay'])):
        add(part, 'Clutter', 0.9)
for p in ((-7.3, 3.9), (-6.85, 3.45), (-7.4, 3.1)):
    add(S.sack((p[0], p[1], 0.0), 1.1), 'Clutter', 0.8)
# extra clay sacks and a big storage jar where the old head was
for p in ((-7.2, 2.2), (-6.7, 1.8)):
    add(S.sack((p[0], p[1], 0.0), 1.2), 'Clutter', 0.6)
for part in S.jar((-7.25, 1.3, 0.0), scale=3.0, kind=1, m='glaze_teal'):
    add(part, 'Clutter', 0.6)
# kiln side: crates, barrel
add(S.crate((7.1, 4.2, 0.0), (0.7, 0.6, 0.5), rotz=0.2), 'Clutter', 0.7)
add(S.crate((7.15, 4.25, 0.5), (0.5, 0.45, 0.35), rotz=-0.15), 'Clutter', 0.7)
add(S.barrel((6.9, 3.2, 0.0)), 'Clutter', 0.7)
# by the bench: stacked books, crate, broom
z = 0.0
for k in range(5):
    hh = R.uniform(0.07, 0.11)
    add(S.bx((R.uniform(0.38, 0.5), R.uniform(0.3, 0.38), hh), (-2.55, 6.1, z + hh / 2), 'cover%d' % R.randrange(8), rot=(0, 0, R.uniform(-0.3, 0.3)),
             bevel=0.01), 'Clutter', 1.0)
    z += hh
add(S.crate((2.75, 6.75, 0.0), (0.6, 0.5, 0.45), rotz=-0.2), 'Clutter', 0.9)
broom = [S.cyl(0.02, 1.4, (1.95, 6.0, 0.0), 'woodZ', rot=(0.25, 0.0, 0), verts=8, bevel=0.005)]
add(broom, 'Clutter', 0.6)
# floor candle clusters around the dais edge (warm pools of light, visible from the game camera)
cl_i = len(wl)
for ci, (cx, cy) in enumerate(((-5.25, 3.55), (5.05, 3.45), (-3.0, 5.65), (3.05, 5.65), (-6.5, -1.2), (6.5, -1.3))):
    lst = []
    hs = [0.45, 0.32, 0.22, 0.15]
    for k, h in enumerate(hs):
        a = k * 2.1 + ci
        p = (cx + math.cos(a) * 0.13 * (k > 0), cy + math.sin(a) * 0.13 * (k > 0), 0.0)
        add(S.candle(p, h, 0.055 - k * 0.006, FLAMES, lst if k == 0 else None, 0), 'Clutter', 0.9)
    cl_i += 1
    light(f'Light_Candle_{cl_i}', 'POINT', (cx, cy, 0.62), (1.0, 0.58, 0.22), 45, radius=0.08)
# safety: nothing may intrude into the clear circle (except the dais itself)
for atlas in ('Room', 'Furn', 'Clutter'):
    for o in STATIC[atlas]:
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            if w.to_2d().length < CLEAR_R and w.z > -0.25 and w.z < CEIL - 0.7:
                print('CLEAR-CIRCLE VIOLATION', o.name, tuple(round(c, 2) for c in w))
                break

# =============================================================== LANTERNS
lantern_specs = [  # (hook position, wall/ceiling, wall point)
    ((-7.35, 0.2, 3.3), (-SIDE_X + 0.32, 0.2, 3.95)),
    ((7.35, 0.2, 3.3), (SIDE_X - 0.32, 0.2, 3.95)),
    ((-7.35, 5.2, 3.3), (-SIDE_X + 0.32, 5.2, 3.95)),
    ((7.35, 5.2, 3.3), (SIDE_X - 0.32, 5.2, 3.95)),
    ((-2.35, 6.65, 3.0), (-2.35, BACK_Y - 0.32, 3.65)),
    ((2.35, 6.65, 3.0), (2.35, BACK_Y - 0.32, 3.65)),
]
for i, (hook, wallp) in enumerate(lantern_specs):
    hx, hy, hz = hook
    parts = S.lantern((hx, hy, hz - 0.62), GLASS, 1.0)
    parts.append(L.curve_tube('hk', [(hx, hy, hz - 0.08), (hx, hy, hz + 0.02)], radius=0.008))
    L.assign(parts[-1], S.mat('iron'))
    side = Vector((1 if hx < 0 else -1, 0, 0)) if abs(hx) > 7 else Vector((0, -1, 0))
    parts += S.wall_bracket(wallp, (hx, hy, hz + 0.05), side)
    add(parts, 'Furn', 0.5)
    light(f'Light_Lantern_{i + 1}', 'POINT', (hx, hy, hz - 0.45), (1.0, 0.6, 0.26), 60, radius=0.1)
# hanging ceiling lanterns (high, near the back corners only)
for i, (x, y) in enumerate(((-5.9, 3.6), (6.1, 2.4))):
    parts = S.lantern((x, y, 4.2), GLASS, 1.3, hang=CEIL - 0.45)
    add(parts, 'Furn', 0.35)
    light(f'Light_Lantern_{len(lantern_specs) + i + 1}', 'POINT', (x, y, 4.45), (1.0, 0.6, 0.26), 90, radius=0.12)

# herbs drying on a rope across the back wall (high)
for k in range(9):
    x = -1.6 + k * 0.4
    hb = L.uv_sphere('herb', 1.0, loc=(x, 7.1, 5.0 - 0.15), seg=10, rings=8, scale=(0.09, 0.07, 0.2))
    L.displace_noise(hb, 0.03, 0.04); L.assign(hb, S.mat('herb'))
    add(hb, 'Clutter', 0.3)
add(L.curve_tube('rope', [(-1.9, 7.15, 5.1), (0, 7.1, 4.98), (1.9, 7.15, 5.1)], radius=0.012), 'Clutter', 0.3)
STATIC['Clutter'][-1].data.materials.append(S.mat('rope'))

# =============================================================== EMISSIVE GROUPS
fl = L.join(FLAMES, 'Emit_CandleFlames')
L.assign(fl, L.emissive_mat('Emit_Flame', (1.0, 0.6, 0.2), 10.0, base=(1.0, 0.7, 0.3)))
fl.visible_shadow = False
EMIT.append(fl)
gl = L.join(GLASS, 'Emit_LanternGlass')
L.assign(gl, L.emissive_mat('Emit_Lantern', (1.0, 0.6, 0.25), 4.0, base=(0.8, 0.5, 0.2)))
gl.visible_shadow = False
EMIT.append(gl)
# rune ring engraved in the dais: thin rings + the 22 letters, faint turquoise
rr = []
for r0, w in ((4.36, 0.022), (4.84, 0.022)):
    bpy.ops.mesh.primitive_torus_add(major_radius=r0, minor_radius=w, major_segments=160, minor_segments=6, location=(0, 0, -0.2))
    o = bpy.context.active_object
    o.scale = (1, 1, 0.25)
    L.apply_all(o)
    rr.append(o)
for i, ch in enumerate(alefbet):
    a = math.pi / 2 - i * 2 * math.pi / 22    # clockwise from the back; letter bases toward the centre
    tm = L.text_mesh('ring', ch, 0.42, 0.004, font=L.HEB_FONT, offset=0.012)
    tm.rotation_euler = (0, 0, a - math.pi / 2)
    tm.location = (math.cos(a) * 4.6, math.sin(a) * 4.6, -0.199)
    L.apply_all(tm)
    rr.append(tm)
runes = L.join(rr, 'Emit_DaisRunes')
L.assign(runes, L.emissive_mat('Emit_Rune', (0.05, 1.0, 0.78), 0.65, base=(0.02, 0.15, 0.13)))
runes.visible_shadow = False
EMIT.append(runes)

# soft overall fill so the board area is not black (very low, cool)
fill = L.light('BoardFill', 'AREA', (0, 0, CEIL - 0.6), 45, (0.35, 0.45, 0.85))
fill.data.size = 9
fill.rotation_euler = (0, 0, 0)
L.world_color((0.004, 0.007, 0.016), 1.0)
ff = L.light('FrontFill', 'AREA', (0, -12.0, 5.0), 900, (0.2, 0.34, 0.95))
ff.data.size = 10
ff.rotation_euler = Vector((0, 1, -0.35)).to_track_quat('-Z', 'Y').to_euler()

# =============================================================== STATS + SAVE
tot = 0
for a, objs in STATIC.items():
    n = sum(L.tri_count(o) for o in objs)
    tot += n
    print('ATLAS', a, len(objs), 'objects', n, 'tris')
et = sum(L.tri_count(o) for o in EMIT)
print('EMIT tris', et, 'TOTAL', tot + et)
meta = {'weights': WEIGHT, 'static': {a: [o.name for o in objs] for a, objs in STATIC.items()}, 'emit': [o.name for o in EMIT],
        'lights': LIGHTS}
json.dump(meta, open(os.path.join(L.BLEND_DIR, 'workshop_meta.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(L.BLEND_DIR, 'workshop_src.blend'))

if not NORENDER:
    sc = bpy.context.scene
    cam = L.camera('GameCam', (0, -9.5, 7.5), (0, 0, 0), fov=35)
    L.render(os.path.join(L.PREVIEW_DIR, 'workshop_src_gamecam.png'), (1280, 720), 64 if FAST else 256, cam)
    cam2 = L.camera('WideCam', (0, -7.5, 2.6), (0, 4, 2.0), lens=18)
    L.render(os.path.join(L.PREVIEW_DIR, 'workshop_src_wide.png'), (1280, 720), 64 if FAST else 256, cam2)
