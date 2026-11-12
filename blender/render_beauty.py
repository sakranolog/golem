"""Beauty shot: the golem standing on a few tiles on the dais inside the fully path-traced workshop.
Imports the exported GLBs (so it also proves they survive export)."""
import bpy, math, os, sys
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__))
import importlib, lib_common as L
importlib.reload(L)

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
FAST = '--fast' in argv
bpy.ops.wm.open_mainfile(filepath=os.path.join(L.BLEND_DIR, 'workshop_src.blend'))
sc = L.setup_cycles(bpy.context.scene, samples=96 if FAST else 512, denoise=True)


def import_glb(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    return [o for o in bpy.data.objects if o not in before]


props = import_glb(os.path.join(L.MODELS_DIR, 'props.glb'))
byname = {o.name: o for o in props}
golem = import_glb(os.path.join(L.MODELS_DIR, 'golem.glb'))
gb = {o.name: o for o in golem}
# hide all props, then place copies on a small board (1 m grid, Blender X/Y; game tile tops at y=0)
for o in props:
    o.hide_render = True
    o.hide_viewport = True


def place(name, x, y, rotz=0.0, z=0.0):
    src = byname[name]
    objs = L.descendants(src)
    mp = {}
    for o in objs:
        c = o.copy()
        if o.data:
            c.data = o.data
        L.link_obj(c)
        c.hide_render = False
        c.hide_viewport = False
        mp[o] = c
    for o, c in mp.items():
        if o.parent in mp:
            c.parent = mp[o.parent]
    root = mp[src]
    root.location = (x, y, z)
    root.rotation_mode = 'XYZ'
    root.rotation_euler = (0, 0, rotz)
    return root


layout = [
    ('Tile_A', -1, 1), ('Tile_B', 0, 1), ('Tile_C', 1, 1), ('Tile_B', 2, 1),
    ('Tile_C', -1, 0), ('Tile_A', 0, 0), ('Tile_B', 1, 0), ('TileGoal', 2, 0),
    ('Tile_B', -1, -1), ('Tile_C', 0, -1), ('Tile_A', 1, -1), ('Tile_C', 2, -1),
    ('Tile_A', -2, 0), ('Tile_C', -2, 1),
]
for i, (n, x, y) in enumerate(layout):
    place(n, x, y, rotz=(i % 4) * math.pi / 2)
place('Block_Books', -2, 1)
place('Block_Crate', 2, 1, 0.1)
place('Candle', -1.3, -1.25)
place('Jug', 1.25, -0.75, 0.6)
place('Plant_Wilted', -0.7, 1.25)
place('Letter_Alef', 2.0, 0.0, 0.0, z=0.45)
place('Cat', -1.6, -0.3, 0.8)
place('Star', 0.6, -1.3, 0.3)
# golem on tile (0, 0), turned slightly toward camera, one arm a little raised (rigid parts rotated)
root = gb['Golem']
root.location = (0.0, 0.0, 0.0)
root.rotation_mode = 'XYZ'
root.rotation_euler = (0, 0, math.radians(-12))
for n, e in (('ArmR_Upper', (0, math.radians(-25), 0)), ('ArmR_Lower', (math.radians(-35), 0, 0)), ('Head', (math.radians(8), 0, math.radians(10)))):
    o = gb[n]
    o.rotation_mode = 'XYZ'
    o.rotation_euler = e

# volumetric haze only for the beauty render (moon shafts)
vol = bpy.data.objects.new('Haze', bpy.data.meshes.new('Haze'))
import bmesh
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bm.to_mesh(vol.data)
bm.free()
L.link_obj(vol)
vol.scale = (16, 21, 8.4)
vol.location = (0, -3.25, 4.2)
vm, t = L.new_mat('HazeMat')
pv = t.node('ShaderNodeVolumePrincipled')
pv.inputs['Density'].default_value = 0.012
pv.inputs['Anisotropy'].default_value = 0.45
out = t.node('ShaderNodeOutputMaterial')
t.link(pv.outputs[0], out.inputs['Volume'])
vol.data.materials.append(vm)
sc.cycles.volume_bounces = 1
try:
    sc.cycles.volume_step_rate = 4.0
except Exception:
    pass

# beauty-only hero lighting (not part of the bake): warm key + turquoise rim on the golem
k = L.light('BeautyKey', 'AREA', (-1.6, -2.4, 2.6), 160, (1.0, 0.72, 0.45), size=1.6, target=(0, 0, 0.8))
r = L.light('BeautyRim', 'AREA', (1.4, 2.0, 2.2), 120, (0.3, 0.8, 1.0), size=1.0, target=(0, 0, 0.9))
cams = {
    'beauty': ((2.5, -3.9, 1.75), (0.15, 0.35, 0.72), 32),
    'beauty_gamecam': ((0, -9.5, 7.5), (0, 0, 0), None),
}
for k, (loc, tgt, lens) in cams.items():
    if lens:
        cam = L.camera('C_' + k, loc, tgt, lens=lens)
    else:
        cam = L.camera('C_' + k, loc, tgt, fov=35)
    L.render(os.path.join(L.PREVIEW_DIR, f'{k}.png'), (1600, 900), sc.cycles.samples, cam)
