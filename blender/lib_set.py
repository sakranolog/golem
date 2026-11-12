"""Set-dressing generators for the workshop (all procedural, chunky, bevelled)."""
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler
import lib_common as L
import lib_mats as M

R = random.Random(5)
MATS = {}


def mat(key):
    """Lazily created shared bake-source materials."""
    if key in MATS:
        return MATS[key]
    k = key
    if k == 'wood':
        m = M.wood('w_wood', base=(0.34, 0.19, 0.09), dark=(0.15, 0.08, 0.04), light=(0.50, 0.31, 0.16), axis='X', space='world', ring_scale=5)
    elif k == 'woodY':
        m = M.wood('w_woodY', base=(0.34, 0.19, 0.09), dark=(0.15, 0.08, 0.04), light=(0.50, 0.31, 0.16), axis='Y', space='world', ring_scale=5)
    elif k == 'woodZ':
        m = M.wood('w_woodZ', base=(0.34, 0.19, 0.09), dark=(0.15, 0.08, 0.04), light=(0.50, 0.31, 0.16), axis='Z', space='world', ring_scale=5)
    elif k == 'darkwood':
        m = M.wood('w_dark', base=(0.20, 0.11, 0.06), dark=(0.08, 0.045, 0.03), light=(0.33, 0.19, 0.10), axis='X', space='world')
    elif k == 'darkwoodY':
        m = M.wood('w_darkY', base=(0.20, 0.11, 0.06), dark=(0.08, 0.045, 0.03), light=(0.33, 0.19, 0.10), axis='Y', space='world')
    elif k == 'darkwoodZ':
        m = M.wood('w_darkZ', base=(0.20, 0.11, 0.06), dark=(0.08, 0.045, 0.03), light=(0.33, 0.19, 0.10), axis='Z', space='world')
    elif k == 'iron':
        m = M.flat('w_iron', (0.07, 0.07, 0.08), 0.5, 0.3, 30, 0.3)
    elif k == 'brass':
        m = M.flat('w_brass', (0.62, 0.42, 0.16), 0.35, 0.2, 30, 0.2)
    elif k == 'wax':
        m = M.flat('w_wax', (0.90, 0.82, 0.62), 0.5, 0.06, 30, 0.2)
    elif k == 'pages':
        m = M.pages('w_pages')
    elif k == 'parch':
        m = M.flat('w_parch', (0.78, 0.66, 0.45), 0.8, 0.2, 8, 0.1)
    elif k == 'clay':
        m = M.terracotta('w_clay', base=(0.55, 0.28, 0.14), band=None, space='world')
    elif k == 'claywet':
        m = M.flat('w_claywet', (0.36, 0.18, 0.09), 0.35, 0.15, 12, 0.5)
    elif k == 'sack':
        m = M.cloth('w_sack', (0.55, 0.45, 0.30), scale=3, bump=0.6)
    elif k == 'rope':
        m = M.cloth('w_rope', (0.55, 0.42, 0.24), scale=6)
    elif k == 'glass_teal':
        m = M.flat('w_gteal', (0.05, 0.35, 0.33), 0.15, 0.1, 10, 0.05)
    elif k == 'glass_green':
        m = M.flat('w_ggreen', (0.12, 0.30, 0.08), 0.15, 0.1, 10, 0.05)
    elif k == 'glass_amber':
        m = M.flat('w_gamber', (0.45, 0.22, 0.04), 0.15, 0.1, 10, 0.05)
    elif k == 'glass_purple':
        m = M.flat('w_gpurple', (0.25, 0.08, 0.30), 0.15, 0.1, 10, 0.05)
    elif k.startswith('glaze_'):
        cols = {'glaze_teal': (0.06, 0.32, 0.34), 'glaze_blue': (0.07, 0.15, 0.40), 'glaze_cream': (0.80, 0.72, 0.55),
                'glaze_brown': (0.30, 0.15, 0.07), 'glaze_green': (0.20, 0.33, 0.12), 'glaze_ochre': (0.65, 0.42, 0.12)}
        c = cols[k]
        m = M.terracotta('w_' + k, base=c, band=(0.75, 0.62, 0.38) if k != 'glaze_cream' else (0.06, 0.3, 0.32), band_z=(0.0, 0.0),
                         space='object', pattern=False)
    elif k.startswith('cover'):
        i = int(k[5:])
        cols = [(0.42, 0.07, 0.06), (0.05, 0.25, 0.27), (0.30, 0.16, 0.07), (0.22, 0.09, 0.26), (0.09, 0.18, 0.09), (0.48, 0.30, 0.08),
                (0.12, 0.12, 0.30), (0.55, 0.45, 0.30)]
        m = M.cloth('w_' + k, cols[i % len(cols)], scale=3)
    elif k == 'rug':
        m = rug_mat()
    elif k == 'straw':
        m = M.flat('w_straw', (0.70, 0.55, 0.22), 0.8, 0.3, 50, 0.6)
    elif k == 'herb':
        m = M.flat('w_herb', (0.22, 0.30, 0.10), 0.8, 0.3, 40, 0.4)
    elif k == 'brick':
        m = brick_mat()
    elif k == 'ink':
        m = L.simple_mat('w_ink', (0.03, 0.025, 0.03), 0.6)
    elif k == 'chalk':
        m = M.flat('w_slate', (0.06, 0.08, 0.08), 0.8, 0.15, 10, 0.1)
    elif k == 'white':
        m = M.flat('w_white', (0.8, 0.78, 0.72), 0.8, 0.1, 10, 0.1)
    elif k == 'ember':
        m = L.emissive_mat('w_ember', (1.0, 0.35, 0.06), 6.0, base=(0.1, 0.02, 0.0))
    elif k == 'soot':
        m = M.flat('w_soot', (0.05, 0.04, 0.04), 0.9, 0.3, 10, 0.3)
    else:
        raise KeyError(k)
    MATS[key] = m
    return m


