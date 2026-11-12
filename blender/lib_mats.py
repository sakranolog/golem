"""Procedural (bake-source) materials shared by props and workshop."""
import bpy, math
import lib_common as L


def _P(t, space='world'):
    if space == 'object':
        return t.tex_coord().outputs['Object']
    return t.geom().outputs['Position']


def stone(name, base=(0.50, 0.46, 0.40), dark=(0.30, 0.28, 0.27), warm=(0.58, 0.50, 0.40), scale=1.0, crack_seed=0.0,
          moss=0.35, crack_amt=1.0, bump=0.6, space='world', tint_var=0.15):
    m, t = L.new_mat(name)
    g = t.geom()
    P = _P(t, space)
    P = t.vmath('ADD', P, (crack_seed, crack_seed * 0.7, crack_seed * 1.3))
    n1 = t.noise(P, 1.6 * scale, 4, 0.55)
    col = t.ramp(n1.outputs['Fac'], [(0.3, dark), (0.5, base), (0.72, warm)])
    n2 = t.noise(P, 9 * scale, 8, 0.62)
    speck = t.voronoi(P, 60 * scale, 'F1')
    sp = t.maprange(speck.outputs['Distance'], 0.0, 0.18, 0.0, 1.0)
    col = t.mix(t.math('MULTIPLY', t.math('SUBTRACT', 1.0, sp), 0.25), col, (0.18, 0.17, 0.17))
    vary = t.maprange(n2.outputs['Fac'], 0.3, 0.7, 1.0 - tint_var, 1.0 + tint_var * 0.6)
    col = t.mix(1.0, col, t.node('ShaderNodeCombineColor', i_Red=vary, i_Green=vary, i_Blue=vary).outputs[0], 'MULTIPLY')
    # cracks
    dn = t.noise(P, 5 * scale, 3, 0.5)
    sd = t.vmath('SCALE', dn.outputs['Color'], None)
    sd.node.inputs['Scale'].default_value = 0.08
    pc = t.vmath('ADD', P, sd)
    cv = t.voronoi(pc, 2.2 * scale, 'DISTANCE_TO_EDGE')
    crack = t.maprange(cv.outputs['Distance'], 0.0, 0.012, 1.0, 0.0)
    cm = t.maprange(t.noise(P, 1.3 * scale, 2, 0.5).outputs['Fac'], 0.5, 0.58, 0.0, crack_amt)
    crack = t.math('MULTIPLY', crack, cm)
    # cavity + edge wear
    pt = g.outputs['Pointiness']
    edge = t.maprange(pt, 0.51, 0.6, 0.0, 1.0)
    col = t.mix(t.math('MULTIPLY', edge, 0.4), col, tuple(min(1.0, c * 1.5 + 0.05) for c in warm))
    cav = t.maprange(pt, 0.4, 0.49, 1.0, 0.0)
    col = t.mix(t.math('MULTIPLY', cav, 0.5), col, (0.15, 0.14, 0.15))
    col = t.mix(crack, col, (0.08, 0.075, 0.08))
    # moss in cavities / up faces
    N = g.outputs['Normal']
    mn = t.noise(P, 3.5 * scale, 8, 0.7)
    mmask = t.maprange(mn.outputs['Fac'], 0.6, 0.66, 0.0, moss)
    mmask = t.math('MAXIMUM', mmask, t.math('MULTIPLY', t.math('MULTIPLY', cav, 0.8), moss))
    mosscol = t.ramp(t.noise(P, 80, 2, 0.5).outputs['Fac'], [(0.3, (0.10, 0.18, 0.06)), (0.7, (0.26, 0.36, 0.10))])
    col = t.mix(mmask, col, mosscol)
    h = t.math('ADD', t.math('MULTIPLY', n2.outputs['Fac'], 0.6), t.math('MULTIPLY', crack, -1.0))
    h = t.math('ADD', h, t.math('MULTIPLY', sp, 0.12))
    nrm = t.bump(h, bump, 0.01)
    rough = t.maprange(n2.outputs['Fac'], 0.3, 0.7, 0.7, 0.92)
    t.principled(color=col, rough=rough, normal=nrm)
    return m


