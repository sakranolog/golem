"""Bake full Cycles lighting of the workshop into lightmap atlases and export public/models/workshop.glb.
Usage: Blender -b -P bake_workshop.py -- [--fast] [--samples N] [--res N]"""
import bpy, bmesh, math, os, sys, json
import numpy as np
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(__file__))
import importlib, lib_common as L
importlib.reload(L)

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
FAST = '--fast' in argv


def arg(name, default):
    return type(default)(argv[argv.index(name) + 1]) if name in argv else default


RES = arg('--res', 1024 if FAST else 4096)
SAMPLES = arg('--samples', 64 if FAST else 384)
EXPOSURE = arg('--exposure', 0.0)
ATLAS_RES = {'Dais': RES, 'Room': RES, 'Furn': max(1024, RES // 2), 'Clutter': RES}

bpy.ops.wm.open_mainfile(filepath=os.path.join(L.BLEND_DIR, 'workshop_src.blend'))
L.setup_cycles(bpy.context.scene, samples=SAMPLES, denoise=False)
sc = bpy.context.scene
sc.view_settings.exposure = EXPOSURE
meta = json.load(open(os.path.join(L.BLEND_DIR, 'workshop_meta.json')))
W = meta['weights']
sc.cycles.max_bounces = 6
sc.cycles.diffuse_bounces = 4
sc.cycles.glossy_bounces = 1
sc.cycles.transmission_bounces = 2
sc.cycles.sample_clamp_indirect = 8.0
sc.cycles.use_light_tree = True

TEXOUT = L.TEX_DIR
baked = {}


def denoise_exr(src_img, out_path):
    """Run OIDN on a float image through the compositor; writes linear EXR to out_path."""
    dsc = bpy.data.scenes.new('DenoiseScene')
    dsc.render.engine = 'BLENDER_WORKBENCH'
    dsc.render.resolution_x, dsc.render.resolution_y = src_img.size
    dsc.render.resolution_percentage = 100
    dsc.render.image_settings.file_format = 'OPEN_EXR'
    dsc.render.image_settings.color_depth = '32'
    dsc.view_settings.view_transform = 'Standard'
    ng = bpy.data.node_groups.new('DN', 'CompositorNodeTree')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    ni = ng.nodes.new('CompositorNodeImage'); ni.image = src_img
    dn = ng.nodes.new('CompositorNodeDenoise')
    try:
        dn.inputs['HDR'].default_value = True
    except Exception:
        pass
    out = ng.nodes.new('NodeGroupOutput')
    ng.links.new(ni.outputs[0], dn.inputs[0])
    ng.links.new(dn.outputs[0], out.inputs[0])
    dsc.compositing_node_group = ng
    dsc.render.filepath = out_path
    win_scene = bpy.context.window.scene if bpy.context.window else None
    bpy.ops.render.render(write_still=True, scene=dsc.name)
    bpy.data.scenes.remove(dsc)
    return out_path


def grade(img):
    """Cinematic split-tone on the linear lightmap: teal/indigo shadows, warm amber highlights."""
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4)
    rgb = px[:, :3]
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    def ss(e0, e1, x):
        t = np.clip((x - e0) / (e1 - e0), 0, 1)
        return t * t * (3 - 2 * t)
    sh = 1.0 - ss(0.0, 0.18, lum)
    hi = ss(0.35, 1.6, lum)
    tint_sh = np.array([0.80, 0.96, 1.25], np.float32)
    tint_hi = np.array([1.06, 1.0, 0.90], np.float32)
    rgb *= (1 + (tint_sh - 1) * (sh * 0.9)[:, None]) * (1 + (tint_hi - 1) * hi[:, None])
    px[:, :3] = rgb
    img.pixels[:] = px.ravel()


def tonemap_save(exr_path, jpg_path, name):
    """Load the linear lightmap, grade it, apply the scene view transform (AgX) and save display-referred JPEG."""
    img = bpy.data.images.load(exr_path, check_existing=False)
    img.name = name + '_lin'
    grade(img)
    s = bpy.context.scene
    s.render.image_settings.file_format = 'JPEG'
    s.render.image_settings.quality = 90
    s.render.image_settings.color_management = 'FOLLOW_SCENE'
    img.save_render(jpg_path, scene=s)
    out = bpy.data.images.load(jpg_path, check_existing=False)
    out.name = name
    return out


def fill_margins(img, iters=24):
    """Dilate valid texels into empty (alpha==0) area so denoise/mip-mapping never pulls black into seams."""
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, 4)
    valid = px[:, :, 3] > 0.5
    col = px[:, :, :3].copy()
    for _ in range(iters):
        if valid.all():
            break
        acc = np.zeros_like(col); cnt = np.zeros((h, w), np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sv = np.roll(valid, (dy, dx), (0, 1)); sc_ = np.roll(col, (dy, dx), (0, 1))
            acc += sc_ * sv[:, :, None]; cnt += sv
        new = (~valid) & (cnt > 0)
        col[new] = acc[new] / cnt[new][:, None]
        valid = valid | new
    px[:, :, :3] = col
    px[:, :, 3] = 1.0
    img.pixels[:] = px.ravel()


def uv_area(o):
    import bmesh
    bm = bmesh.new(); bm.from_mesh(o.data); lay = bm.loops.layers.uv.active; tot = 0
    for f in bm.faces:
        p = [l[lay].uv for l in f.loops]
        tot += abs(sum(p[i].x * p[(i + 1) % len(p)].y - p[(i + 1) % len(p)].x * p[i].y for i in range(len(p)))) / 2
    bm.free()
    return tot


for atlas, names in meta['static'].items():
    objs = [bpy.data.objects[n] for n in names if n in bpy.data.objects]
    if not objs:
        continue
    print('== ATLAS', atlas, len(objs))
    # group by weight, join groups, unwrap jointly, scale by weight, join, pack
    groups = {}
    for o in objs:
        groups.setdefault(round(W.get(o.name, 1.0), 2), []).append(o)
    gobjs = []
    for w, lst in groups.items():
        g = L.join(lst, f'{atlas}_w{w}')
        g['w'] = w
        gobjs.append(g)
    for g in gobjs:
        for uvl in list(g.data.uv_layers):
            g.data.uv_layers.remove(uvl)
        g.data.uv_layers.new(name='UVMap')
    L.smart_uv(gobjs, island_margin=0.0, angle=50)
    for g in gobjs:
        L.scale_uv(g, math.sqrt(g['w']) if g['w'] < 1 else g['w'])
    ob = L.join(gobjs, 'Baked_' + atlas)
    print('UV AREA pre-pack', atlas, uv_area(ob))
    L.pack_uv([ob], margin=5.0 / ATLAS_RES[atlas], method='ADD')
    print('UV AREA packed', atlas, uv_area(ob))
    res = ATLAS_RES[atlas]
    img = L.new_image('lm_' + atlas, res, alpha=True, float_buf=True)
    img.generated_color = (0, 0, 0, 0)
    print('baking', atlas, res, SAMPLES)
    L.bake([ob], img, 'COMBINED', pass_filter={'DIRECT', 'INDIRECT', 'DIFFUSE', 'TRANSMISSION', 'EMIT'}, margin=0, samples=SAMPLES)
    fill_margins(img, 32)
    raw = os.path.join(TEXOUT, f'lm_{atlas}_raw.exr')
    img.filepath_raw = raw
    img.file_format = 'OPEN_EXR'
    img.save()
    baked[atlas] = (ob, img)
    print('UV AREA', atlas, uv_area(ob))

for atlas, (ob, img) in list(baked.items()):
    dn = denoise_exr(img, os.path.join(TEXOUT, f'lm_{atlas}_dn.exr'))
    jpg = os.path.join(TEXOUT, f'workshop_{atlas.lower()}_lightmap.jpg')
    out = tonemap_save(dn, jpg, 'Baked_' + atlas + '_tex')
    baked[atlas] = (ob, out)

# ---------------------------------------------------------------- swap to unlit lightmap materials
for atlas, (ob, img) in baked.items():
    m, t = L.new_mat('Baked_' + atlas)
    it = t.node('ShaderNodeTexImage', image=img)
    em = t.node('ShaderNodeEmission')
    out = t.node('ShaderNodeOutputMaterial')
    t.link(it.outputs['Color'], em.inputs['Color'])
    t.link(em.outputs[0], out.inputs['Surface'])
    ob.data.materials.clear()
    ob.data.materials.append(m)

# window sky: bake its procedural emission into a small texture so glTF keeps it
win = bpy.data.objects.get('Emit_Window')
if win:
    for uvl in list(win.data.uv_layers):
        win.data.uv_layers.remove(uvl)
    win.data.uv_layers.new(name='UVMap')
    L.smart_uv([win], island_margin=0.01)
    wimg = L.new_image('window_sky', 512)
    L.bake([win], wimg, 'EMIT', samples=1, margin=8)
    L.save_image(wimg, os.path.join(TEXOUT, 'workshop_window_sky.jpg'), 'JPEG', 90)
    m, t = L.new_mat('Emit_WindowSky')
    bs = t.principled(color=(0, 0, 0), rough=1.0)
    ie = t.node('ShaderNodeTexImage', image=wimg)
    t.link(ie.outputs['Color'], bs.inputs['Emission Color'])
    bs.inputs['Emission Strength'].default_value = 2.2
    win.data.materials.clear(); win.data.materials.append(m)

# ---------------------------------------------------------------- light empties (game lights)
emp = []
for Ld in meta['lights']:
    e = bpy.data.objects.new(Ld['name'], None)
    e.empty_display_type = 'SINGLE_ARROW' if Ld['direction'] else 'SPHERE'
    e.empty_display_size = 0.3
    L.link_obj(e)
    e.location = Ld['pos']
    if Ld['direction']:
        d = Vector(Ld['direction'])
        # orient the empty so its local -Z points along the light direction (glTF light convention after Y-up conversion)
        e.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        gd = [d.x, d.z, -d.y]
        e['direction_gltf'] = gd
    e['light_type'] = Ld['type']
    e['color'] = Ld['color']
    e['blender_power'] = Ld['power']
    emp.append(e)

# ---------------------------------------------------------------- previews of the baked result (what the game shows unlit)
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
sc.view_settings.exposure = 0.0
for o in list(bpy.data.objects):
    if o.type == 'LIGHT':
        o.hide_render = True
sc.world.node_tree.nodes['Background'].inputs[1].default_value = 0.0
for o in bpy.data.objects:   # unbaked leftovers? hide anything not exported
    if o.type == 'MESH' and not (o.name.startswith('Baked_') or o.name.startswith('Emit_')):
        print('LEFTOVER', o.name)
        o.hide_render = True
cam = L.camera('GameCam_b', (0, -9.5, 7.5), (0, 0, 0), fov=35)
L.render(os.path.join(L.PREVIEW_DIR, 'workshop_baked_gamecam.png'), (1280, 720), 16, cam)
for k, ang in (('orbitL', -20), ('orbitR', 20)):
    a = math.radians(ang)
    c = L.camera('Orb' + k, (9.5 * math.sin(a), -9.5 * math.cos(a), 7.5), (0, 0, 0), fov=35)
    L.render(os.path.join(L.PREVIEW_DIR, f'workshop_baked_{k}.png'), (1280, 720), 16, c)
cam2 = L.camera('Wide_b', (0, -7.5, 2.6), (0, 4, 2.0), lens=18)
L.render(os.path.join(L.PREVIEW_DIR, 'workshop_baked_wide.png'), (1280, 720), 16, cam2)

# ---------------------------------------------------------------- export (unlit = image straight into the output)
for atlas, (ob, img) in baked.items():
    m = bpy.data.materials['Baked_' + atlas]
    nt = m.node_tree
    it = [n for n in nt.nodes if n.type == 'TEX_IMAGE'][0]
    out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    for n in [n for n in nt.nodes if n.type == 'EMISSION']:
        nt.nodes.remove(n)
    nt.links.new(it.outputs['Color'], out.inputs['Surface'])
exp = [o for o, _ in baked.values()] + [o for o in bpy.data.objects if o.name.startswith('Emit_')] + emp
tris = {o.name: L.tri_count(o) for o in exp if o.type == 'MESH'}
print('WORKSHOP_TRIS', sum(tris.values()), tris)
L.export_glb(os.path.join(L.MODELS_DIR, 'workshop.glb'), exp, extra={'export_normals': False, 'export_jpeg_quality': 88})
json.dump({'tris': tris, 'res': RES, 'samples': SAMPLES}, open(os.path.join(L.BLEND_DIR, 'workshop_bake_info.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(L.BLEND_DIR, 'workshop_baked.blend'))
