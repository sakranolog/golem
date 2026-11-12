"""Re-import each exported GLB into a fresh scene, check the contract, render the re-imported result.
Writes blender/verify_report.json and previews/verify_*.png"""
import bpy, math, os, sys, json
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.dirname(__file__))
import importlib, lib_common as L
importlib.reload(L)

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
which = argv[0] if argv else 'all'
report = {}

GOLEM_TREE = {
    'Golem': None, 'Hips': 'Golem', 'Torso': 'Hips', 'Head': 'Torso', 'Eye_L': 'Head', 'Eye_R': 'Head', 'Brow_L': 'Head', 'Brow_R': 'Head',
    'Jaw': 'Head', 'ArmL_Upper': 'Torso', 'ArmL_Lower': 'ArmL_Upper', 'HandL': 'ArmL_Lower', 'ArmR_Upper': 'Torso',
    'ArmR_Lower': 'ArmR_Upper', 'HandR': 'ArmR_Lower', 'LegL': 'Hips', 'LegR': 'Hips'}
PROP_NAMES = ['Tile_A', 'Tile_B', 'Tile_C', 'TileGoal', 'Block_Books', 'Block_Crate', 'Block_Stone', 'Candle', 'Pedestal', 'Jug'] + \
             [f'JugShard_{i}' for i in range(1, 6)] + ['Plant_Wilted', 'Plant_Bloom', 'Letter_Alef', 'Letter_Mem', 'Letter_Tav', 'Cat',
                                                       'Cat_Awake', 'Broom', 'DustPile', 'Scroll', 'Star']


def fresh():
    L.reset_scene()


def imp(path):
    bpy.ops.import_scene.gltf(filepath=path)
    return list(bpy.context.scene.objects)


def bbox(objs):
    mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
    for o in objs:
        if o.type != 'MESH':
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
    return mn, mx