def wood(name, base=(0.36, 0.20, 0.10), dark=(0.17, 0.09, 0.05), light=(0.52, 0.32, 0.17), axis='X', ring_scale=6.0,
         space='object', bump=0.4, worn=0.5):
    m, t = L.new_mat(name)
    g = t.geom()
    P = _P(t, space)
    sc = {'X': (0.15, 1.0, 1.0), 'Y': (1.0, 0.15, 1.0), 'Z': (1.0, 1.0, 0.15)}[axis]
    Ps = t.vmath('MULTIPLY', P, sc)
    dn = t.noise(Ps, 2.0, 4, 0.6)
    sd = t.vmath('SCALE', dn.outputs['Color'], None)
    sd.node.inputs['Scale'].default_value = 0.25
    Pd = t.vmath('ADD', Ps, sd)
    grain = t.noise(Pd, ring_scale * 4, 6, 0.7)
    wv = t.node('ShaderNodeTexWave')
    wv.wave_type = 'RINGS'
    wv.rings_direction = {'X': 'X', 'Y': 'Y', 'Z': 'Z'}[axis]
    t.set_in(wv, 'Vector', Pd)
    t.set_in(wv, 'Scale', ring_scale)
    t.set_in(wv, 'Distortion', 4.0)
    t.set_in(wv, 'Detail', 3.0)
    f = t.math('MULTIPLY', wv.outputs['Fac'], grain.outputs['Fac'])
    col = t.ramp(f, [(0.05, dark), (0.35, base), (0.75, light)])
    pt = g.outputs['Pointiness']
    edge = t.maprange(pt, 0.51, 0.6, 0.0, worn)
    col = t.mix(edge, col, light)
    cav = t.maprange(pt, 0.4, 0.49, 0.6, 0.0)
    col = t.mix(cav, col, (0.06, 0.035, 0.02))
    nrm = t.bump(f, bump, 0.005)
    rough = t.maprange(f, 0.0, 1.0, 0.8, 0.6)
    t.principled(color=col, rough=rough, normal=nrm)
    return m


def cloth(name, base, dark=None, scale=1.0, bump=0.3, worn=0.35, space='world', pattern=None):
    """leather / book covers / fabric"""
    dark = dark or tuple(c * 0.55 for c in base)
    m, t = L.new_mat(name)
    g = t.geom()
    P = _P(t, space)
    n1 = t.noise(P, 6 * scale, 6, 0.6)
    col = t.ramp(n1.outputs['Fac'], [(0.3, dark), (0.7, base)])
    pt = g.outputs['Pointiness']
    edge = t.maprange(pt, 0.51, 0.6, 0.0, worn)
    col = t.mix(edge, col, tuple(min(1, c * 1.6 + 0.08) for c in base))
    cav = t.maprange(pt, 0.4, 0.49, 0.6, 0.0)
    col = t.mix(cav, col, (0.03, 0.02, 0.02))
    fine = t.noise(P, 90 * scale, 3, 0.5)
    nrm = t.bump(t.math('ADD', fine.outputs['Fac'], n1.outputs['Fac']), bump, 0.003)
    t.principled(color=col, rough=0.7, normal=nrm)
    return m


def pages(name, base=(0.80, 0.72, 0.55), axis='Z'):
    m, t = L.new_mat(name)
    P = t.geom().outputs['Position']
    wv = t.node('ShaderNodeTexWave')
    wv.wave_type = 'BANDS'
    wv.bands_direction = axis
    t.set_in(wv, 'Vector', P)
    t.set_in(wv, 'Scale', 140)
    t.set_in(wv, 'Distortion', 2.0)
    n = t.noise(P, 5, 4, 0.5)
    col = t.ramp(t.math('MULTIPLY', wv.outputs['Fac'], n.outputs['Fac']), [(0.0, (0.45, 0.38, 0.27)), (0.4, base)])
    nrm = t.bump(wv.outputs['Fac'], 0.3, 0.002)
    t.principled(color=col, rough=0.85, normal=nrm)
    return m