def rug_mat():
    m, t = L.new_mat('w_rug')
    uv = t.tex_coord().outputs['Object']
    sep = t.node('ShaderNodeSeparateXYZ', i_Vector=uv)
    ax = t.math('ABSOLUTE', sep.outputs['X'])
    ay = t.math('ABSOLUTE', sep.outputs['Y'])
    border = t.math('MAXIMUM', t.math('DIVIDE', ax, 1.0), t.math('DIVIDE', ay, 1.0))
    dia = t.math('ADD', t.math('MULTIPLY', ax, 1.0), ay)
    pat = t.math('FRACT', t.math('MULTIPLY', dia, 3.0))
    c1 = t.ramp(pat, [(0.0, (0.45, 0.08, 0.06)), (0.45, (0.45, 0.08, 0.06)), (0.5, (0.85, 0.62, 0.30)), (0.6, (0.07, 0.20, 0.30)), (0.9, (0.07, 0.20, 0.30))])
    bmask = t.math('GREATER_THAN', border, 0.8)
    stripe = t.math('FRACT', t.math('MULTIPLY', border, 25))
    c2 = t.ramp(stripe, [(0.0, (0.06, 0.16, 0.22)), (0.5, (0.80, 0.58, 0.26)), (0.7, (0.30, 0.05, 0.04))])
    col = t.mix(bmask, c1, c2)
    fine = t.noise(uv, 200, 3, 0.5)
    fv = t.maprange(fine.outputs['Fac'], 0.3, 0.7, 0.75, 1.05)
    col = t.mix(1.0, col, t.node('ShaderNodeCombineColor', i_Red=fv, i_Green=fv, i_Blue=fv).outputs[0], 'MULTIPLY')
    wear = t.maprange(t.noise(uv, 3, 4, 0.6).outputs['Fac'], 0.55, 0.75, 0.0, 0.4)
    col = t.mix(wear, col, (0.35, 0.3, 0.25))
    t.principled(color=col, rough=0.95, normal=t.bump(fine.outputs['Fac'], 0.4, 0.003))
    return m


def brick_mat():
    m, t = L.new_mat('w_brick')
    P = t.geom().outputs['Position']
    sp = t.node('ShaderNodeSeparateXYZ', i_Vector=P)
    ang = t.math('ARCTAN2', t.math('SUBTRACT', sp.outputs['Y'], 6.05), t.math('SUBTRACT', sp.outputs['X'], 5.35))
    uvb = t.node('ShaderNodeCombineXYZ', i_X=t.math('MULTIPLY', ang, 1.1), i_Y=sp.outputs['Z']).outputs[0]
    br = t.node('ShaderNodeTexBrick')
    t.set_in(br, 'Vector', uvb)
    br.offset = 0.5
    t.set_in(br, 'Scale', 1.0)
    br.inputs['Brick Width'].default_value = 0.24
    br.inputs['Row Height'].default_value = 0.08
    br.inputs['Mortar Size'].default_value = 0.008
    br.inputs['Color1'].default_value = (0.42, 0.16, 0.08, 1)
    br.inputs['Color2'].default_value = (0.58, 0.27, 0.13, 1)
    br.inputs['Mortar'].default_value = (0.25, 0.2, 0.17, 1)
    soot = t.maprange(t.noise(P, 2, 3, 0.5).outputs['Fac'], 0.45, 0.65, 0.0, 0.6)
    col = t.mix(soot, br.outputs['Color'], (0.05, 0.03, 0.025))
    t.principled(color=col, rough=0.85, normal=t.bump(br.outputs['Fac'], 0.6, 0.01))
    return m


