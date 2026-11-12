"""Shared helpers for the Golem asset pipeline (Blender 5.3, Cycles/Metal)."""
import bpy, bmesh, math, os, random, json
from mathutils import Vector, Matrix, Euler

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
BLEND_DIR = os.path.join(ROOT, 'blender')
PREVIEW_DIR = os.path.join(BLEND_DIR, 'previews')
TEX_DIR = os.path.join(BLEND_DIR, 'textures')
MODELS_DIR = os.path.join(ROOT, 'public', 'models')
ENV_DIR = os.path.join(ROOT, 'public', 'env')
for d in (PREVIEW_DIR, TEX_DIR, MODELS_DIR, ENV_DIR):
    os.makedirs(d, exist_ok=True)

HEB_FONT = '/System/Library/Fonts/SFHebrew.ttf'
HEB_FONT_ALT = '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'


# ----------------------------------------------------------------- scene
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    setup_cycles(sc)
    return sc


def setup_cycles(sc=None, samples=128, denoise=True):
    sc = sc or bpy.context.scene
    sc.render.engine = 'CYCLES'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.refresh_devices()
    for d in prefs.devices:
        d.use = (d.type == 'METAL')
    sc.cycles.device = 'GPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = denoise
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Base Contrast'
    except Exception:
        pass
    sc.render.film_transparent = False
    return sc


def world_color(rgb, strength=1.0):
    w = bpy.context.scene.world or bpy.data.worlds.new('World')
    bpy.context.scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    if bg is None:
        bg = w.node_tree.nodes.new('ShaderNodeBackground')
        out = w.node_tree.nodes.get('World Output') or w.node_tree.nodes.new('ShaderNodeOutputWorld')
        w.node_tree.links.new(bg.outputs[0], out.inputs[0])
    bg.inputs[0].default_value = (*rgb, 1)
    bg.inputs[1].default_value = strength
    return w


def link_obj(ob, coll=None):
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob


def set_active(ob, select_only=True):
    if select_only:
        for o in bpy.context.view_layer.objects:
            if o is not None:
                o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def select(objs):
    for o in bpy.context.view_layer.objects:
        if o is not None:
            o.select_set(False)
    for o in objs:
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]


def apply_all(ob, transforms=True):
    set_active(ob)
    if ob.type != 'MESH':
        bpy.ops.object.convert(target='MESH')
        ob = bpy.context.view_layer.objects.active
    for m in list(ob.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=m.name)
        except Exception as e:
            print('modifier apply failed', ob.name, m.name, e)
            ob.modifiers.remove(m)
    if transforms:
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return ob


def set_origin(ob, world_pt):
    """Move object origin to world_pt without moving geometry."""
    mw = ob.matrix_world.copy()
    local = mw.inverted() @ Vector(world_pt)
    ob.data.transform(Matrix.Translation(-local))
    ob.matrix_world = mw @ Matrix.Translation(local)


def join(objs, name=None):
    objs = [o for o in objs if o is not None]
    objs = [apply_all(o, transforms=False) if (o.type != 'MESH' or len(o.modifiers)) else o for o in objs]
    select(objs)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    if name:
        ob.name = name
        ob.data.name = name
    return ob


def shade_smooth(ob, angle=None):
    for p in ob.data.polygons:
        p.use_smooth = True
    if angle is not None:
        set_active(ob)
        try:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(angle))
        except Exception:
            try:
                bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))
            except Exception as e:
                print('auto smooth fail', e)


def tri_count(ob):
    if ob.type != 'MESH':
        return 0
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    n = sum(len(p.vertices) - 2 for p in me.polygons)
    ev.to_mesh_clear()
    return n


# ----------------------------------------------------------------- primitives
def mesh_from_bm(bm, name):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    link_obj(ob)
    return ob


