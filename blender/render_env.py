"""Render the lit (unbaked, fully path-traced) workshop as an equirectangular HDR from game (0, 1.2, 0)
-> public/env/workshop_env.hdr. Orientation matches three.js EquirectangularReflectionMapping
(image centre = +X, Blender world-environment convention, which equals three.js's)."""
import bpy, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import importlib, lib_common as L
importlib.reload(L)

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
FAST = '--fast' in argv
bpy.ops.wm.open_mainfile(filepath=os.path.join(L.BLEND_DIR, 'workshop_src.blend'))
sc = L.setup_cycles(bpy.context.scene, samples=64 if FAST else 1024, denoise=True)
sc.view_settings.view_transform = 'Standard'
sc.view_settings.look = 'None'
cd = bpy.data.cameras.new('EnvCam')
cd.type = 'PANO'
try:
    cd.panorama_type = 'EQUIRECTANGULAR'
except Exception:
    cd.cycles.panorama_type = 'EQUIRECTANGULAR'
cam = bpy.data.objects.new('EnvCam', cd)
L.link_obj(cam)
cam.location = (0, 0, 1.2)          # game (0, 1.2, 0)
cam.rotation_euler = (math.radians(90), 0, math.radians(-90))   # centre of image looks down +X
sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y = 2048, 1024
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'HDR'
sc.render.filepath = os.path.join(L.ENV_DIR, 'workshop_env.hdr')
bpy.ops.render.render(write_still=True)
# LDR preview for eyeballing
sc.view_settings.view_transform = 'AgX'
img = bpy.data.images.load(os.path.join(L.ENV_DIR, 'workshop_env.hdr'))
sc.render.image_settings.file_format = 'PNG'
img.save_render(os.path.join(L.PREVIEW_DIR, 'workshop_env_preview.png'), scene=sc)
print('ENV DONE')