def mat_info(o):
    out = []
    for s in o.material_slots:
        m = s.material
        if m is None:
            continue
        imgs = [n.image.name for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
        out.append({'name': m.name, 'images': imgs})
    return out


def check_golem():
    fresh()
    objs = imp(os.path.join(L.MODELS_DIR, 'golem.glb'))
    r = {'errors': [], 'nodes': {}}
    byname = {o.name: o for o in objs}
    for n, par in GOLEM_TREE.items():
        o = byname.get(n)
        if o is None:
            r['errors'].append('missing ' + n)
            continue
        pn = o.parent.name if o.parent else None
        if pn != par:
            r['errors'].append(f'{n} parent {pn} != {par}')
        q = o.rotation_quaternion if o.rotation_mode == 'QUATERNION' else o.rotation_euler.to_quaternion()
        rot_ok = abs(q.w) > 0.99999
        sc_ok = all(abs(s - 1) < 1e-5 for s in o.scale)
        if not rot_ok or not sc_ok:
            r['errors'].append(f'{n} non-identity rot/scale {tuple(q)} {tuple(o.scale)}')
        # glTF-space local translation (Y up): (x, z, -y)
        t = o.location
        r['nodes'][n] = {'parent': pn, 'local_translation_gltf': [round(t.x, 4), round(t.z, 4), round(-t.y, 4)],
                         'world_pivot_gltf': [round((o.matrix_world.translation).x, 4), round(o.matrix_world.translation.z, 4),
                                              round(-o.matrix_world.translation.y, 4)],
                         'materials': mat_info(o) if o.type == 'MESH' else []}
    extra = [o.name for o in objs if o.name not in GOLEM_TREE]
    if extra:
        r['extra_nodes'] = extra
    mn, mx = bbox(objs)
    r['bbox_gltf'] = {'size': [round(mx.x - mn.x, 3), round(mx.z - mn.z, 3), round(mx.y - mn.y, 3)],
                      'min_y': round(mn.z, 3), 'max_y': round(mx.z, 3)}
    mats = {m.name for o in objs if o.type == 'MESH' for m in [s.material for s in o.material_slots] if m}
    for need in ('Clay', 'Rune', 'Eye'):
        if need not in mats:
            r['errors'].append('missing material ' + need)
    r['materials'] = sorted(mats)
    r['tris'] = sum(L.tri_count(o) for o in objs)
    # render re-import + a posed check (arms rotated 60 deg) for gaps
    L.ground(10, (0.07, 0.065, 0.075))
    L.studio_lights()
    cam = L.camera('vc', (1.9, -2.6, 1.2), (0, 0, 0.66), lens=50)
    L.render(os.path.join(L.PREVIEW_DIR, 'verify_golem.png'), (800, 900), 48, cam)
    byname['ArmL_Upper'].rotation_mode = 'XYZ'
    byname['ArmL_Upper'].rotation_euler = (math.radians(-60), 0, 0)     # swing forward
    byname['ArmR_Upper'].rotation_mode = 'XYZ'
    byname['ArmR_Upper'].rotation_euler = (0, math.radians(-60), 0)      # raise sideways (about glTF Z)
    byname['ArmR_Lower'].rotation_mode = 'XYZ'
    byname['ArmR_Lower'].rotation_euler = (math.radians(-60), 0, 0)
    byname['Head'].rotation_mode = 'XYZ'
    byname['Head'].rotation_euler = (0, 0, math.radians(35))
    byname['LegL'].rotation_mode = 'XYZ'
    byname['LegL'].rotation_euler = (math.radians(-45), 0, 0)
    byname['Jaw'].rotation_mode = 'XYZ'
    byname['Jaw'].rotation_euler = (math.radians(20), 0, 0)
    L.render(os.path.join(L.PREVIEW_DIR, 'verify_golem_posed.png'), (800, 900), 48, cam)
    return r


def check_props():
    fresh()
    objs = imp(os.path.join(L.MODELS_DIR, 'props.glb'))
    r = {'errors': [], 'props': {}}
    tops = [o for o in objs if o.parent is None]
    names = {o.name for o in tops}
    for n in PROP_NAMES:
        if n not in names:
            r['errors'].append('missing ' + n)
    for o in tops:
        mn, mx = bbox(L.descendants(o))
        r['props'][o.name] = {'tris': sum(L.tri_count(c) for c in L.descendants(o)),
                              'translation_gltf': [round(o.location.x, 3), round(o.location.z, 3), round(-o.location.y, 3)],
                              'size_gltf': [round(mx.x - mn.x, 3), round(mx.z - mn.z, 3), round(mx.y - mn.y, 3)],
                              'min_y': round(mn.z, 3), 'max_y': round(mx.z, 3),
                              'children': [c.name for c in o.children], 'materials': mat_info(o)}
    c = bpy.data.objects.get('Candle')
    if not c or 'Flame' not in [k.name for k in c.children]:
        r['errors'].append('Candle has no Flame child')
    # lay out and render
    sp = 1.3
    for i, o in enumerate(sorted(tops, key=lambda o: PROP_NAMES.index(o.name) if o.name in PROP_NAMES else 99)):
        o.location = Vector(((i % 7) * sp, -(i // 7) * sp, o.location.z)) + (Vector((o.location.x, o.location.y, 0)) if o.name.startswith('JugShard') else Vector())
    L.ground(40, (0.06, 0.06, 0.07), z=-0.2)
    L.studio_lights(scale=3.0)
    for lo in [o for o in bpy.data.objects if o.type == 'LIGHT']:
        lo.location.x += 3.9; lo.location.y -= 2.0
    cam = L.camera('vc', (3.9, -9.0, 6.5), (3.9, -2.2, 0.0), lens=32)
    L.render(os.path.join(L.PREVIEW_DIR, 'verify_props.png'), (1600, 1000), 48, cam)
    return r


def check_workshop():
    fresh()
    objs = imp(os.path.join(L.MODELS_DIR, 'workshop.glb'))
    r = {'errors': [], 'meshes': {}, 'empties': {}}
    for o in objs:
        if o.type == 'MESH':
            mn, mx = bbox([o])
            r['meshes'][o.name] = {'tris': L.tri_count(o), 'materials': mat_info(o)}
        elif o.type == 'EMPTY':
            p = o.matrix_world.translation
            r['empties'][o.name] = {'pos_gltf': [round(p.x, 3), round(p.z, 3), round(-p.y, 3)],
                                    'props': {k: (list(v) if hasattr(v, '__len__') and not isinstance(v, str) else v) for k, v in o.items()}}
    # clear-circle check (game coords): nothing but the dais within r<5.5 above y=-0.25
    for o in objs:
        if o.type != 'MESH' or o.name in ('Baked_Dais', 'Emit_DaisRunes'):
            continue
        me = o.data
        bad = 0
        for v in me.vertices:
            w = o.matrix_world @ v.co
            if w.to_2d().length < 5.495 and -0.25 < w.z < 7.5:
                bad += 1
        if bad:
            r['errors'].append(f'{o.name}: {bad} verts inside the clear circle')
    r['tris'] = sum(L.tri_count(o) for o in objs if o.type == 'MESH')
    # unlit check
    for o in objs:
        if o.name.startswith('Baked_'):
            m = o.material_slots[0].material
            r['meshes'][o.name]['unlit_import'] = any(n.type == 'LIGHT_PATH' for n in m.node_tree.nodes) or any(
                n.type == 'EMISSION' for n in m.node_tree.nodes) or any(n.type == 'BACKGROUND' for n in m.node_tree.nodes)
    sc = bpy.context.scene
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    L.world_color((0, 0, 0), 0)
    cam = L.camera('vc', (0, -9.5, 7.5), (0, 0, 0), fov=35)
    L.render(os.path.join(L.PREVIEW_DIR, 'verify_workshop_gamecam.png'), (1280, 720), 16, cam)
    return r


if which in ('all', 'golem'):
    report['golem'] = check_golem()
if which in ('all', 'props'):
    report['props'] = check_props()
if which in ('all', 'workshop'):
    report['workshop'] = check_workshop()
path = os.path.join(L.BLEND_DIR, f'verify_report_{which}.json')
json.dump(report, open(path, 'w'), indent=1)
for k, v in report.items():
    print('VERIFY', k, 'errors:', v['errors'], 'tris:', v.get('tris'))