def terracotta(name, base=(0.62, 0.30, 0.16), band=(0.09, 0.42, 0.42), band_z=(0.25, 0.32), space='object', glaze=0.45,
               pattern=True):
    m, t = L.new_mat(name)
    g = t.geom()
    P = _P(t, space)
    n1 = t.noise(P, 8, 5, 0.6)
    col = t.ramp(n1.outputs['Fac'], [(0.35, tuple(c * 0.75 for c in base)), (0.7, base)])
    z = t.node('ShaderNodeSeparateXYZ', i_Vector=P)
    if band:
        # painted band with zigzag
        ang = t.math('ARCTAN2', z.outputs['Y'], z.outputs['X'])
        zig = t.math('MULTIPLY', t.math('PINGPONG', t.math('MULTIPLY', ang, 2.5), 0.5) if False else t.math('SINE', t.math('MULTIPLY', ang, 12.0)), 0.012)
        zz = t.math('ADD', z.outputs['Z'], zig)
        b1 = t.math('MULTIPLY', t.math('GREATER_THAN', zz, band_z[0]), t.math('LESS_THAN', zz, band_z[1]))
        thin = t.math('MULTIPLY', t.math('GREATER_THAN', z.outputs['Z'], band_z[1] + 0.018), t.math('LESS_THAN', z.outputs['Z'], band_z[1] + 0.03))
        b = t.math('MAXIMUM', b1, thin) if pattern else b1
        bn = t.noise(P, 30, 3, 0.5)
        b = t.math('MULTIPLY', b, t.maprange(bn.outputs['Fac'], 0.3, 0.45, 0.4, 1.0))
        col = t.mix(b, col, band)
    pt = g.outputs['Pointiness']
    edge = t.maprange(pt, 0.51, 0.6, 0.0, 0.4)
    col = t.mix(edge, col, (0.85, 0.6, 0.42))
    cav = t.maprange(pt, 0.4, 0.49, 0.6, 0.0)
    col = t.mix(cav, col, (0.12, 0.05, 0.03))
    nrm = t.bump(t.noise(P, 40, 4, 0.5).outputs['Fac'], 0.25, 0.003)
    t.principled(color=col, rough=glaze + 0.25 * 0, normal=nrm)
    return m


def flat(name, color, rough=0.6, noise_amt=0.12, scale=20, bump=0.15, metal=0.0):
    m, t = L.new_mat(name)
    P = t.geom().outputs['Position']
    n = t.noise(P, scale, 5, 0.6)
    col = t.ramp(n.outputs['Fac'], [(0.3, tuple(c * (1 - noise_amt) for c in color)), (0.7, tuple(min(1, c * (1 + noise_amt)) for c in color))])
    pt = t.geom().outputs['Pointiness']
    cav = t.maprange(pt, 0.4, 0.49, 0.5, 0.0)
    col = t.mix(cav, col, tuple(c * 0.25 for c in color))
    nrm = t.bump(n.outputs['Fac'], bump, 0.003)
    t.principled(color=col, rough=rough, normal=nrm, metal=metal)
    return m


def fur(name, base=(0.85, 0.42, 0.12), stripe=(0.45, 0.17, 0.05), belly=(0.95, 0.85, 0.7), space='object'):
    m, t = L.new_mat(name)
    g = t.geom()
    P = _P(t, space)
    dn = t.noise(P, 6, 3, 0.5)
    sd = t.vmath('SCALE', dn.outputs['Color'], None)
    sd.node.inputs['Scale'].default_value = 0.05
    Pd = t.vmath('ADD', P, sd)
    wv = t.node('ShaderNodeTexWave')
    wv.wave_type = 'BANDS'
    wv.bands_direction = 'X'
    t.set_in(wv, 'Vector', Pd)
    t.set_in(wv, 'Scale', 9)
    t.set_in(wv, 'Distortion', 3.0)
    t.set_in(wv, 'Detail', 2.0)
    s = t.maprange(wv.outputs['Fac'], 0.62, 0.8, 0.0, 1.0)
    col = t.mix(s, base, stripe)
    z = t.node('ShaderNodeSeparateXYZ', i_Vector=P)
    N = g.outputs['Normal']
    nz = t.node('ShaderNodeSeparateXYZ', i_Vector=N)
    bm = t.maprange(nz.outputs['Z'], -0.2, -0.6, 0.0, 1.0)
    col = t.mix(bm, col, belly)
    fine = t.noise(P, 200, 2, 0.5)
    fv = t.maprange(fine.outputs['Fac'], 0.3, 0.7, 0.85, 1.1)
    col = t.mix(1.0, col, t.node('ShaderNodeCombineColor', i_Red=fv, i_Green=fv, i_Blue=fv).outputs[0], 'MULTIPLY')
    nrm = t.bump(fine.outputs['Fac'], 0.25, 0.002)
    t.principled(color=col, rough=0.85, normal=nrm)
    return m


def gold(name='Gold', color=(1.0, 0.70, 0.28), rough=0.28):
    m, t = L.new_mat(name)
    t.principled(color=color, rough=rough, metal=1.0)
    m.diffuse_color = (*color, 1)
    return m