def box(name, size, loc=(0, 0, 0), bevel=0.02, segs=2, rot=(0, 0, 0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
    ob = mesh_from_bm(bm, name)
    ob.location = loc
    ob.rotation_euler = rot
    if bevel > 0:
        m = ob.modifiers.new('bev', 'BEVEL')
        m.width = bevel
        m.segments = segs
        m.limit_method = 'ANGLE'
        m.harden_normals = False
    return ob


def cylinder(name, r, h, loc=(0, 0, 0), verts=24, bevel=0.01, segs=2, r2=None, rot=(0, 0, 0), cap=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=verts,
                          radius1=r, radius2=r if r2 is None else r2, depth=h)
    bmesh.ops.translate(bm, verts=bm.verts, vec=(0, 0, h / 2))
    ob = mesh_from_bm(bm, name)
    ob.location = loc
    ob.rotation_euler = rot
    if bevel > 0:
        m = ob.modifiers.new('bev', 'BEVEL')
        m.width = bevel
        m.segments = segs
        m.limit_method = 'ANGLE'
    shade_smooth(ob, 40)
    return ob


def uv_sphere(name, r, loc=(0, 0, 0), seg=24, rings=16, scale=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    for v in bm.verts:
        v.co = Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2]))
    ob = mesh_from_bm(bm, name)
    ob.location = loc
    shade_smooth(ob)
    return ob


def lathe(name, profile, loc=(0, 0, 0), steps=32, thickness=0.0, smooth=True):
    """profile: list of (r, z) from bottom centre outward/upward. Revolve around Z."""
    bm = bmesh.new()
    prev = None
    vs = [bm.verts.new((r, 0, z)) for r, z in profile]
    for a, b in zip(vs[:-1], vs[1:]):
        bm.edges.new((a, b))
    ob = mesh_from_bm(bm, name)
    ob.location = loc
    m = ob.modifiers.new('screw', 'SCREW')
    m.steps = steps
    m.render_steps = steps
    m.use_merge_vertices = True
    m.merge_threshold = 0.0005
    m.use_normal_calculate = True
    if thickness:
        s = ob.modifiers.new('solid', 'SOLIDIFY')
        s.thickness = thickness
        s.offset = -1
    if smooth:
        shade_smooth(ob, 50)
    return ob


def curve_tube(name, pts, radius=0.01, res=6, radii=None, closed=False, bevel_res=3):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = bevel_res
    cu.use_fill_caps = True
    sp = cu.splines.new('BEZIER')
    sp.bezier_points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        bp = sp.bezier_points[i]
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = 'AUTO'
        if radii:
            bp.radius = radii[i]
    sp.use_cyclic_u = closed
    sp.resolution_u = res
    ob = bpy.data.objects.new(name, cu)
    link_obj(ob)
    return ob


def text_mesh(name, body, size, extrude, bevel=0.0, font=HEB_FONT, bevel_res=2, resu=6, offset=0.0):
    cu = bpy.data.curves.new(name, 'FONT')
    cu.body = body
    cu.font = bpy.data.fonts.load(font, check_existing=True)
    cu.size = size
    cu.extrude = extrude
    cu.bevel_depth = bevel
    cu.bevel_resolution = bevel_res
    cu.resolution_u = resu
    cu.offset = offset
    cu.align_x = 'CENTER'
    cu.align_y = 'CENTER'
    ob = bpy.data.objects.new(name, cu)
    link_obj(ob)
    set_active(ob)
    bpy.ops.object.convert(target='MESH')
    ob = bpy.context.view_layer.objects.active
    return ob


def metaball_mesh(name, elements, resolution=0.02, threshold=0.6, voxel=None, smooth_iter=0):
    """elements: list of dicts {type, co, radius, size(x,y,z), rot(euler), stiffness, negative}"""
    mb = bpy.data.metaballs.new(name + '_mb')
    mb.resolution = resolution
    mb.render_resolution = resolution
    mb.threshold = threshold
    for e in elements:
        el = mb.elements.new(type=e.get('type', 'BALL'))
        el.co = e['co']
        el.radius = e.get('radius', 0.1)
        el.stiffness = e.get('stiffness', 2.0)
        el.use_negative = e.get('negative', False)
        sz = e.get('size')
        if sz is not None:
            el.size_x, el.size_y, el.size_z = sz
        r = e.get('rot')
        if r is not None:
            el.rotation = Euler(r).to_quaternion()
    ob = bpy.data.objects.new(name + '_mbobj', mb)
    link_obj(ob)
    bpy.context.view_layer.update()
    set_active(ob)
    bpy.ops.object.convert(target='MESH')
    me_ob = bpy.context.view_layer.objects.active
    me_ob.name = name
    me_ob.data.name = name
    # remove leftover metaball object if still present
    if name + '_mbobj' in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name + '_mbobj'])
    if voxel:
        remesh(me_ob, voxel)
    if smooth_iter:
        sm = me_ob.modifiers.new('sm', 'SMOOTH')
        sm.iterations = smooth_iter
        sm.factor = 0.5
        apply_all(me_ob, transforms=False)
    shade_smooth(me_ob)
    return me_ob