# ------------------------------------------------------------------ basic builders
def bx(size, loc, m, rot=(0, 0, 0), bevel=0.02, segs=2, name='bx'):
    o = L.box(name, size, loc=loc, bevel=bevel, segs=segs, rot=rot)
    L.assign(o, mat(m) if isinstance(m, str) else m)
    return o


def cyl(r, h, loc, m, rot=(0, 0, 0), verts=16, bevel=0.01, r2=None, name='cyl'):
    o = L.cylinder(name, r, h, loc=loc, verts=verts, bevel=bevel, r2=r2, rot=rot)
    L.assign(o, mat(m) if isinstance(m, str) else m)
    return o


def lathe(profile, loc, m, steps=24, name='lathe', rot=(0, 0, 0), scale=1.0):
    o = L.lathe(name, [(r * scale, z * scale) for r, z in profile], loc=loc, steps=steps)
    o.rotation_euler = rot
    L.assign(o, mat(m) if isinstance(m, str) else m)
    return o


def finalize(objs):
    out = []
    for o in objs:
        out.append(L.apply_all(o))
    return out


# ------------------------------------------------------------------ props
JAR_PROFILES = [
    [(0, 0), (0.08, 0), (0.1, 0.03), (0.11, 0.12), (0.09, 0.2), (0.05, 0.23), (0.05, 0.26), (0.065, 0.27), (0.05, 0.28), (0, 0.28)],
    [(0, 0), (0.06, 0), (0.12, 0.08), (0.13, 0.16), (0.1, 0.24), (0.06, 0.27), (0.07, 0.3), (0, 0.3)],
    [(0, 0), (0.07, 0), (0.075, 0.18), (0.08, 0.19), (0.06, 0.2), (0, 0.2)],
    [(0, 0), (0.05, 0), (0.09, 0.05), (0.1, 0.12), (0.07, 0.18), (0.03, 0.2), (0.025, 0.3), (0.035, 0.31), (0, 0.31)],   # bottle
    [(0, 0), (0.1, 0), (0.12, 0.04), (0.12, 0.1), (0.11, 0.12), (0, 0.12)],                                           # squat pot
]
JAR_MATS = ['glaze_teal', 'glaze_blue', 'glaze_cream', 'glaze_brown', 'glaze_green', 'glaze_ochre', 'clay', 'glass_teal', 'glass_green',
            'glass_amber', 'glass_purple']


def jar(loc, scale=1.0, kind=None, m=None, rotz=0.0):
    kind = R.randrange(len(JAR_PROFILES)) if kind is None else kind
    m = m or R.choice(JAR_MATS)
    o = lathe(JAR_PROFILES[kind], loc, m, steps=16, scale=scale, rot=(0, 0, rotz))
    parts = [o]
    if kind in (0, 2) and R.random() < 0.6:   # cork / cloth lid
        top = JAR_PROFILES[kind][-1][1] * scale
        parts.append(cyl(0.05 * scale, 0.03 * scale, (loc[0], loc[1], loc[2] + top - 0.005), 'sack' if R.random() < 0.5 else 'wood',
                         verts=12, bevel=0.006))
    if kind == 3:
        top = 0.31 * scale
        parts.append(cyl(0.022 * scale, 0.03 * scale, (loc[0], loc[1], loc[2] + top - 0.01), 'woodZ', verts=10, bevel=0.004))
    return parts


