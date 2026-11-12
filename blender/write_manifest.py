"""Collect everything the game needs into public/models/manifest.json (plain python3, no Blender needed)."""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODELS = os.path.join(ROOT, 'public', 'models')
ENV = os.path.join(ROOT, 'public', 'env')


def load(p):
    p = os.path.join(HERE, p)
    return json.load(open(p)) if os.path.exists(p) else {}


vg = load('verify_report_golem.json').get('golem', {})
vp = load('verify_report_props.json').get('props', {})
vw = load('verify_report_workshop.json').get('workshop', {})
meta = load('workshop_meta.json')
bake = load('workshop_bake_info.json')


def size(p):
    return os.path.getsize(p) if os.path.exists(p) else None


def b2g(v):  # Blender (x, y, z) Z-up -> glTF (x, z, -y) Y-up
    return [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]


lights = []
for Ld in meta.get('lights', []):
    t = Ld['type']
    e = {'name': Ld['name'],
         'type': {'SUN': 'directional', 'POINT': 'point', 'SPOT': 'spot', 'AREA': 'area'}[t],
         'position': b2g(Ld['pos']),
         'color': [round(c, 3) for c in Ld['color']],
         'blender_power': Ld['power'],
         'blender_unit': 'W/m^2 (sun strength)' if t == 'SUN' else 'W',
         # glTF KHR_lights_punctual conversions (same math as Blender's exporter)
         'intensity_physical': round(Ld['power'] * 683, 1) if t == 'SUN' else round(Ld['power'] / (4 * math.pi) * 683, 1),
         'intensity_physical_unit': 'lux' if t == 'SUN' else 'candela',
         'intensity_threejs_suggested': round(Ld['power'] * 0.35, 3) if t == 'SUN' else round(Ld['power'] / (4 * math.pi), 3),
         'radius': Ld.get('radius')}
    if Ld.get('direction'):
        d = Ld['direction']
        e['direction'] = b2g(d)
    if t == 'POINT':
        e['suggested_distance'] = 8.0 if 'Lantern' in Ld['name'] or 'Fire' in Ld['name'] else 3.0
        e['suggested_decay'] = 2
    lights.append(e)

