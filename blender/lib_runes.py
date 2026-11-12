"""Rune glyphs and surface-projected glowing inlay geometry."""
import bpy, bmesh, math
from mathutils import Vector


def _circle(cx, cy, r, n=20, a0=0.0, a1=2 * math.pi):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


# glyphs in unit box [-0.5, 0.5]^2, list of polylines
GLYPHS = {
    'fe': [[(0, -0.5), (0, 0.5)], [(0, 0.2), (0.35, 0.45)], [(0, -0.05), (0.35, 0.2)]],
    'eye': [[(-0.45, 0), (0, 0.35), (0.45, 0), (0, -0.35), (-0.45, 0)], _circle(0, 0, 0.1, 10)],
    'arrow': [[(0, -0.5), (0, 0.5)], [(-0.35, 0.15), (0, 0.5), (0.35, 0.15)], [(-0.25, -0.3), (0.25, -0.3)]],
    'moon': [_circle(0, 0, 0.42, 16, math.radians(40), math.radians(320)), [(0, -0.2), (0, 0.2)]],
    'zig': [[(-0.4, 0.45), (0.3, 0.2), (-0.3, -0.1), (0.4, -0.45)]],
    'tree': [[(0, -0.5), (0, 0.5)], [(-0.35, 0.45), (0, 0.1), (0.35, 0.45)], [(-0.3, -0.5), (0.3, -0.5)]],
    'hook': [[(-0.3, 0.5), (-0.3, -0.2)] + [(p[0], p[1]) for p in _circle(0, -0.2, 0.3, 10, math.pi, 2 * math.pi)] + [(0.3, 0.3)]],
    'star': [[(0, 0.5), (0, -0.5)], [(-0.43, 0.25), (0.43, -0.25)], [(-0.43, -0.25), (0.43, 0.25)]],
}

SIGIL = [
    _circle(0, 0, 0.5, 40),
    _circle(0, 0, 0.17, 18),
    [(0, 0.17), (0, 0.5)],
    [(0.147, -0.085), (0.433, -0.25)],
    [(-0.147, -0.085), (-0.433, -0.25)],
    [(0, 0.5), (0.433, -0.25), (-0.433, -0.25), (0, 0.5)],
]


def place(strokes, cx, cy, size, rot=0.0):
    out = []
    c, s = math.cos(rot), math.sin(rot)
    for st in strokes:
        out.append([(cx + size * (x * c - y * s), cy + size * (x * s + y * c)) for x, y in st])
    return out


def _resample(pts, step):
    out = [Vector(pts[0])]
    for a, b in zip(pts[:-1], pts[1:]):
        a, b = Vector(a), Vector(b)
        L = (b - a).length
        n = max(1, int(L / step))
        for i in range(1, n + 1):
            out.append(a.lerp(b, i / n))
    return out


def project_strokes(target, strokes, ray_fn, radius=0.006, step=0.004, sink=0.0025, ring=6, name='Runes'):
    """strokes: list of 2D polylines (u, v). ray_fn(u, v) -> (origin_world, dir_world).
    Builds round tubes sitting on target's surface (centre sunk by `sink`). Returns new object (world space)."""
    dg = bpy.context.evaluated_depsgraph_get()
    mw = target.matrix_world
    mwi = mw.inverted()
    nmat = mw.to_3x3().inverted().transposed()
    bm = bmesh.new()

    def hit(u, v):
        o, d = ray_fn(u, v)
        lo = mwi @ Vector(o)
        ld = (mwi.to_3x3() @ Vector(d)).normalized()
        ok, loc, nor, idx = target.ray_cast(lo, ld, distance=10.0)
        if not ok:
            return None
        return mw @ loc, (nmat @ nor).normalized()

    for st in strokes:
        pts = _resample(st, step)
        hits = [hit(p.x, p.y) for p in pts]
        if any(h is None for h in hits):
            hits = [h for h in hits if h is not None]
            if len(hits) < 2:
                continue
        rings = []
        for i, (p, n) in enumerate(hits):
            a = hits[max(i - 1, 0)][0]
            b = hits[min(i + 1, len(hits) - 1)][0]
            t = (b - a)
            if t.length < 1e-9:
                t = Vector((1, 0, 0))
            t.normalize()
            bn = n.cross(t).normalized()
            nn = t.cross(bn).normalized()
            c = p - nn * sink
            rv = []
            for k in range(ring):
                ang = 2 * math.pi * k / ring
                rv.append(bm.verts.new(c + nn * (radius * math.cos(ang)) + bn * (radius * math.sin(ang))))
            rings.append((rv, c, t))
        for (r0, _, _), (r1, _, _) in zip(rings[:-1], rings[1:]):
            for k in range(ring):
                bm.faces.new((r0[k], r0[(k + 1) % ring], r1[(k + 1) % ring], r1[k]))
        # rounded caps
        for idx, sign in ((0, -1), (-1, 1)):
            rv, c, t = rings[idx]
            tip = bm.verts.new(c + t * sign * radius * 0.9)
            for k in range(ring):
                f = (rv[k], rv[(k + 1) % ring], tip) if sign > 0 else (rv[(k + 1) % ring], rv[k], tip)
                bm.faces.new(f)
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    return ob


def project_mesh(target, src, ray_fn, lift=0.0015):
    """Project a flat mesh (in its local XY plane, Z = thickness) onto target surface.
    Each vertex (x, y, z) -> surface(x, y) + normal * (z + lift)."""
    mw = target.matrix_world
    mwi = mw.inverted()
    nmat = mw.to_3x3().inverted().transposed()
    me = src.data
    for v in me.vertices:
        o, d = ray_fn(v.co.x, v.co.y)
        lo = mwi @ Vector(o)
        ld = (mwi.to_3x3() @ Vector(d)).normalized()
        ok, loc, nor, idx = target.ray_cast(lo, ld, distance=10.0)
        if not ok:
            continue
        p = mw @ loc
        n = (nmat @ nor).normalized()
        v.co = p + n * (v.co.z + lift)
    src.matrix_world.identity()
    me.update()
    return src