def book_row(x0, x1, y, z, depth, hmin, hmax, axis='X', tilt_end=True, gap_chance=0.08, facing=-1):
    """Books standing on a shelf between x0..x1 along `axis` (X for back wall, Y for side walls)."""
    out = []
    x = x0
    while x < x1 - 0.04:
        if R.random() < gap_chance:
            x += R.uniform(0.04, 0.12)
            continue
        t = R.uniform(0.035, 0.09)
        h = R.uniform(hmin, hmax)
        d = depth * R.uniform(0.75, 1.0)
        if x + t > x1:
            break
        cm = 'cover%d' % R.randrange(8)
        lean = 0.0
        if R.random() < 0.06 and x + h < x1:
            # lying stack
            for k in range(R.randint(2, 4)):
                hh = R.uniform(0.035, 0.06)
                ww = R.uniform(0.18, 0.28)
                c = (x + ww / 2, y, z + hh / 2 + k * hh) if axis == 'X' else (y, x + ww / 2, z + hh / 2 + k * hh)
                sz = (ww, d, hh) if axis == 'X' else (d, ww, hh)
                out.append(bx(sz, c, 'cover%d' % R.randrange(8), rot=(0, 0, R.uniform(-0.1, 0.1)), bevel=0.006))
            x += 0.3
            continue
        if axis == 'X':
            c = (x + t / 2, y, z + h / 2)
            sz = (t, d, h)
        else:
            c = (y, x + t / 2, z + h / 2)
            sz = (d, t, h)
        b = bx(sz, c, cm, bevel=0.007, segs=1)
        out.append(b)
        # page block edge visible at top front is implied by cover colour; add spine bands for richness
        if h > 0.25 and R.random() < 0.6:
            for k in (0.25, 0.75):
                bc = (c[0], c[1] + facing * d / 2 if axis == 'X' else c[1], z + h * k) if axis == 'X' else (c[0] + facing * d / 2, c[1], z + h * k)
                bsz = (t + 0.004, 0.012, 0.012) if axis == 'X' else (0.012, t + 0.004, 0.012)
                out.append(bx(bsz, bc, 'brass', bevel=0.0))
        x += t + R.uniform(0.0, 0.01)
    return out


def candle(loc, h, r=0.04, flames=None, lights=None, light_power=0.0, drip=True):
    """Pillar candle; adds flame mesh to `flames` list (Emit_) and returns static parts."""
    parts = [cyl(r, h, loc, 'wax', verts=16, bevel=0.008)]
    if drip:
        for k in range(R.randint(2, 4)):
            a = R.uniform(0, 6.28)
            ln = R.uniform(0.03, h * 0.6)
            p0 = Vector((loc[0] + math.cos(a) * r, loc[1] + math.sin(a) * r, loc[2] + h - 0.005))
            d = L.curve_tube('drip', [p0, p0 + Vector((0, 0, -ln * 0.6)), p0 + Vector((0, 0, -ln))], radius=r * 0.22, radii=[1, 0.9, 1.2], res=3, bevel_res=2)
            L.assign(d, mat('wax'))
            parts.append(d)
    top = Vector((loc[0], loc[1], loc[2] + h))
    if flames is not None:
        f = L.lathe('flame', [(0, 0), (0.014, 0.01), (0.019, 0.028), (0.013, 0.05), (0.005, 0.068), (0, 0.078)], loc=top + Vector((0, 0, 0.012)), steps=12)
        f.scale = (r / 0.04,) * 3 if r > 0.04 else (1, 1, 1)
        flames.append(f)
        parts.append(cyl(0.003, 0.018, tuple(top), 'ink', verts=6, bevel=0))
    if lights is not None and light_power > 0:
        lights.append((tuple(top + Vector((0, 0, 0.06))), light_power))
    return parts


