"""Build the Golem: rigid parts hierarchy, baked clay atlas, glowing runes. -> public/models/golem.glb"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(__file__))
import importlib, lib_common as L, lib_runes as R
importlib.reload(L); importlib.reload(R)

random.seed(7)
FAST = '--fast' in sys.argv
ATLAS = 1024 if FAST else 2048

L.reset_scene()


# ------------------------------------------------------------------ shape kit
def ell(c, r, rot=(0, 0, 0), seg=40, rings=24):
    return ('ell', c, r, rot, seg, rings)


def cap(p0, p1, r0, r1=None):
    return ('cap', p0, p1, r0, r1 if r1 is not None else r0)


def mirror(prims):
    out = []
    for p in prims:
        if p[0] == 'ell':
            c = (-p[1][0], p[1][1], p[1][2])
            rot = (p[3][0], -p[3][1], -p[3][2])
            out.append(('ell', c, p[2], rot, p[4], p[5]))
        else:
            out.append(('cap', (-p[1][0], p[1][1], p[1][2]), (-p[2][0], p[2][1], p[2][2]), p[3], p[4]))
    return out


def build_prims(name, prims):
    objs = []
    for i, p in enumerate(prims):
        if p[0] == 'ell':
            o = L.uv_sphere(f'{name}_p{i}', 1.0, loc=p[1], seg=p[4], rings=p[5], scale=p[2])
            o.rotation_euler = p[3]
            objs.append(o)
        else:
            a, b, r0, r1 = Vector(p[1]), Vector(p[2]), p[3], p[4]
            n = max(3, int((b - a).length / (min(r0, r1) * 0.25)))
            for k in range(n + 1):
                t = k / n
                o = L.uv_sphere(f'{name}_c{i}_{k}', r0 + (r1 - r0) * t, loc=a.lerp(b, t), seg=32, rings=16)
                objs.append(o)
    for o in objs:
        L.set_active(o)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    ob = L.join(objs, name)
    return ob


def clay_part(name, prims, voxel=0.007, smooth=6, dents=True, cuts=(), flatten_bottom=False, target=None):
    ob = build_prims(name, prims)
    L.remesh(ob, voxel)
    sm = ob.modifiers.new('sm', 'SMOOTH')
    sm.factor = 0.6
    sm.iterations = smooth
    L.apply_all(ob, transforms=False)
    # low-frequency hand-shaped irregularity
    m, tex = L.displace_noise(ob, 0.010, 0.09, depth=2)
    if dents:
        vt = bpy.data.textures.new(name + '_dent', 'VORONOI')
        vt.distance_metric = 'DISTANCE'
        vt.noise_scale = 0.045
        vt.weight_1, vt.weight_2, vt.weight_3, vt.weight_4 = 1.0, 0.0, 0.0, 0.0
        vt.noise_intensity = 1.6
        vt.color_mode = 'INTENSITY'
        d = ob.modifiers.new('dent', 'DISPLACE')
        d.texture = vt
        d.texture_coords = 'GLOBAL'
        d.strength = 0.0055
        d.mid_level = 0.55
    L.apply_all(ob, transforms=False)
    sm = ob.modifiers.new('sm2', 'SMOOTH')
    sm.factor = 0.4
    sm.iterations = 1
    L.apply_all(ob, transforms=False)
    for c in cuts:  # chips / sockets: boolean difference with ellipsoids
        k = L.uv_sphere(name + '_cut', 1.0, loc=c[0], seg=c[3] if len(c) > 3 else 10, rings=c[4] if len(c) > 4 else 7, scale=c[1])
        k.rotation_euler = c[2]
        b = ob.modifiers.new('cut', 'BOOLEAN')
        b.operation = 'DIFFERENCE'
        b.object = k
        b.solver = 'EXACT'
        L.apply_all(ob, transforms=False)
        bpy.data.objects.remove(k)
    if flatten_bottom:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0.0), plane_no=(0, 0, 1),
                               clear_inner=True, clear_outer=False)
        edges = [e for e in bm.edges if e.is_boundary]
        bmesh.ops.holes_fill(bm, edges=edges, sides=0)
        bm.to_mesh(ob.data)
        bm.free()
    if target:
        L.decimate(ob, target)
    L.shade_smooth(ob)
    return ob


# ------------------------------------------------------------------ proportions (Blender: Z up, golem faces -Y)
SH = (0.255, 0.0, 1.0)     # left shoulder pivot (+X is the golem's left)
EL = (0.305, -0.02, 0.735)  # elbow
WR = (0.33, -0.05, 0.425)   # wrist
HIP = (0.13, 0.0, 0.36)

parts = {}

parts['Hips'] = clay_part('Hips', [
    ell((0, 0.0, 0.40), (0.21, 0.165, 0.12)),
    ell((0.12, 0, 0.36), (0.1, 0.1, 0.1)), ell((-0.12, 0, 0.36), (0.1, 0.1, 0.1)),
], voxel=0.008, target=4500)

torso_l = [
    ell((0.2, 0.025, 1.0), (0.155, 0.15, 0.135), (0, 0.25, 0)),          # shoulder mass
    ell((0.15, 0.03, 1.09), (0.12, 0.13, 0.11), (0, 0.35, 0)),          # trapezius hugging the head
    ell((0.27, 0.0, 1.07), (0.11, 0.12, 0.1)),                          # deltoid cap
    ell((0.11, -0.105, 0.90), (0.13, 0.1, 0.105)),                      # pec
    ell((0.17, 0.0, 0.70), (0.1, 0.14, 0.18)),                          # flank
]
parts['Torso'] = clay_part('Torso', [
    ell((0, 0.01, 0.78), (0.255, 0.215, 0.34)),
    ell((0, -0.055, 0.64), (0.205, 0.17, 0.2)),
    ell((0, 0.06, 1.03), (0.24, 0.15, 0.14)),                           # shoulder yoke rising behind the head
    ell((0, 0.0, 0.52), (0.2, 0.16, 0.1)),
    ell((0, -0.02, 1.08), (0.15, 0.13, 0.08)),                          # collar the head sinks into
] + torso_l + mirror(torso_l), voxel=0.008,
    target=22000)

# head: tiny, sunk between the shoulders
HZ = -0.04
HEAD_C = (0, -0.06, 1.195 + HZ)
parts['Head'] = clay_part('Head', [
    ell(HEAD_C, (0.13, 0.125, 0.135)),
    ell((0, -0.1, 1.27 + HZ), (0.1, 0.07, 0.06)),                                                   # broad forehead
    ell((0.07, -0.115, 1.145 + HZ), (0.06, 0.055, 0.045)), ell((-0.07, -0.115, 1.145 + HZ), (0.06, 0.055, 0.045)),   # cheeks
    ell((0, -0.03, 1.12 + HZ), (0.11, 0.1, 0.06)),                                                  # neck plug (hidden in torso)
    ell((0, -0.15, 1.152 + HZ), (0.022, 0.032, 0.024)),                                              # little nose bump
], voxel=0.0055,
    cuts=[((0.058, -0.185, 1.197 + HZ), (0.043, 0.036, 0.047), (0, 0, 0), 24, 16),
          ((-0.058, -0.185, 1.197 + HZ), (0.043, 0.036, 0.047), (0, 0, 0), 24, 16),
          ((0, -0.17, 1.115 + HZ), (0.052, 0.05, 0.016), (0, 0, 0), 24, 12)],
    target=11000)

parts['Jaw'] = clay_part('Jaw', [
    ell((0, -0.1, 1.095 + HZ), (0.08, 0.062, 0.028)),
    ell((0, -0.07, 1.10 + HZ), (0.09, 0.06, 0.03)),
], voxel=0.004, dents=False, target=3000)

for side, sx in (('L', 1), ('R', -1)):
    parts[f'Brow_{side}'] = clay_part(f'Brow_{side}', [
        cap((sx * 0.022, -0.18, 1.262 + HZ), (sx * 0.098, -0.162, 1.25 + HZ), 0.016, 0.012)], voxel=0.0035, dents=False, target=1500)


ARM_DX = -0.012


def shift(prims, dx):
    out = []
    for p in prims:
        if p[0] == 'ell':
            out.append(('ell', (p[1][0] + dx, p[1][1], p[1][2])) + tuple(p[2:]))
        else:
            out.append(('cap', (p[1][0] + dx, p[1][1], p[1][2]), (p[2][0] + dx, p[2][1], p[2][2]), p[3], p[4]))
    return out


def scale_prims(prims, centre, k):
    c = Vector(centre)
    out = []
    for p in prims:
        if p[0] == 'ell':
            out.append(('ell', tuple(c + (Vector(p[1]) - c) * k), tuple(r * k for r in p[2])) + tuple(p[3:]))
        else:
            out.append(('cap', tuple(c + (Vector(p[1]) - c) * k), tuple(c + (Vector(p[2]) - c) * k), p[3] * k, p[4] * k))
    return out


def side_prims(prims, sx):
    prims = shift(prims, ARM_DX)
    return prims if sx > 0 else mirror(prims)


for side, sx in (('L', 1), ('R', -1)):
    up = [ell(SH, (0.1, 0.1, 0.1)), cap((SH[0] + 0.005, -0.005, 0.98), (EL[0], EL[1], EL[2] + 0.01), 0.088, 0.074)]
    parts[f'Arm{side}_Upper'] = clay_part(f'Arm{side}_Upper', side_prims(up, sx), voxel=0.007, target=5000)
    lo = [ell(EL, (0.08, 0.08, 0.08)),
          cap(EL, (WR[0], WR[1], WR[2] + 0.02), 0.085, 0.112),
          ell((0.322, -0.045, 0.55), (0.118, 0.115, 0.125)),           # popeye forearm
          ell((0.335, -0.052, 0.455), (0.105, 0.1, 0.05)),            # cuff
          ]
    parts[f'Arm{side}_Lower'] = clay_part(f'Arm{side}_Lower', side_prims(lo, sx), voxel=0.007,
                                          target=8000)
    hand = [ell((0.336, -0.06, 0.325), (0.085, 0.125, 0.11)),
            ell(WR, (0.08, 0.09, 0.065))]
    for i, yy in enumerate((-0.135, -0.06, 0.015)):
        ln = 0.1 if i == 1 else 0.088
        hand.append(cap((0.342, yy, 0.27), (0.336, yy - 0.015 + 0.008 * i, 0.27 - ln), 0.046, 0.043))
    hand.append(cap((0.295, -0.13, 0.35), (0.262, -0.185, 0.28), 0.045, 0.04))   # thumb (front, inner)
    hand = scale_prims(hand, (WR[0], WR[1] - 0.01, WR[2]), 1.18)
    parts[f'Hand{side}'] = clay_part(f'Hand{side}', side_prims(hand, sx), voxel=0.006, target=7000)
    leg = [ell(HIP, (0.11, 0.11, 0.11)),
           cap(HIP, (HIP[0] + 0.01, -0.01, 0.14), 0.112, 0.122),
           ell((0.14, -0.045, 0.065), (0.13, 0.165, 0.08)),
           ell((0.08, -0.19, 0.045), (0.042, 0.04, 0.04)), ell((0.14, -0.205, 0.045), (0.045, 0.042, 0.042)),
           ell((0.20, -0.19, 0.045), (0.04, 0.04, 0.04))]
    parts[f'Leg{side}'] = clay_part(f'Leg{side}', side_prims(leg, sx), voxel=0.007, flatten_bottom=True, target=6000)

# ------------------------------------------------------------------ clay material (procedural, baked later)
def clay_material():
    m, t = L.new_mat('ClayProc')
    g = t.geom()
    P = g.outputs['Position']
    N = g.outputs['Normal']
    base_n = t.noise(P, 2.6, 3, 0.5)
    col = t.ramp(base_n.outputs['Fac'], [(0.3, (0.30, 0.13, 0.055)), (0.55, (0.43, 0.21, 0.085)), (0.75, (0.54, 0.33, 0.14))])
    mott = t.noise(P, 14, 6, 0.6)
    mf = t.maprange(mott.outputs['Fac'], 0.3, 0.7, 0.86, 1.1)
    col = t.mix(1.0, col, t.node('ShaderNodeCombineColor', i_Red=mf, i_Green=mf, i_Blue=mf).outputs[0], 'MULTIPLY')
    # finger dents
    dv = t.voronoi(P, 26, 'SMOOTH_F1')
    dent = t.maprange(dv.outputs['Distance'], 0.0, 0.55, 0.0, 1.0)
    # drag streaks
    sv = t.vmath('MULTIPLY', P, (9, 9, 2.2))
    streak = t.noise(sv, 1.0, 5, 0.65).outputs['Fac']
    # cracks
    distort = t.noise(P, 9, 3, 0.5)
    sdist = t.vmath('SCALE', distort.outputs['Color'], None)
    sdist.node.inputs['Scale'].default_value = 0.05
    pc = t.vmath('ADD', P, sdist)
    cv = t.voronoi(pc, 6.0, 'DISTANCE_TO_EDGE')
    crack = t.maprange(cv.outputs['Distance'], 0.0, 0.016, 1.0, 0.0)
    cmask = t.maprange(t.noise(P, 2.2, 2, 0.5, ).outputs['Fac'], 0.52, 0.6, 0.0, 1.0)
    crack = t.math('MULTIPLY', crack, cmask)
    # moss on up-facing areas
    up = t.node('ShaderNodeSeparateXYZ', i_Vector=N).outputs['Z']
    upm = t.maprange(up, 0.35, 0.8, 0.0, 1.0)
    mn = t.noise(P, 5, 8, 0.7)
    mossm = t.math('MULTIPLY', upm, t.maprange(mn.outputs['Fac'], 0.56, 0.62, 0.0, 1.0))
    mosscol = t.ramp(t.noise(P, 60, 2, 0.5).outputs['Fac'], [(0.3, (0.12, 0.22, 0.05)), (0.7, (0.30, 0.42, 0.09))])
    # pointiness edge wear (lighter) and cavity (darker)
    pt = g.outputs['Pointiness']
    edge = t.maprange(pt, 0.5, 0.58, 0.0, 1.0)
    col = t.mix(t.math('MULTIPLY', edge, 0.35), col, (0.66, 0.46, 0.28))
    cav = t.maprange(pt, 0.42, 0.49, 1.0, 0.0)
    col = t.mix(t.math('MULTIPLY', cav, 0.4), col, (0.22, 0.12, 0.08))
    # dirt on feet
    z = t.node('ShaderNodeSeparateXYZ', i_Vector=P).outputs['Z']
    dirt = t.maprange(z, 0.02, 0.2, 0.55, 0.0)
    col = t.mix(dirt, col, (0.2, 0.15, 0.13))
    col = t.mix(crack, col, (0.11, 0.06, 0.045))
    col = t.mix(mossm, col, mosscol)
    # height for bump
    h = t.math('MULTIPLY', dent, 0.55)
    h = t.math('ADD', h, t.math('MULTIPLY', streak, 0.25))
    h = t.math('SUBTRACT', h, t.math('MULTIPLY', crack, 0.9))
    h = t.math('ADD', h, t.math('MULTIPLY', mossm, t.noise(P, 120, 2, 0.5).outputs['Fac']))
    nrm = t.bump(h, 0.7, 0.004)
    rough = t.maprange(mott.outputs['Fac'], 0.3, 0.7, 0.72, 0.9)
    rough = t.math('ADD', rough, t.math('MULTIPLY', t.math('ADD', mossm, crack), 0.15), clamp=True)
    t.principled(color=col, rough=rough, normal=nrm)
    return m


clay_proc = clay_material()
clay_objs = list(parts.values())
for o in clay_objs:
    L.assign(o, clay_proc)

import lib_mats as M
stone_proc = M.stone('GolemStoneProc', base=(0.24, 0.22, 0.20), dark=(0.12, 0.11, 0.10), warm=(0.34, 0.31, 0.27), scale=6, moss=0.4,
                     crack_amt=0.3)


def rock(part, c, size, rot, seed):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    rnd = random.Random(seed)
    for v in bm.verts:
        v.co *= 1.0 + rnd.uniform(-0.18, 0.18)
    r = L.mesh_from_bm(bm, 'rock')
    r.scale = size
    r.rotation_euler = rot
    r.location = c
    L.set_active(r)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    L.bevel_mod(r, 0.006, 2, 20)
    L.apply_all(r, transforms=False)
    L.shade_smooth(r, 35)
    L.assign(r, stone_proc)
    L.select([parts[part], r]); bpy.context.view_layer.objects.active = parts[part]
    bpy.ops.object.join()


rock('Torso', (0.29, -0.01, 1.135), (0.065, 0.055, 0.04), (0.2, 0.3, 0.5), 1)
rock('Torso', (-0.30, 0.03, 1.125), (0.05, 0.055, 0.035), (0.4, -0.3, 1.1), 2)
rock('Torso', (0.17, -0.165, 0.58), (0.045, 0.035, 0.04), (1.2, 0.2, 0.4), 3)
rock('Torso', (-0.09, 0.2, 0.86), (0.055, 0.035, 0.05), (1.4, 0.1, 0.2), 4)
rock('ArmR_Lower', (-0.385, -0.03, 0.60), (0.035, 0.05, 0.055), (0.3, 0.2, 0.1), 5)
rock('LegL', (0.18, -0.095, 0.25), (0.04, 0.035, 0.04), (0.3, 0.6, 0.2), 7)
# a tiny sprout growing out of the moss on top of the head (storytelling / charm)
sprout_m = M.flat('SproutProc', (0.16, 0.48, 0.08), 0.6, 0.2, 40, 0.2)
stem = L.curve_tube('sprout', [(0.035, -0.04, 1.30 + HZ), (0.04, -0.045, 1.335 + HZ), (0.032, -0.055, 1.355 + HZ)], radius=0.0045)
L.apply_all(stem)
sp_parts = [stem]
for sgn in (-1, 1):
    lf = L.uv_sphere('sproutleaf', 1.0, loc=(0.032 + sgn * 0.017, -0.055, 1.36 + HZ), seg=12, rings=8, scale=(0.02, 0.009, 0.004))
    lf.rotation_euler = (0, -sgn * 0.5, 0)
    L.apply_all(lf)
    sp_parts.append(lf)
sp = L.join(sp_parts, 'sprout')
L.shade_smooth(sp)
L.assign(sp, sprout_m)
L.select([parts['Head'], sp]); bpy.context.view_layer.objects.active = parts['Head']
bpy.ops.object.join()
clay_objs = list(parts.values())

# ------------------------------------------------------------------ pivots and hierarchy (translation only)
PIVOTS = {
    'Hips': (0, 0, 0.40), 'Torso': (0, 0, 0.48), 'Head': (0, -0.02, 1.10 + HZ), 'Jaw': (0, -0.06, 1.125 + HZ),
    'Brow_L': (0.06, -0.172, 1.256 + HZ), 'Brow_R': (-0.06, -0.172, 1.256 + HZ),
    'ArmL_Upper': (SH[0] + ARM_DX, SH[1], SH[2]), 'ArmL_Lower': (EL[0] + ARM_DX, EL[1], EL[2]), 'HandL': (WR[0] + ARM_DX, WR[1], WR[2]),
    'ArmR_Upper': (-SH[0] - ARM_DX, SH[1], SH[2]), 'ArmR_Lower': (-EL[0] - ARM_DX, EL[1], EL[2]), 'HandR': (-WR[0] - ARM_DX, WR[1], WR[2]),
    'LegL': HIP, 'LegR': (-HIP[0], HIP[1], HIP[2]),
}
PARENT = {
    'Hips': 'Golem', 'Torso': 'Hips', 'Head': 'Torso', 'Jaw': 'Head', 'Brow_L': 'Head', 'Brow_R': 'Head',
    'Eye_L': 'Head', 'Eye_R': 'Head',
    'ArmL_Upper': 'Torso', 'ArmL_Lower': 'ArmL_Upper', 'HandL': 'ArmL_Lower',
    'ArmR_Upper': 'Torso', 'ArmR_Lower': 'ArmR_Upper', 'HandR': 'ArmR_Lower',
    'LegL': 'Hips', 'LegR': 'Hips',
}

# ------------------------------------------------------------------ bake clay atlas
L.smart_uv(clay_objs, island_margin=0.006, angle=60)
L.pack_uv(clay_objs, margin=0.006)
sc = bpy.context.scene
clay = L.bake_pbr(clay_objs, 'Clay', ATLAS, 'golem_clay', samples=32, ao_strength=0.5)
L.rename_mat(clay, 'Clay')

# ------------------------------------------------------------------ glowing materials
rune_mat = L.emissive_mat('Rune', (0.03, 1.0, 0.75), 2.6, base=(0.02, 0.2, 0.17))
eye_mat = L.emissive_mat('Eye', (0.12, 1.0, 0.82), 2.6, base=(0.2, 0.85, 0.75))
mouth_mat = L.simple_mat('MouthDark', (0.035, 0.02, 0.02), 0.9)

torso = parts['Torso']
head = parts['Head']

# chest sigil + rune arc, projected along +Y onto the torso front
chest = R.place(R.SIGIL, 0.0, 0.80, 0.15)
for gname, (u, v, s, rot) in zip(['fe', 'eye', 'arrow', 'moon', 'zig', 'tree'],
                                 [(-0.15, 0.66, 0.055, 0.2), (0.15, 0.66, 0.055, -0.2), (-0.2, 0.80, 0.05, 0.1),
                                  (0.2, 0.80, 0.05, -0.1), (-0.075, 0.55, 0.045, 0.1), (0.075, 0.55, 0.045, -0.1)]):
    chest += R.place(R.GLYPHS[gname], u, v, s, rot)
r_chest = R.project_strokes(torso, chest, lambda u, v: ((u, -1.0, v), (0, 1, 0)), radius=0.0065, sink=0.0035, step=0.007, ring=5, name='RuneChest')
# back sigil
back = R.place(R.GLYPHS['star'], 0.0, 0.86, 0.11) + R.place(R.GLYPHS['moon'], 0.0, 0.86, 0.2)
r_back = R.project_strokes(torso, back, lambda u, v: ((-u, 1.0, v), (0, -1, 0)), radius=0.006, sink=0.0035, step=0.007, ring=5, name='RuneBack')
torso_runes = L.join([r_chest, r_back], 'TorsoRunes')

# forearm bands, projected radially toward the forearm axis
arm_runes = {}
for side, sx in (('L', 1), ('R', -1)):
    lo = parts[f'Arm{side}_Lower']
    a = Vector((sx * (EL[0] + ARM_DX), EL[1], EL[2]))
    b = Vector((sx * (WR[0] + ARM_DX), WR[1], WR[2]))

    def ray(u, v, a=a, b=b, sx=sx):
        # u: angle (radians from outward), v: height fraction along axis
        p = a.lerp(b, v)
        ang = u
        d = Vector((sx * math.cos(ang), -math.sin(ang), 0))
        return (p + d * 0.6, -d)
    strokes = []
    for gname, ang in (('hook', -0.7), ('star', 0.0), ('arrow', 0.7), ('eye', 1.35)):
        g = R.place(R.GLYPHS[gname], 0, 0, 1.0)
        # glyph in (angle, axis fraction): scale to ~0.055m
        strokes += [[(ang + x * 0.5, 0.42 - y * 0.18) for x, y in st] for st in g]
    # ring lines above/below the band
    strokes += [[(-1.1 + 2.7 * i / 40, 0.26) for i in range(41)], [(-1.1 + 2.7 * i / 40, 0.6) for i in range(41)]]
    arm_runes[side] = R.project_strokes(lo, strokes, ray, radius=0.0055, sink=0.003, step=0.06, ring=5, name=f'RuneArm{side}')

# forehead word: Blender lays glyphs out left-to-right, so store the string reversed (visual order) -> reads אמת
word = L.text_mesh('Word', 'תמא', 0.062, 0.003, bevel=0.0012, font=L.HEB_FONT)
# text is in XY plane; project onto the head front along +Y. (x -> u, y -> v height)
fz = 1.297 + HZ
R.project_mesh(head, word, lambda u, v: ((u, -1.0, fz + v), (0, 1, 0)), lift=0.0005)
bpy.context.view_layer.update()

for ob, mat in ((torso_runes, rune_mat), (arm_runes['L'], rune_mat), (arm_runes['R'], rune_mat), (word, rune_mat)):
    L.assign(ob, mat)

# eyes (separate nodes), mouth interior
eyes = {}
for side, sx in (('L', 1), ('R', -1)):
    e = L.uv_sphere(f'Eye_{side}', 1.0, loc=(sx * 0.058, -0.165, 1.197 + HZ), seg=32, rings=20, scale=(0.033, 0.022, 0.039))
    L.set_active(e)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    L.assign(e, eye_mat)
    eyes[side] = e
mouth = L.uv_sphere('MouthIn', 1.0, loc=(0, -0.135, 1.115 + HZ), seg=24, rings=12, scale=(0.055, 0.035, 0.016))
L.set_active(mouth); bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
L.assign(mouth, mouth_mat)


def join_into(main, extra):
    """Join extra (in world space) into main, keeping main's material slots first."""
    for o in extra:
        if 'UVMap' not in o.data.uv_layers and o.type == 'MESH':
            o.data.uv_layers.new(name=main.data.uv_layers[0].name)
    L.select([main] + extra)
    bpy.context.view_layer.objects.active = main
    bpy.ops.object.join()
    return main