def remesh(ob, voxel, adaptivity=0.0):
    m = ob.modifiers.new('rem', 'REMESH')
    m.mode = 'VOXEL'
    m.voxel_size = voxel
    m.adaptivity = adaptivity
    m.use_smooth_shade = True
    apply_all(ob, transforms=False)


def decimate(ob, target_tris):
    t = tri_count(ob)
    if t > target_tris:
        m = ob.modifiers.new('dec', 'DECIMATE')
        m.ratio = target_tris / t
        apply_all(ob, transforms=False)


def displace_noise(ob, strength, scale, kind='CLOUDS', basis='BLENDER_ORIGINAL', depth=2, mid=0.5, seed_off=(0, 0, 0), ttype=None, coords='GLOBAL'):
    tex = bpy.data.textures.new(ob.name + '_disp', type=ttype or 'CLOUDS')
    if hasattr(tex, 'noise_scale'):
        tex.noise_scale = scale
    if hasattr(tex, 'noise_depth'):
        tex.noise_depth = depth
    if hasattr(tex, 'noise_basis'):
        tex.noise_basis = basis
    m = ob.modifiers.new('disp', 'DISPLACE')
    m.texture = tex
    m.strength = strength
    m.mid_level = mid
    m.texture_coords = coords
    return m, tex


def subsurf(ob, levels=1):
    m = ob.modifiers.new('sub', 'SUBSURF')
    m.levels = levels
    m.render_levels = levels
    return m


def bevel_mod(ob, width, segs=2, angle=40):
    m = ob.modifiers.new('bev', 'BEVEL')
    m.width = width
    m.segments = segs
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(angle)
    return m