def lantern(loc, glass_list, size=1.0, hang=None):
    """Brass/iron lantern; glass panes appended to glass_list (Emit_). loc = bottom centre."""
    s = size
    x, y, z = loc
    parts = []
    parts.append(bx((0.24 * s, 0.24 * s, 0.04 * s), (x, y, z + 0.02 * s), 'iron', bevel=0.01))
    parts.append(bx((0.2 * s, 0.2 * s, 0.03 * s), (x, y, z + 0.32 * s), 'iron', bevel=0.008))
    roof = cyl(0.17 * s, 0.12 * s, (x, y, z + 0.33 * s), 'iron', verts=4, r2=0.03 * s, bevel=0.01, rot=(0, 0, math.pi / 4))
    parts.append(roof)
    for dx in (-1, 1):
        for dy in (-1, 1):
            parts.append(bx((0.025 * s, 0.025 * s, 0.3 * s), (x + dx * 0.105 * s, y + dy * 0.105 * s, z + 0.18 * s), 'iron', bevel=0.005))
    ring = L.curve_tube('ring', [(x, y, z + 0.45 * s), (x + 0.04 * s, y, z + 0.5 * s), (x, y, z + 0.55 * s), (x - 0.04 * s, y, z + 0.5 * s)],
                        radius=0.008 * s, closed=True)
    L.assign(ring, mat('iron'))
    parts.append(ring)
    g = L.box('lglass', (0.19 * s, 0.19 * s, 0.27 * s), loc=(x, y, z + 0.175 * s), bevel=0.0)
    glass_list.append(g)
    # inner candle
    parts += [cyl(0.03 * s, 0.1 * s, (x, y, z + 0.04 * s), 'wax', verts=10, bevel=0.004)]
    if hang:  # chain to ceiling / bracket
        top = Vector((x, y, z + 0.55 * s))
        n = int((hang - top.z) / 0.07)
        for k in range(n):
            lk = L.curve_tube('link', [(x, y, top.z + k * 0.07), (x + 0.02, y, top.z + k * 0.07 + 0.035), (x, y, top.z + k * 0.07 + 0.07),
                                       (x - 0.02, y, top.z + k * 0.07 + 0.035)], radius=0.006, closed=True, res=3, bevel_res=1)
            lk.rotation_euler = (0, 0, (k % 2) * math.pi / 2)
            lk.location = (0, 0, 0)
            L.assign(lk, mat('iron'))
            parts.append(lk)
    return parts


def wall_bracket(p_wall, p_hook, axis_out):
    """Iron arm from wall to a hook point."""
    a = Vector(p_wall)
    b = Vector(p_hook)
    mid = (a + b) / 2 + Vector((0, 0, 0.15))
    arm = L.curve_tube('bracket', [a, mid, b], radius=0.018, res=8)
    L.assign(arm, mat('iron'))
    brace = L.curve_tube('brace', [a - Vector((0, 0, 0.35)), (a + b) / 2], radius=0.012, res=4)
    L.assign(brace, mat('iron'))
    plate = bx((0.04, 0.14, 0.5) if abs(axis_out[0]) > 0.5 else (0.14, 0.04, 0.5), tuple(a - Vector((0, 0, 0.15))), 'iron', bevel=0.01)
    return [arm, brace, plate]


def barrel(loc, h=0.9, r=0.33, rotz=0.0):
    prof = [(0, 0), (r * 0.85, 0), (r * 0.98, h * 0.25), (r, h * 0.5), (r * 0.98, h * 0.75), (r * 0.85, h), (r * 0.8, h - 0.02), (0, h - 0.02)]
    b = lathe(prof, loc, 'woodZ', steps=28)
    parts = [b]
    for zz in (0.12, 0.35, 0.65, 0.88):
        rr = r * (0.88 + 0.12 * math.sin(math.pi * zz))
        hoop = lathe([(rr + 0.008, -0.025), (rr + 0.012, 0.0), (rr + 0.008, 0.025)], (loc[0], loc[1], loc[2] + h * zz), 'iron', steps=28)
        parts.append(hoop)
    return parts


def sack(loc, s=1.0, rotz=0.0):
    o = L.uv_sphere('sack', 1.0, loc=(loc[0], loc[1], loc[2] + 0.22 * s), seg=24, rings=14, scale=(0.24 * s, 0.2 * s, 0.26 * s))
    L.displace_noise(o, 0.04 * s, 0.12, depth=2)
    for v in o.data.vertices:
        if v.co.z < -0.18:
            v.co.z = -0.18 - (v.co.z + 0.18) * 0.1
    o.rotation_euler = (0, 0, rotz)
    L.assign(o, mat('sack'))
    tie = cyl(0.06 * s, 0.1 * s, (loc[0], loc[1], loc[2] + 0.44 * s), 'sack', verts=10, r2=0.09 * s, bevel=0.01)
    return [o, tie]


def crate(loc, s=(0.6, 0.5, 0.45), rotz=0.0):
    parts = []
    w, d, h = s
    c = bx((w, d, h), (loc[0], loc[1], loc[2] + h / 2), 'wood', bevel=0.02, rot=(0, 0, rotz))
    parts.append(c)
    for zz in (0.08, h - 0.08):
        band = bx((w + 0.02, d + 0.02, 0.06), (loc[0], loc[1], loc[2] + zz), 'darkwood', bevel=0.012, rot=(0, 0, rotz))
        parts.append(band)
    return parts