torso = join_into(torso, [torso_runes])
head = join_into(head, [word, mouth])
for side in 'LR':
    join_into(parts[f'Arm{side}_Lower'], [arm_runes[side]])

# ------------------------------------------------------------------ assemble hierarchy
root = bpy.data.objects.new('Golem', None)
root.empty_display_type = 'PLAIN_AXES'
L.link_obj(root)
nodes = dict(parts)
nodes['Eye_L'] = eyes['L']
nodes['Eye_R'] = eyes['R']
PIVOTS['Eye_L'] = (0.058, -0.165, 1.197 + HZ)
PIVOTS['Eye_R'] = (-0.058, -0.165, 1.197 + HZ)
nodes['Golem'] = root
PIVOTS['Golem'] = (0, 0, 0)
# global scale so the golem stands ~1.35 m tall (meshes + pivots scaled, no object scale left behind)
S = 1.04
for n, ob in nodes.items():
    if n != 'Golem':
        ob.data.transform(ob.matrix_world)       # bake any object transform into the mesh first
        ob.matrix_world = Matrix.Identity(4)
        ob.data.transform(Matrix.Scale(S, 4))
PIVOTS = {k: tuple(c * S for c in v) for k, v in PIVOTS.items()}
for n, ob in nodes.items():
    if n == 'Golem':
        continue
    ob.name = n
    ob.data.name = n + '_mesh'
    L.set_origin(ob, PIVOTS[n])
    ob.rotation_euler = (0, 0, 0)
    ob.scale = (1, 1, 1)