# ----------------------------------------------------------------- node helpers
class NT:
    """Tiny node-tree builder."""
    def __init__(self, mat):
        self.mat = mat
        self.nt = mat.node_tree
        self.n = self.nt.nodes
        self.l = self.nt.links
        self.x = 0

    def node(self, t, **kw):
        nd = self.n.new(t)
        for k, v in kw.items():
            if k.startswith('i_'):
                self.set_in(nd, k[2:].replace('_', ' '), v)
            else:
                setattr(nd, k, v)
        return nd

    @staticmethod
    def _sock(socks, name, typ=None):
        if isinstance(name, int):
            return socks[name]
        cands = [s for s in socks if s.name == name and s.enabled]
        if typ:
            c2 = [s for s in cands if s.type == typ]
            if c2:
                return c2[0]
        if cands:
            return cands[0]
        cands = [s for s in socks if s.name == name]
        if not cands:
            alt = {'Fac': 'Factor', 'Factor': 'Fac'}.get(name)
            cands = [s for s in socks if s.name == alt]
        if not cands:
            raise KeyError(f'socket {name} not in {[s.name for s in socks]}')
        return cands[0]

    def set_in(self, nd, name, v):
        s = self._sock(nd.inputs, name)
        if isinstance(v, bpy.types.NodeSocket):
            self.l.new(v, s)
        else:
            if s.type == 'RGBA' and len(v) == 3:
                v = (*v, 1)
            s.default_value = v

    def link(self, a, b):
        self.l.new(a, b)

    # convenience
    def tex_coord(self):
        return self.node('ShaderNodeTexCoord')

    def geom(self):
        return self.node('ShaderNodeNewGeometry')

    def noise(self, vec, scale, detail=4, rough=0.55, dist=0.0, dims='3D', ntype=None):
        nd = self.node('ShaderNodeTexNoise')
        nd.noise_dimensions = dims
        if ntype:
            nd.noise_type = ntype
        self.set_in(nd, 'Vector', vec)
        self.set_in(nd, 'Scale', scale)
        self.set_in(nd, 'Detail', detail)
        self.set_in(nd, 'Roughness', rough)
        self.set_in(nd, 'Distortion', dist)
        return nd

    def voronoi(self, vec, scale, feature='F1', metric='EUCLIDEAN', rand=1.0, detail=0):
        nd = self.node('ShaderNodeTexVoronoi')
        nd.feature = feature
        nd.distance = metric
        self.set_in(nd, 'Vector', vec)
        self.set_in(nd, 'Scale', scale)
        self.set_in(nd, 'Randomness', rand)
        try:
            self.set_in(nd, 'Detail', detail)
        except Exception:
            pass
        return nd

    def math(self, op, a, b=None, clamp=False, c=None):
        nd = self.node('ShaderNodeMath')
        nd.operation = op
        nd.use_clamp = clamp
        for i, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                self.l.new(v, nd.inputs[i])
            else:
                nd.inputs[i].default_value = v
        return nd.outputs[0]

    def vmath(self, op, a, b=None):
        nd = self.node('ShaderNodeVectorMath')
        nd.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                self.l.new(v, nd.inputs[i])
            else:
                nd.inputs[i].default_value = v
        return nd.outputs[0] if op not in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else nd.outputs['Value']

    def maprange(self, v, a, b, c=0.0, d=1.0, clamp=True, interp='LINEAR'):
        nd = self.node('ShaderNodeMapRange')
        nd.interpolation_type = interp
        nd.clamp = clamp
        self.set_in(nd, 'Value', v)
        nd.inputs['From Min'].default_value = a
        nd.inputs['From Max'].default_value = b
        nd.inputs['To Min'].default_value = c
        nd.inputs['To Max'].default_value = d
        return nd.outputs['Result']

    def ramp(self, fac, stops):
        """stops: list of (pos, (r,g,b)) or (pos, (r,g,b,a))"""
        nd = self.node('ShaderNodeValToRGB')
        self.set_in(nd, 'Fac', fac)
        cr = nd.color_ramp
        while len(cr.elements) > 1:
            cr.elements.remove(cr.elements[-1])
        for i, (p, c) in enumerate(stops):
            c = (*c, 1) if len(c) == 3 else c
            if i == 0:
                cr.elements[0].position = p
                cr.elements[0].color = c
            else:
                e = cr.elements.new(p)
                e.color = c
        return nd.outputs['Color']

    def mix(self, fac, a, b, blend='MIX', clamp=True):
        nd = self.node('ShaderNodeMix')
        nd.data_type = 'RGBA'
        nd.blend_type = blend
        nd.clamp_result = clamp
        self.set_in(nd, 'Factor', fac)
        sa = [s for s in nd.inputs if s.name == 'A' and s.type == 'RGBA'][0]
        sb = [s for s in nd.inputs if s.name == 'B' and s.type == 'RGBA'][0]
        for s, v in ((sa, a), (sb, b)):
            if isinstance(v, bpy.types.NodeSocket):
                self.l.new(v, s)
            else:
                s.default_value = (*v, 1) if len(v) == 3 else v
        return [s for s in nd.outputs if s.name == 'Result' and s.type == 'RGBA'][0]

    def bump(self, height, strength=0.5, distance=0.02, normal=None):
        nd = self.node('ShaderNodeBump')
        self.set_in(nd, 'Height', height)
        nd.inputs['Strength'].default_value = strength
        nd.inputs['Distance'].default_value = distance
        if normal is not None:
            self.l.new(normal, nd.inputs['Normal'])
        return nd.outputs['Normal']

    def principled(self, color=None, rough=0.6, metal=0.0, normal=None, emit=None, emit_strength=0.0, spec=0.5, coat=0.0):
        bs = self.n.get('Principled BSDF') or self.node('ShaderNodeBsdfPrincipled')
        out = self.n.get('Material Output') or self.node('ShaderNodeOutputMaterial')
        self.l.new(bs.outputs[0], out.inputs['Surface'])
        for name, v in (('Base Color', color), ('Roughness', rough), ('Metallic', metal), ('Normal', normal),
                        ('Emission Color', emit), ('Specular IOR Level', spec), ('Coat Weight', coat)):
            if v is None:
                continue
            self.set_in(bs, name, v)
        bs.inputs['Emission Strength'].default_value = emit_strength
        return bs