manifest = {
    'generator': 'blender/build_all.sh (Blender 5.3, Cycles/Metal), fully procedural',
    'conventions': {
        'units': 'metres', 'up': '+Y', 'forward': 'models face +Z',
        'game_camera': {'position': [0, 7.5, 9.5], 'target': [0, 0, 0], 'fov_deg': 35, 'orbit_deg': 20},
        'board': 'tiles are 1.0 x 1.0 x 0.2, top at y=0, sit on the dais whose top is at y=-0.2',
    },
    'files': {
        'golem': {
            'path': 'models/golem.glb', 'bytes': size(os.path.join(MODELS, 'golem.glb')), 'triangles': vg.get('tris'),
            'bbox_size': vg.get('bbox_gltf', {}).get('size'), 'height': vg.get('bbox_gltf', {}).get('max_y'),
            'skinned': False,
            'hierarchy': {n: d['parent'] for n, d in vg.get('nodes', {}).items()},
            'pivots_world': {n: d['world_pivot_gltf'] for n, d in vg.get('nodes', {}).items()},
            'local_translations': {n: d['local_translation_gltf'] for n, d in vg.get('nodes', {}).items()},
            'rest_pose': 'every node has identity rotation and unit scale; local axes == world axes. Rotate about local X to swing '
                         'arms/legs forward/back, about Z to swing them sideways.',
            'materials': {
                'Clay': 'baked 2K base colour / ORM / normal textures',
                'Rune': 'emissive turquoise (chest + back sigils, forearm bands, forehead word), animate emissiveIntensity',
                'Eye': 'emissive turquoise eyes (Eye_L, Eye_R are separate nodes), animate emissiveIntensity',
                'MouthDark': 'dark mouth interior (behind the Jaw)'},
            'forehead_word': 'אמת (emet) engraved in Rune material on the Head; it reads correctly right-to-left',
        },
        'props': {
            'path': 'models/props.glb', 'bytes': size(os.path.join(MODELS, 'props.glb')),
            'nodes': {n: {'size': d['size_gltf'], 'triangles': d['tris'], 'min_y': d['min_y'], 'max_y': d['max_y'],
                          'translation': d['translation_gltf'], 'children': d['children'],
                          'materials': [m['name'] for m in d['materials']]} for n, d in vp.get('props', {}).items()},
            'notes': {
                'origins': 'origin at centre of the base on the ground (y=0) for every prop, except: Tile_*/TileGoal top face at y=0 '
                           '(body to y=-0.2); Letter_* origin at the letter centre; JugShard_* origin at the shard centre.',
                'JugShard_n': 'exported at their rest offset relative to an un-broken Jug placed at the origin, so placing all five at the '
                              'jug position reassembles the jug; the translations are listed per shard.',
                'Candle': 'child node Flame (material Flame, emissive) has its origin at the wick tip; scale/flicker it.',
                'TileGoal': 'engraved rings use emissive material Glow.',
                'Letter_*': 'material Gold (metallic). Letters face +Z.',
                'Star': 'stands upright facing +Z, origin at its lowest point.',
            },
        },
        'workshop': {
            'path': 'models/workshop.glb', 'bytes': size(os.path.join(MODELS, 'workshop.glb')), 'triangles': vw.get('tris'),
            'meshes': {n: d['tris'] for n, d in vw.get('meshes', {}).items()},
            'lightmap_resolution': bake.get('res'), 'bake_samples': bake.get('samples'),
            'notes': {
                'Baked_*': 'full Cycles lighting (direct + indirect + emission, denoised) baked into the base colour texture. Exported with '
                           'KHR_materials_unlit. The textures are display-referred (AgX tone mapping already applied, sRGB), so render them '
                           'with toneMapped = false (or NoToneMapping) and no extra lighting.',
                'Emit_*': 'emissive meshes for bloom: Emit_Window (night sky + moon texture), Emit_KilnFire, Emit_CandleFlames, '
                          'Emit_LanternGlass, Emit_DaisRunes (alef-bet ring engraved in the dais), Emit_Potion / Emit_MagicJar* (turquoise).',
                'Light_*': 'empties at the real-time light positions (extras carry light_type, color, blender_power, direction_gltf).',
                'clear_area': 'nothing but the dais (Baked_Dais, Emit_DaisRunes) inside radius 5.5 m around the origin; dais top y=-0.2; '
                              'curb stones from r=5.0 to 5.56 rise to y=+0.02; the room floor is y=0.',
                'front': 'the +Z side is open: side walls run to z=+14, front wall at z=+14 (behind the camera), ceiling at y=8.5 with '
                         'beams above the camera height only.',
            },
        },
        'environment': {'path': 'env/workshop_env.hdr', 'bytes': size(os.path.join(ENV, 'workshop_env.hdr')),
                        'format': 'Radiance HDR, equirectangular 2048x1024, linear, rendered from (0, 1.2, 0)',
                        'usage': 'THREE.RGBELoader + EquirectangularReflectionMapping (image centre = +X, matches three.js)'},
    },
    'lights': lights,
    'palette': {'moon': [0.42, 0.6, 1.0], 'fire': [1.0, 0.42, 0.12], 'lantern': [1.0, 0.6, 0.26], 'candle': [1.0, 0.58, 0.22],
                'rune_turquoise': [0.03, 1.0, 0.75], 'ambient_indigo': [0.03, 0.05, 0.12]},
}
total = sum(v for v in (size(os.path.join(MODELS, f)) for f in ('golem.glb', 'props.glb', 'workshop.glb')) if v) + (size(os.path.join(ENV, 'workshop_env.hdr')) or 0)
manifest['total_bytes'] = total
json.dump(manifest, open(os.path.join(MODELS, 'manifest.json'), 'w'), indent=1, ensure_ascii=False)
print('manifest written, total bytes', total)