for n, ob in nodes.items():
    if n == 'Golem':
        continue
    par = nodes[PARENT[n]]
    ob.parent = par
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.location = Vector(PIVOTS[n]) - Vector(PIVOTS[PARENT[n]])
bpy.context.view_layer.update()

# ------------------------------------------------------------------ stats + export
all_nodes = L.descendants(root)
tris = sum(L.tri_count(o) for o in all_nodes)
mins = Vector((9, 9, 9)); maxs = Vector((-9, -9, -9))
for o in all_nodes:
    if o.type != 'MESH':
        continue
    for v in o.data.vertices:
        w = o.matrix_world @ v.co
        mins = Vector(map(min, mins, w)); maxs = Vector(map(max, maxs, w))
print('GOLEM_TRIS', tris, 'BBOX', tuple(round(x, 3) for x in mins), tuple(round(x, 3) for x in maxs))
for o in all_nodes:
    print('  ', o.name, L.tri_count(o), [s.material.name for s in o.material_slots] if o.type == 'MESH' else '')

L.export_glb(os.path.join(L.MODELS_DIR, 'golem.glb'), all_nodes)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(L.BLEND_DIR, 'golem.blend'))

# ------------------------------------------------------------------ previews
L.ground(12, (0.07, 0.065, 0.075))
L.studio_lights()
L.light('EyeBounce', 'POINT', (0, -0.6, 1.0), 4, (0.3, 1, 0.9), size=0.3)
views = {'front': ((0, -3.1, 1.0), (0, 0, 0.66)), 'threequarter': ((2.0, -2.4, 1.25), (0, 0, 0.66)),
         'back': ((0.6, 3.0, 1.1), (0, 0, 0.66)), 'face': ((0.25, -1.1, 1.26), (0, -0.05, 1.18))}
for k, (loc, tgt) in views.items():
    cam = L.camera('Cam_' + k, loc, tgt, lens=50 if k != 'face' else 70)
    L.render(os.path.join(L.PREVIEW_DIR, f'golem_{k}.png'), (900, 1000) if k != 'face' else (900, 700), samples=64 if FAST else 160, cam=cam)