def new_mat(name, clear=True):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    if clear:
        m.node_tree.nodes.clear()
    return m, NT(m)


def simple_mat(name, color, rough=0.5, metal=0.0, emit=None, emit_strength=0.0):
    m, t = new_mat(name)
    t.principled(color=color, rough=rough, metal=metal, emit=emit, emit_strength=emit_strength)
    m.diffuse_color = (*color, 1) if len(color) == 3 else color
    return m


def emissive_mat(name, color, strength=4.0, base=None):
    m, t = new_mat(name)
    t.principled(color=base or (0, 0, 0), rough=0.4, emit=color, emit_strength=strength)
    return m


def assign(ob, mat, slot_only=False):
    if not slot_only:
        ob.data.materials.clear()
    ob.data.materials.append(mat)
    return ob


# ----------------------------------------------------------------- uv / bake
def smart_uv(objs, margin=0.003, angle=66, name=None, island_margin=None):
    select(objs)
    for o in objs:
        if name:
            if name not in o.data.uv_layers:
                o.data.uv_layers.new(name=name)
            o.data.uv_layers.active = o.data.uv_layers[name]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.reveal()
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=island_margin if island_margin is not None else margin,
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def pack_uv(objs, margin=0.004, rotate=True, method='FRACTION'):
    select(objs)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.select_all(action='SELECT')
    try:
        bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=rotate, scale=True, margin_method=method,
                                margin=margin, shape_method='CONCAVE')
    except TypeError:
        bpy.ops.uv.pack_islands(rotate=rotate, margin=margin)
    bpy.ops.object.mode_set(mode='OBJECT')


def scale_uv(ob, s, layer=None):
    uvl = ob.data.uv_layers[layer] if layer else ob.data.uv_layers.active
    for d in uvl.data:
        d.uv = d.uv * s


def new_image(name, res, alpha=False, non_color=False, float_buf=False):
    if name in bpy.data.images:
        bpy.data.images.remove(bpy.data.images[name])
    img = bpy.data.images.new(name, res, res, alpha=alpha, float_buffer=float_buf)
    if non_color:
        img.colorspace_settings.name = 'Non-Color'
    return img


def _set_bake_target(objs, img):
    """Put an active image node in every material of objs."""
    added = []
    for o in objs:
        for slot in o.material_slots:
            m = slot.material
            if m is None:
                continue
            nt = m.node_tree
            nd = nt.nodes.get('__bake__')
            if nd is None:
                nd = nt.nodes.new('ShaderNodeTexImage')
                nd.name = '__bake__'
                added.append((nt, nd))
            nd.image = img
            nt.nodes.active = nd
            nd.select = True
    return added


def _clear_bake_nodes(objs):
    for o in objs:
        for slot in o.material_slots:
            m = slot.material
            if m and '__bake__' in m.node_tree.nodes:
                m.node_tree.nodes.remove(m.node_tree.nodes['__bake__'])


def bake(objs, img, btype, pass_filter=None, margin=8, samples=16, uv_layer=None):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = samples
    sc.render.bake.margin = margin
    sc.render.bake.use_clear = True
    sc.render.bake.use_selected_to_active = False
    sc.render.bake.target = 'IMAGE_TEXTURES'
    if uv_layer:
        for o in objs:
            o.data.uv_layers.active = o.data.uv_layers[uv_layer]
    _set_bake_target(objs, img)
    select(objs)
    kw = dict(type=btype, margin=margin, use_clear=True)
    if pass_filter is not None:
        kw['pass_filter'] = pass_filter
    if btype == 'NORMAL':
        kw['normal_space'] = 'TANGENT'
    bpy.ops.object.bake(**kw)
    _clear_bake_nodes(objs)
    return img