def scroll(loc, length=0.35, r=0.04, rotz=0.0, lying=True):
    rot = (0, math.pi / 2, rotz) if lying else (0, 0, rotz)
    c = cyl(r, length, loc, 'parch', verts=14, bevel=0.006, rot=rot)
    return [c]


def clay_figure(loc, s=1.0, rotz=0.0, wet=False):
    """Little golem prototype figurine."""
    m = 'claywet' if wet else 'clay'
    x, y, z = loc
    parts = []
    body = L.uv_sphere('fig', 1.0, loc=(x, y, z + 0.11 * s), seg=16, rings=10, scale=(0.08 * s, 0.065 * s, 0.1 * s))
    head = L.uv_sphere('fig', 1.0, loc=(x, y - 0.01 * s, z + 0.22 * s), seg=12, rings=8, scale=(0.035 * s, 0.035 * s, 0.035 * s))
    for o in (body, head):
        L.assign(o, mat(m)); parts.append(o)
    for sx in (-1, 1):
        a = L.uv_sphere('fig', 1.0, loc=(x + sx * 0.085 * s, y, z + 0.1 * s), seg=10, rings=6, scale=(0.03 * s, 0.03 * s, 0.07 * s))
        lg = L.uv_sphere('fig', 1.0, loc=(x + sx * 0.04 * s, y, z + 0.025 * s), seg=10, rings=6, scale=(0.03 * s, 0.035 * s, 0.03 * s))
        for o in (a, lg):
            L.assign(o, mat(m)); parts.append(o)
    return parts


def logs(loc, n=6, rotz=0.0):
    parts = []
    rows = [(0, 3), (1, 2), (2, 1)]
    k = 0
    for row, cnt in rows:
        for i in range(cnt):
            if k >= n:
                break
            xo = (i - (cnt - 1) / 2) * 0.2
            p = Vector((xo, 0, 0.09 + row * 0.165))
            p.rotate(Euler((0, 0, rotz)))
            lg = cyl(0.085 + R.uniform(-0.01, 0.01), 0.75 + R.uniform(-0.1, 0.1), (loc[0] + p.x, loc[1] + p.y, loc[2] + p.z), 'darkwoodY',
                     verts=10, bevel=0.015, rot=(math.pi / 2, 0, rotz))
            lg.location = Vector(lg.location) + Vector((0, 0, 0)) - Vector((0, 0, 0))
            # centre the log along its axis
            ax = Vector((0, -0.375, 0)); ax.rotate(Euler((0, 0, rotz)))
            lg.location = Vector(lg.location) + ax * -1
            parts.append(lg)
            k += 1
    return parts


def voussoir_arch(center, radius, thick, depth, n, plane='XZ', facing=-1, m='stoneTrim', keystone=True, start=0.0, end=math.pi):
    """Semicircular arch of bevelled wedge stones. plane XZ: arch in X/Z at y=center.y, protruding along facing*Y."""
    parts = []
    c = Vector(center)
    for i in range(n):
        a0 = start + (end - start) * i / n
        a1 = start + (end - start) * (i + 1) / n
        bm = bmesh.new()
        vs = []
        for a in (a0, a1):
            for rr in (radius, radius + thick * (1.25 if keystone and i == n // 2 else 1.0)):
                for dd in (0.0, depth):
                    u = math.cos(a) * rr
                    v = math.sin(a) * rr
                    if plane == 'XZ':
                        p = c + Vector((u, facing * dd, v))
                    else:
                        p = c + Vector((facing * dd, u, v))
                    vs.append(bm.verts.new(p))
        bmesh.ops.convex_hull(bm, input=vs)
        o = L.mesh_from_bm(bm, 'vous')
        L.bevel_mod(o, 0.025, 2, 30)
        # tiny gap so stones read separately
        cen = sum((Vector(v) for v in [o.data.vertices[k].co for k in range(len(o.data.vertices))]), Vector()) / max(1, len(o.data.vertices))
        o.data.transform(Matrix.Translation(-cen))
        o.data.transform(Matrix.Scale(0.97, 4))
        o.data.transform(Matrix.Translation(cen))
        L.assign(o, MATS[m] if m in MATS else mat(m))
        parts.append(o)
    return parts