def save_image(img, path, fmt='JPEG', quality=90):
    img.filepath_raw = path
    img.file_format = fmt
    sc = bpy.context.scene
    if fmt == 'JPEG':
        sc.render.image_settings.quality = quality
    img.save(filepath=path, quality=quality) if fmt == 'JPEG' else img.save(filepath=path)
    # reload so the datablock refers to the file on disk
    img.filepath = path
    img.source = 'FILE'
    img.reload()
    return img


def bake_pbr(objs, mat_name, res, out_prefix, do_rough=True, do_normal=True, do_ao=True, ao_strength=0.55,
             samples=16, metal_value=0.0, extra_emit=None, normal_png=False, aux_res=None):
    aux_res = aux_res or res
    """Bake the procedural material(s) on objs (already UV-unwrapped into one atlas) into
    textures and replace ALL their materials with a single image-based Principled material."""
    import numpy as np
    col = new_image(mat_name + '_col', res)
    bake(objs, col, 'DIFFUSE', pass_filter={'COLOR'}, samples=1)
    colpx = np.array(col.pixels[:]).reshape(-1, 4)
    if do_ao:
        ao = new_image(mat_name + '_ao', res, non_color=True)
        bake(objs, ao, 'AO', samples=max(samples, 32))
        aopx = np.array(ao.pixels[:]).reshape(-1, 4)[:, 0]
        a = 1.0 - ao_strength * (1.0 - aopx)
        colpx[:, :3] *= a[:, None]
        bpy.data.images.remove(ao)
    col.pixels[:] = colpx.ravel()
    save_image(col, os.path.join(TEX_DIR, out_prefix + '_col.jpg'), 'JPEG', 90)
    rgh = None
    if do_rough:
        rgh = new_image(mat_name + '_rgh', aux_res, non_color=True)
        bake(objs, rgh, 'ROUGHNESS', samples=1)
        px = np.array(rgh.pixels[:]).reshape(-1, 4)
        orm = np.ones_like(px)
        orm[:, 0] = 1.0
        orm[:, 1] = px[:, 0]
        orm[:, 2] = metal_value
        rgh.pixels[:] = orm.ravel()
        save_image(rgh, os.path.join(TEX_DIR, out_prefix + '_orm.jpg'), 'JPEG', 92)
        rgh.colorspace_settings.name = 'Non-Color'
    nrm = None
    if do_normal:
        nrm = new_image(mat_name + '_nrm', aux_res, non_color=True)
        bake(objs, nrm, 'NORMAL', samples=4)
        if normal_png:
            save_image(nrm, os.path.join(TEX_DIR, out_prefix + '_nrm.png'), 'PNG')
        else:
            save_image(nrm, os.path.join(TEX_DIR, out_prefix + '_nrm.jpg'), 'JPEG', 94)
        nrm.colorspace_settings.name = 'Non-Color'
    # new material
    m, t = new_mat(mat_name + '__tmp')
    build_image_material(t, col, rgh, nrm)
    for o in objs:
        o.data.materials.clear()
        o.data.materials.append(m)
    return m


def build_image_material(t, col, orm=None, nrm=None, emit_img=None, emit_strength=1.0, metal_factor=None, uv=None):
    bs = t.principled()
    ic = t.node('ShaderNodeTexImage', image=col)
    t.link(ic.outputs['Color'], bs.inputs['Base Color'])
    if orm is not None:
        io = t.node('ShaderNodeTexImage', image=orm)
        orm.colorspace_settings.name = 'Non-Color'
        sep = t.node('ShaderNodeSeparateColor')
        t.link(io.outputs['Color'], sep.inputs[0])
        t.link(sep.outputs[1], bs.inputs['Roughness'])
        t.link(sep.outputs[2], bs.inputs['Metallic'])
    if nrm is not None:
        inn = t.node('ShaderNodeTexImage', image=nrm)
        nrm.colorspace_settings.name = 'Non-Color'
        nm = t.node('ShaderNodeNormalMap')
        t.link(inn.outputs['Color'], nm.inputs['Color'])
        t.link(nm.outputs['Normal'], bs.inputs['Normal'])
    if emit_img is not None:
        ie = t.node('ShaderNodeTexImage', image=emit_img)
        t.link(ie.outputs['Color'], bs.inputs['Emission Color'])
        bs.inputs['Emission Strength'].default_value = emit_strength
    return bs


def rename_mat(m, name):
    old = bpy.data.materials.get(name)
    if old is not None and old != m:
        old.name = name + '__old'
    m.name = name


# ----------------------------------------------------------------- render
def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def camera(name='Cam', loc=(0, -5, 2), target=(0, 0, 1), lens=None, fov=None, ortho=None):
    cd = bpy.data.cameras.new(name)
    if fov:
        cd.sensor_fit = 'VERTICAL'
        cd.angle_y = math.radians(fov)
    elif lens:
        cd.lens = lens
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = ortho
    cd.clip_start = 0.05
    cd.clip_end = 200
    ob = bpy.data.objects.new(name, cd)
    link_obj(ob)
    ob.location = loc
    look_at(ob, target)
    bpy.context.scene.camera = ob
    return ob


def light(name, kind, loc, energy, color=(1, 1, 1), size=0.1, target=None, rot=None, spot=None):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind in ('POINT', 'SPOT'):
        ld.shadow_soft_size = size
    elif kind == 'AREA':
        ld.size = size
    elif kind == 'SUN':
        ld.angle = size
    if spot and kind == 'SPOT':
        ld.spot_size = math.radians(spot)
        ld.spot_blend = 0.6
    ob = bpy.data.objects.new(name, ld)
    link_obj(ob)
    ob.location = loc
    if target is not None:
        look_at(ob, target)
    if rot is not None:
        ob.rotation_euler = rot
    return ob


def render(path, res=(1280, 720), samples=96, cam=None):
    sc = bpy.context.scene
    if cam:
        sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('RENDERED', path)


def studio_lights(scale=1.0, warm=True):
    """Moody preview rig echoing the game palette: warm key, teal rim, indigo fill."""
    world_color((0.03, 0.045, 0.08), 1.0)
    light('Key', 'AREA', (-2.2 * scale, -3.0 * scale, 3.2 * scale), 400 * scale * scale, (1.0, 0.78, 0.55), size=2.0 * scale, target=(0, 0, 0.7 * scale))
    light('Rim', 'AREA', (2.4 * scale, 2.6 * scale, 2.6 * scale), 350 * scale * scale, (0.35, 0.65, 1.0), size=1.5 * scale, target=(0, 0, 0.8 * scale))
    light('Fill', 'AREA', (3.0 * scale, -2.5 * scale, 1.0 * scale), 70 * scale * scale, (0.45, 0.5, 0.75), size=3.0 * scale, target=(0, 0, 0.6 * scale))


def ground(size=10, color=(0.09, 0.08, 0.09), z=0.0):
    bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, z))
    g = bpy.context.active_object
    g.name = '__ground'
    assign(g, simple_mat('__ground_mat', color, 0.8))
    return g


# ----------------------------------------------------------------- export
def export_glb(path, objs, extra=None):
    select(objs)
    kw = dict(filepath=path, export_format='GLB', use_selection=True, export_apply=True, export_yup=True,
              export_image_format='AUTO', export_jpeg_quality=90, export_materials='EXPORT',
              export_cameras=False, export_lights=False, export_extras=True, export_animations=False,
              export_texcoords=True, export_normals=True, export_tangents=False)
    if extra:
        kw.update(extra)
    try:
        bpy.ops.export_scene.gltf(**kw)
    except TypeError as e:
        print('export kw issue', e)
        for k in ('export_jpeg_quality', 'export_extras'):
            kw.pop(k, None)
        bpy.ops.export_scene.gltf(**kw)
    print('EXPORTED', path, os.path.getsize(path))


def descendants(ob):
    out = [ob]
    for c in ob.children:
        out += descendants(c)
    return out
