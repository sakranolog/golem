// 3D world: renderer, lighting, assets, board, golem rig and all animation.
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import {
  EffectComposer, RenderPass, EffectPass, BloomEffect, VignetteEffect, ToneMappingEffect,
  ToneMappingMode, DepthOfFieldEffect, NoiseEffect, BlendFunction, SMAAEffect,
  ShaderPass, Effect,
} from 'postprocessing';
import { audio } from './audio.js';
import { DIRS } from './interp.js';

const E = {
  lin: (t) => t,
  inOut: (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2),
  out: (t) => 1 - Math.pow(1 - t, 3),
  in: (t) => t * t * t,
  back: (t) => { const c = 1.70158; return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); },
  elastic: (t) => (t === 0 || t === 1 ? t : Math.pow(2, -10 * t) * Math.sin((t * 10 - 0.75) * (2 * Math.PI) / 3) + 1),
  bounce: (t) => { const n = 7.5625, d = 2.75; if (t < 1 / d) return n * t * t; if (t < 2 / d) return n * (t -= 1.5 / d) * t + 0.75; if (t < 2.5 / d) return n * (t -= 2.25 / d) * t + 0.9375; return n * (t -= 2.625 / d) * t + 0.984375; },
};
const lerp = (a, b, t) => a + (b - a) * t;
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
const rand = (a, b) => a + Math.random() * (b - a);
const hash = (x, z) => { const s = Math.sin(x * 127.1 + z * 311.7) * 43758.5453; return s - Math.floor(s); };
const JOINTS = ['Hips', 'Torso', 'Head', 'ArmL_Upper', 'ArmL_Lower', 'HandL', 'ArmR_Upper', 'ArmR_Lower', 'HandR', 'LegL', 'LegR'];

// Kept modest and lifted clear of the candle: a strong light right on the brass overflows the HDR buffer into black pixels.
const CANDLE_LIGHT = 10;

export class World {
  constructor(canvas) {
    this.canvas = canvas;
    this.tweens = new Set();
    this.speed = 1;
    this.time = 0;
    this.shake = 0;
    this.pointer = new THREE.Vector2();
    this.camBase = new THREE.Vector3(0, 8.4, 10.2);
    this.camTarget = new THREE.Vector3(0, 0.2, 0.6);
    this.camOrbit = 0; this.camZoom = 1; this.camLift = 0;
    this.flames = [];
    this.fx = [];
  }

  // ---------- tween engine ----------
  tween(dur, fn, ease = E.inOut) {
    return new Promise((res) => this.tweens.add({ t: 0, dur: Math.max(dur, 0.0001), fn, ease, res }));
  }
  wait(s) { return this.tween(s, () => {}); }

  // ---------- setup ----------
  async init(onProgress = () => {}) {
    const r = this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: false, powerPreference: 'high-performance', stencil: false, depth: false, alpha: false });
    r.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    r.shadowMap.enabled = true; r.shadowMap.type = THREE.PCFSoftShadowMap;
    r.toneMapping = THREE.NoToneMapping; r.outputColorSpace = THREE.SRGBColorSpace;
    const scene = this.scene = new THREE.Scene();
    scene.background = new THREE.Color(0x05070d);
    scene.fog = new THREE.FogExp2(0x0a1020, 0.006);
    const cam = this.camera = new THREE.PerspectiveCamera(32, 1, 0.5, 120);

    // lights (positions refined from the asset manifest when available)
    this.hemi = new THREE.HemisphereLight(0x7f9be0, 0x4a3524, 0.95); scene.add(this.hemi);
    const moon = this.moon = new THREE.DirectionalLight(0x9dbdff, 3.3);
    moon.position.set(-7, 11, -5); moon.castShadow = true;
    moon.shadow.mapSize.set(2048, 2048); moon.shadow.bias = -0.0004; moon.shadow.normalBias = 0.03; moon.shadow.radius = 5;
    const sc = moon.shadow.camera; sc.left = -6; sc.right = 6; sc.top = 6; sc.bottom = -6; sc.near = 1; sc.far = 40;
    scene.add(moon, moon.target);
    this.fire = new THREE.PointLight(0xff8a3c, 60, 26, 1.8); this.fire.position.set(6, 2.2, -5.5); scene.add(this.fire);
    this.warm = new THREE.PointLight(0xffc890, 46, 22, 1.8); this.warm.position.set(1.5, 4.2, 5.5); scene.add(this.warm);
    this.runeLight = new THREE.PointLight(0x3ff5e0, 0, 4.5, 2); scene.add(this.runeLight);

    this.board = new THREE.Group(); scene.add(this.board);
    this.buildDust();

    // assets
    const loader = new GLTFLoader();
    const exists = (url) => fetch(url, { method: 'HEAD' }).then((r) => r.ok && !/text\/html/.test(r.headers.get('content-type') || '')).catch(() => false);
    const load = async (url) => (await exists(url)) ? new Promise((res) => loader.load(url, (g) => res(g.scene), undefined, () => res(null))) : null;
    let done = 0; const tick = () => onProgress(++done / 4);
    const [golem, props, shop, env] = await Promise.all([
      load('/models/golem.glb').then((v) => (tick(), v)),
      load('/models/props.glb').then((v) => (tick(), v)),
      load('/models/workshop.glb').then((v) => (tick(), v)),
      exists('/env/workshop_env.hdr').then((ok) => ok ? new Promise((res) => new RGBELoader().load('/env/workshop_env.hdr', (t) => res(t), undefined, () => res(null))) : null).then((v) => (tick(), v)),
    ]);
    const pm = new THREE.PMREMGenerator(r);
    if (env) { env.mapping = THREE.EquirectangularReflectionMapping; scene.environment = pm.fromEquirectangular(env).texture; scene.environmentIntensity = 1.25; }
    else { scene.environment = pm.fromScene(new RoomEnvironment(), 0.04).texture; scene.environmentIntensity = 0.25; }

    const mf = (await exists('/models/manifest.json')) ? await fetch('/models/manifest.json').then((r) => r.json()).catch(() => null) : null;
    this.props = this.indexProps(props);
    this.setupWorkshop(shop);
    const ml = mf?.lights?.find((l) => l.name === 'Light_Moon');
    if (ml?.direction) { this.moonDir = new THREE.Vector3(...ml.direction).normalize(); this.moon.position.copy(this.moonDir).multiplyScalar(-18); this.moon.target.position.set(0, 0, 0); }
    if (shop) this.buildShafts(shop);
    this.setupGolem(golem);
    this.setupPost();
    this.resize();
    window.addEventListener('resize', () => this.resize());
    window.addEventListener('pointermove', (e) => this.pointer.set((e.clientX / innerWidth) * 2 - 1, (e.clientY / innerHeight) * 2 - 1));
    this.setupInput();
    this.clock = new THREE.Clock();
    r.setAnimationLoop(() => this.frame());
  }

  setupPost() {
    const c = this.composer = new EffectComposer(this.renderer, { frameBufferType: THREE.HalfFloatType, multisampling: 0 });
    c.addPass(new RenderPass(this.scene, this.camera));
    this.dof = new DepthOfFieldEffect(this.camera, { worldFocusDistance: 13, worldFocusRange: 7, bokehScale: 3.2, resolutionScale: 0.5 });
    this.bloom = new BloomEffect({ intensity: 1.15, luminanceThreshold: 0.82, luminanceSmoothing: 0.18, mipmapBlur: true, radius: 0.78 });
    const vig = new VignetteEffect({ offset: 0.3, darkness: 0.5 });
    const noise = new NoiseEffect({ blendFunction: BlendFunction.OVERLAY, premultiply: false }); noise.blendMode.opacity.value = 0.16;
    const tone = new ToneMappingEffect({ mode: ToneMappingMode.NEUTRAL });
    // One overflowed pixel (a hot glint on metal, say) turns into "not a number", and the blur passes
    // then smear it over the whole frame as a black flash. Scrub those before anything blurs.
    // It runs twice on purpose: every pass flips the composer's two buffers, and only one of them carries
    // the depth texture. A single extra pass would leave the depth-of-field blur writing into the buffer
    // whose depth it is reading (a GL feedback loop, which drops the draw). Two flips put it back.
    const scrub = () => new ShaderPass(new THREE.ShaderMaterial({
      uniforms: { inputBuffer: { value: null } }, depthTest: false, depthWrite: false, toneMapped: false,
      vertexShader: 'varying vec2 vUv; void main() { vUv = position.xy * 0.5 + 0.5; gl_Position = vec4(position.xy, 1.0, 1.0); }',
      fragmentShader: `uniform sampler2D inputBuffer; varying vec2 vUv;
        void main() { vec4 c = texture2D(inputBuffer, vUv);
          // Invalid pixels must be caught three ways: this GPU driver's fast-math lets them slip past
          // isnan() and past clamp(), but they do answer "yes" to a plain greater-than test.
          uvec3 e = floatBitsToUint(c.rgb) & uvec3(0x7f800000u);
          bool bits = any(equal(e, uvec3(0x7f800000u)));
          bool hot = max(c.r, max(c.g, c.b)) > 20.0;
          bool sane = all(greaterThanEqual(c.rgb, vec3(0.0))) && all(lessThanEqual(c.rgb, vec3(20.0)));
          if (bits || hot || !sane) c.rgb = vec3(9.0, 8.0, 6.0); // a blown-out highlight, not a hole
          gl_FragColor = vec4(c.rgb, 1.0); }`,
    }), 'inputBuffer');
    c.addPass(scrub()); c.addPass(scrub());
    c.addPass(new EffectPass(this.camera, this.dof));
    // The grain's overlay blend turns anything brighter than white into black, so cap the picture first.
    const cap = new Effect('Cap', 'void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) { vec3 c = inputColor.rgb; c.r = (c.r > 1.0 || !(c.r <= 1.0)) ? 1.0 : c.r; c.g = (c.g > 1.0 || !(c.g <= 1.0)) ? 1.0 : c.g; c.b = (c.b > 1.0 || !(c.b <= 1.0)) ? 1.0 : c.b; outputColor = vec4(max(c, 0.0), inputColor.a); }'); // selects, not clamp(): clamp lets invalid values through on this driver
    c.addPass(new EffectPass(this.camera, this.bloom, tone, cap, vig, noise, new SMAAEffect()));
  }

  indexProps(root) {
    const map = {};
    if (root) for (const ch of [...root.children]) { map[ch.name] = ch; ch.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; if (/flame/i.test(o.name + o.material.name)) this.flameMat(o); else this.tuneMat(o.material); } }); }
    return map;
  }
  // Flames are pure light: unlit, never shadowed, and kept inside the range the post stack can hold.
  flameMat(o) {
    this._flameMat ||= new THREE.MeshBasicMaterial({ name: 'Flame', color: new THREE.Color(2.4, 1.45, 0.5), toneMapped: false, side: THREE.DoubleSide });
    o.material = this._flameMat; o.castShadow = false; o.receiveShadow = false;
  }
  tuneMat(m) {
    if (!m || m._tuned) return; m._tuned = true;
    if (/glow|rune|eye|flame/i.test(m.name)) { m.emissiveIntensity = 3; if (m.emissive.getHex() === 0) m.emissive.set(/flame/i.test(m.name) ? 0xffa040 : 0x3ff5e0); m.toneMapped = false; }
  }

  // Clone a named prop, or build a tasteful stand-in when the asset is missing.
  prop(name) {
    const src = this.props[name];
    if (src) { const o = src.clone(true); o.position.set(0, 0, 0); return o; }
    return this.standIn(name);
  }
  standIn(name) {
    const g = new THREE.Group(); g.name = name;
    const mat = (c, o = {}) => new THREE.MeshStandardMaterial({ color: c, roughness: 0.85, ...o });
    const add = (geo, m, x = 0, y = 0, z = 0) => { const k = new THREE.Mesh(geo, m); k.position.set(x, y, z); k.castShadow = k.receiveShadow = true; g.add(k); return k; };
    if (name.startsWith('Tile')) {
      add(new THREE.BoxGeometry(0.96, 0.2, 0.96), mat(name === 'TileGoal' ? 0x54606e : 0x4a4f5c), 0, -0.1, 0);
      if (name === 'TileGoal') { const ring = add(new THREE.TorusGeometry(0.3, 0.035, 8, 40), mat(0x0, { emissive: 0x3ff5e0, emissiveIntensity: 3 }), 0, 0.005, 0); ring.rotation.x = Math.PI / 2; ring.material.name = 'Glow'; ring.castShadow = false; }
    } else if (name.startsWith('Block')) add(new THREE.BoxGeometry(0.86, 0.9, 0.86), mat(name === 'Block_Books' ? 0x7a3b2a : name === 'Block_Crate' ? 0x6b4a2c : 0x5c6068), 0, 0.45, 0);
    else if (name === 'Candle') { add(new THREE.CylinderGeometry(0.07, 0.08, 0.4, 16), mat(0xf2e6c8), 0, 0.2, 0); const f = add(new THREE.SphereGeometry(0.06, 12, 12), mat(0x0), 0, 0.47, 0); f.name = 'Flame'; f.scale.y = 1.7; this.flameMat(f); }
    else if (name === 'Pedestal') add(new THREE.CylinderGeometry(0.28, 0.34, 0.35, 20), mat(0x5c6068), 0, 0.175, 0);
    else if (name === 'Jug') add(new THREE.LatheGeometry([[0, 0], [0.13, 0], [0.19, 0.18], [0.14, 0.34], [0.08, 0.4], [0.1, 0.45]].map((p) => new THREE.Vector2(...p)), 20), mat(0xb5653a));
    else if (name.startsWith('JugShard')) add(new THREE.TetrahedronGeometry(0.09), mat(0xb5653a));
    else if (name.startsWith('Plant')) { add(new THREE.CylinderGeometry(0.17, 0.12, 0.26, 16), mat(0x9a5533), 0, 0.13, 0); const bloom = name === 'Plant_Bloom'; for (let i = 0; i < 6; i++) { const l = add(new THREE.SphereGeometry(0.1, 8, 8), mat(bloom ? 0x3fa35a : 0x6b6a3a), Math.cos(i) * 0.1, bloom ? 0.42 + (i % 3) * 0.08 : 0.3, Math.sin(i) * 0.1); l.scale.set(1, bloom ? 1.4 : 0.5, 0.5); } if (bloom) add(new THREE.SphereGeometry(0.06, 8, 8), mat(0xff7aa8, { emissive: 0xff3a78, emissiveIntensity: 0.6 }), 0, 0.66, 0); }
    else if (name.startsWith('Letter')) add(new THREE.BoxGeometry(0.34, 0.42, 0.08), mat(0xe2b84a, { metalness: 1, roughness: 0.25 }));
    else if (name.startsWith('Cat')) { add(new THREE.SphereGeometry(0.2, 16, 12), mat(0x2b2b33), 0, name === 'Cat' ? 0.13 : 0.2, 0).scale.set(1.2, name === 'Cat' ? 0.65 : 1.1, 0.9); add(new THREE.SphereGeometry(0.11, 12, 10), mat(0x2b2b33), 0.02, name === 'Cat' ? 0.16 : 0.45, 0.17); }
    else if (name === 'Star') add(new THREE.OctahedronGeometry(0.15), mat(0xffd35a, { emissive: 0xffb020, emissiveIntensity: 2 }));
    else add(new THREE.BoxGeometry(0.3, 0.3, 0.3), mat(0x888888), 0, 0.15, 0);
    return g;
  }

  setupWorkshop(root) {
    if (!root) {
      // minimal moody stand-in room
      const floor = new THREE.Mesh(new THREE.CircleGeometry(30, 64), new THREE.MeshStandardMaterial({ color: 0x1a1d26, roughness: 0.95 }));
      floor.rotation.x = -Math.PI / 2; floor.position.y = -0.2; floor.receiveShadow = true; this.scene.add(floor);
      return;
    }
    this.scene.add(root);
    const flameMeshes = [];
    root.traverse((o) => {
      if (o.name.startsWith('Light_')) this.placeLight(o);
      if (!o.isMesh) return;
      const m = o.material; const emit = /^Emit_/.test(o.name) || /^Emit_/.test(o.parent?.name || '');
      if (emit) {
        const col = (m.emissive && m.emissive.getHex() ? m.emissive : m.color).clone();
        o.material = new THREE.MeshBasicMaterial({ color: col.multiplyScalar(/window|glass/i.test(o.name) ? 1.6 : 2.6), map: m.emissiveMap || m.map || null, toneMapped: false });
        if (/flame|fire/i.test(o.name)) flameMeshes.push(o);
      } else if (/^Baked_/.test(m.name) || m.isMeshBasicMaterial) {
        const tex = m.map || m.emissiveMap;
        if (tex) { tex.anisotropy = 8; o.material = new THREE.MeshBasicMaterial({ map: tex, name: m.name, fog: false, color: new THREE.Color(1.5, 1.46, 1.42) }); }
        // the dais under the board also catches real-time shadows
        if (/dais|rug|floor/i.test(o.name)) this.shadowCatcher(o);
      } else { o.receiveShadow = true; o.castShadow = false; }
    });
    for (const m of flameMeshes) this.splitFlames(m);
  }
  // All the room's flames arrive merged into one mesh. Give every flame its own pivot at its base,
  // so the flicker stretches it in place instead of sliding it around the room.
  splitFlames(mesh) {
    const g = mesh.geometry, pos = g.attributes.position, idx = g.index, n = pos.count;
    const parent = new Int32Array(n); for (let i = 0; i < n; i++) parent[i] = i;
    const find = (a) => { while (parent[a] !== a) a = parent[a] = parent[parent[a]]; return a; };
    const seen = new Map();
    for (let i = 0; i < n; i++) {
      const k = `${Math.round(pos.getX(i) * 2000)},${Math.round(pos.getY(i) * 2000)},${Math.round(pos.getZ(i) * 2000)}`;
      if (seen.has(k)) parent[find(i)] = find(seen.get(k)); else seen.set(k, i);
    }
    const count = idx ? idx.count : n, at = (i) => (idx ? idx.getX(i) : i);
    for (let i = 0; i < count; i += 3) { parent[find(at(i))] = find(at(i + 1)); parent[find(at(i + 1))] = find(at(i + 2)); }
    const islands = new Map();
    for (let i = 0; i < count; i++) { const r = find(at(i)); if (!islands.has(r)) islands.set(r, []); islands.get(r).push(at(i)); }
    for (const verts of islands.values()) {
      const arr = new Float32Array(verts.length * 3);
      verts.forEach((v, i) => { arr[i * 3] = pos.getX(v); arr[i * 3 + 1] = pos.getY(v); arr[i * 3 + 2] = pos.getZ(v); });
      const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(arr, 3)); geo.computeBoundingBox();
      const b = geo.boundingBox, pivot = new THREE.Vector3((b.min.x + b.max.x) / 2, b.min.y, (b.min.z + b.max.z) / 2);
      geo.translate(-pivot.x, -pivot.y, -pivot.z);
      const f = new THREE.Mesh(geo, mesh.material); f.name = mesh.name; f.position.copy(pivot); mesh.add(f);
      // shells of the same flame share a seed, so they flicker together
      this.flames.push({ mesh: f, base: f.scale.clone(), seed: (Math.round(pivot.x * 20) * 1.7 + Math.round(pivot.z * 20) * 2.3) % 10 });
    }
    mesh.geometry = new THREE.BufferGeometry(); // the parent stays only as the flames' anchor
  }
  shadowCatcher(src) {
    const m = new THREE.Mesh(src.geometry, new THREE.ShadowMaterial({ opacity: 0.5, color: 0x02040a }));
    src.getWorldPosition(m.position); src.getWorldQuaternion(m.quaternion); src.getWorldScale(m.scale);
    m.position.y += 0.004; m.receiveShadow = true; m.renderOrder = 1; this.scene.add(m);
  }
  placeLight(o) {
    const p = o.getWorldPosition(new THREE.Vector3());
    if (/Moon/i.test(o.name)) {
      const dir = new THREE.Vector3(0, 0, -1).applyQuaternion(o.getWorldQuaternion(new THREE.Quaternion()));
      if (dir.y > -0.15) dir.set(0.45, -0.8, 0.35); // safety: moonlight must come from above
      this.moon.position.copy(dir.normalize().multiplyScalar(-16)); this.moon.target.position.set(0, 0, 0);
    } else if (/Fire/i.test(o.name)) this.fire.position.copy(p);
  }

  // Moonlight shafts: thin additive sheets extruded from the window along the light direction.
  buildShafts(shop) {
    const win = shop.getObjectByName('Emit_Window'); if (!win || !this.moonDir) return;
    const box = new THREE.Box3().setFromObject(win); const c = box.getCenter(new THREE.Vector3()), size = box.getSize(new THREE.Vector3());
    const wide = size.x >= size.z ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 0, 1); const w = Math.max(size.x, size.z);
    const len = (c.y + 0.2) / -this.moonDir.y; const dir = this.moonDir.clone().multiplyScalar(len);
    this.shaftMat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, uniforms: { uTime: { value: 0 } },
      vertexShader: `attribute float seed; varying vec2 vUv; varying float vSeed; void main(){ vUv = uv; vSeed = seed; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `varying vec2 vUv; varying float vSeed; uniform float uTime;
        void main(){ float edge = smoothstep(0.0, 0.5, vUv.x) * (1.0 - smoothstep(0.5, 1.0, vUv.x)); float along = smoothstep(0.0, 0.08, vUv.y) * pow(clamp(1.0 - vUv.y, 0.0, 1.0), 1.6); // never pow() a negative: that is an invalid pixel
          float flick = 0.7 + 0.3 * sin(uTime * (0.25 + vSeed * 0.4) + vSeed * 40.0);
          gl_FragColor = vec4(vec3(0.42, 0.6, 1.0) * clamp(edge * along * flick, 0.0, 1.0) * 0.3, 1.0); }`,
    });
    const pos = [], uv = [], seed = [], idx = []; const n = 9;
    for (let i = 0; i < n; i++) {
      const sd = Math.random(); const off = (i / (n - 1) - 0.5) * w * 0.9; const hw = w * rand(0.035, 0.07);
      for (const yy of [-0.3, 0.3]) { // two sheets per strip at different window heights give the beam some volume
        const a = c.clone().addScaledVector(wide, off - hw).setY(c.y + size.y * yy), b = c.clone().addScaledVector(wide, off + hw).setY(c.y + size.y * yy);
        const k = pos.length / 3; for (const [v, u, t] of [[a, 0, 0], [b, 1, 0], [b.clone().add(dir), 1, 1], [a.clone().add(dir), 0, 1]]) { pos.push(v.x, v.y, v.z); uv.push(u, t); seed.push(sd); }
        idx.push(k, k + 1, k + 2, k, k + 2, k + 3);
      }
    }
    const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); geo.setAttribute('seed', new THREE.Float32BufferAttribute(seed, 1)); geo.setIndex(idx);
    const m = new THREE.Mesh(geo, this.shaftMat); m.frustumCulled = false; m.renderOrder = 5; this.scene.add(m);
  }

  // ---------- golem ----------
  setupGolem(root) {
    const actor = this.actor = new THREE.Group(); this.scene.add(actor);
    if (!root) root = this.standInGolem();
    const g = root.getObjectByName('Golem') || root;
    actor.add(root);
    const j = this.j = {};
    for (const n of JOINTS) j[n] = g.getObjectByName(n) || new THREE.Object3D();
    this.rest = {}; this.pose = {};
    for (const n of JOINTS) { this.rest[n] = j[n].rotation.clone(); this.pose[n] = new THREE.Vector3(); }
    this.eyes = [g.getObjectByName('Eye_L'), g.getObjectByName('Eye_R')].filter(Boolean);
    this.eyeRest = this.eyes.map((e) => e.scale.clone());
    this.runeMats = []; this.eyeMats = [];
    root.traverse((o) => {
      if (!o.isMesh) return; o.castShadow = true; o.receiveShadow = true;
      for (const m of [].concat(o.material)) {
        if (/rune|glow/i.test(m.name) && !this.runeMats.includes(m)) { this.runeMats.push(m); m.toneMapped = false; if (m.emissive.getHex() === 0) m.emissive.set(0x3ff5e0); }
        if (/eye/i.test(m.name) && !this.eyeMats.includes(m)) { this.eyeMats.push(m); m.toneMapped = false; if (m.emissive.getHex() === 0) m.emissive.set(0x7ffcf0); }
      }
    });
    actor.userData.touch = { kind: 'golem', o: actor, drag: true };
    this.hold = new THREE.Group(); this.hold.position.set(0, 0.62, 0.5); actor.add(this.hold);
    this.g = { rune: 0.12, eye: 0.0, squash: 1, lean: 0, bob: 0, awake: false, blink: 0, nextBlink: 2, lookX: 0, lookY: 0, angle: 0, hopY: 0, tilt: 0, roll: 0 };
    this.bodyRoot = root; this.restY = root.position.y;
  }
  standInGolem() {
    const clay = new THREE.MeshStandardMaterial({ color: 0x8a6a52, roughness: 0.92, name: 'Clay' });
    const rune = new THREE.MeshStandardMaterial({ color: 0x0, emissive: 0x3ff5e0, emissiveIntensity: 2, name: 'Rune' });
    const eye = new THREE.MeshStandardMaterial({ color: 0x0, emissive: 0x9ffff4, emissiveIntensity: 3, name: 'Eye' });
    const N = (name, parent, x, y, z) => { const o = new THREE.Group(); o.name = name; o.position.set(x, y, z); parent.add(o); return o; };
    const M = (parent, geo, m, x, y, z, sx = 1, sy = 1, sz = 1) => { const k = new THREE.Mesh(geo, m); k.position.set(x, y, z); k.scale.set(sx, sy, sz); parent.add(k); return k; };
    const S = (r) => new THREE.SphereGeometry(r, 28, 20);
    const root = new THREE.Group(); root.name = 'Golem';
    const hips = N('Hips', root, 0, 0.36, 0); M(hips, S(0.26), clay, 0, 0, 0, 1.15, 0.7, 0.95);
    const torso = N('Torso', hips, 0, 0.1, 0); M(torso, S(0.4), clay, 0, 0.36, 0, 1.05, 1.0, 0.85);
    M(torso, new THREE.TorusGeometry(0.1, 0.018, 8, 30), rune, 0, 0.4, 0.335);
    const head = N('Head', torso, 0, 0.74, 0.04); M(head, S(0.17), clay, 0, 0.1, 0, 1.1, 0.9, 1);
    for (const s of [-1, 1]) { const e = M(head, S(0.038), eye, s * 0.07, 0.11, 0.155); e.name = s < 0 ? 'Eye_R' : 'Eye_L'; }
    M(head, new THREE.BoxGeometry(0.12, 0.022, 0.01), rune, 0, 0.19, 0.15);
    for (const s of [-1, 1]) {
      const side = s > 0 ? 'L' : 'R';
      const up = N(`Arm${side}_Upper`, torso, s * 0.43, 0.56, 0); M(up, S(0.13), clay, s * 0.03, -0.14, 0, 1, 1.5, 1);
      const lo = N(`Arm${side}_Lower`, up, s * 0.05, -0.32, 0); M(lo, S(0.15), clay, 0, -0.16, 0, 1.05, 1.5, 1.05); M(lo, new THREE.TorusGeometry(0.15, 0.014, 8, 30), rune, 0, -0.1, 0).rotation.x = Math.PI / 2;
      const h = N(`Hand${side}`, lo, 0, -0.38, 0); M(h, S(0.14), clay, 0, -0.05, 0.01, 1.1, 0.9, 1.1);
      const leg = N(`Leg${side}`, hips, s * 0.17, -0.06, 0); M(leg, S(0.14), clay, 0, -0.14, 0, 1, 1.25, 1); M(leg, S(0.14), clay, 0, -0.26, 0.04, 1.1, 0.45, 1.4);
    }
    return root;
  }

  cellPos(x, z) { return new THREE.Vector3(x - (this.w - 1) / 2, 0, z - (this.h - 1) / 2); }
  dirAngle(d) { return Math.PI - d * Math.PI / 2; }
  setPose(target, k = 1) { for (const n in target) { const p = this.pose[n]; const t = target[n]; p.set(lerp(p.x, t[0], k), lerp(p.y, t[1], k), lerp(p.z, t[2], k)); } }
  poseTo(target, dur, ease = E.inOut) {
    const from = {}; for (const n in target) from[n] = this.pose[n].clone();
    return this.tween(dur, (t) => { for (const n in target) { const f = from[n], g = target[n]; this.pose[n].set(lerp(f.x, g[0], t), lerp(f.y, g[1], t), lerp(f.z, g[2], t)); } }, ease);
  }
  neutral(dur = 0.3) { const t = {}; for (const n of JOINTS) t[n] = [0, 0, 0]; if (this.carrying) Object.assign(t, CARRY); return this.poseTo(t, dur); }
  gv(key, to, dur, ease) { const from = this.g[key]; return this.tween(dur, (t) => { this.g[key] = lerp(from, to, t); }, ease); }

  // ---------- level ----------
  async loadLevel(level, { instant = false } = {}) {
    this.level = level; this.w = Math.max(...level.map.map((r) => r.length)); this.h = level.map.length;
    this.board.clear(); this.items = []; this.blocks = {}; this.goalGlow = []; this.candle = null; this.plant = null;
    this.clearFx();
    const tiles = [];
    for (let z = 0; z < this.h; z++) for (let x = 0; x < this.w; x++) {
      const c = level.map[z][x] ?? ' '; if (c === ' ') continue;
      const p = this.cellPos(x, z); const hsh = hash(x + level.day * 7, z);
      const tile = this.prop(c === 'G' ? 'TileGoal' : ['Tile_A', 'Tile_B', 'Tile_C'][Math.floor(hsh * 3)]);
      tile.position.copy(p); if (c !== 'G') tile.rotation.y = Math.floor(hsh * 4) * Math.PI / 2;
      this.board.add(tile); tiles.push({ o: tile, d: p.length() }); tile.userData.touch = { kind: 'tile', o: tile, x, z };
      if (c === 'G') tile.traverse((o) => { if (o.isMesh && /glow/i.test(o.material.name)) { o.material = o.material.clone(); o.material.toneMapped = false; this.goalGlow.push(o.material); } });
      if (c === '#') {
        const dec = level.decor.find((d) => d.x === x && d.z === z);
        let b;
        if (dec?.type === 'candle') { b = new THREE.Group(); const ped = this.prop('Pedestal'); const can = this.prop('Candle'); can.position.y = 0.35; b.add(ped, can); this.candle = { o: can, flame: can.getObjectByName('Flame'), light: new THREE.PointLight(0xffb060, 0, 7, 2) }; this.candle.light.position.set(0, 1.4, 0.15); b.add(this.candle.light); if (this.candle.flame) this.candle.flame.visible = false; }
        else if (dec?.type === 'plant') { b = new THREE.Group(); const a = this.prop('Plant_Wilted'), bl = this.prop('Plant_Bloom'); bl.visible = false; const ped = this.prop('Pedestal'); a.position.y = bl.position.y = 0.35; b.add(ped, a, bl); this.plant = { wilted: a, bloom: bl }; }
        else if (level.lowWalls) { b = this.prop('Block_Stone'); b.scale.set(1.06, 0.42, 1.06); b.userData.sy = 0.42; b.rotation.y = Math.floor(hsh * 4) * Math.PI / 2; }
        else { b = this.prop(['Block_Books', 'Block_Stone', 'Block_Crate'][Math.floor(hash(x * 3 + 1, z * 5 + level.day) * 3)]); b.rotation.y = Math.floor(hsh * 4) * Math.PI / 2 + (hsh - 0.5) * 0.12; }
        b.position.copy(p); this.board.add(b); b.userData.touch = { kind: 'block', o: b }; this.blocks[`${x},${z}`] = b; tiles.push({ o: b, d: p.length() + 0.4, block: true });
      }
    }
    level.items.forEach((it, i) => {
      const name = it.type === 'jug' ? 'Jug' : it.type === 'cat' ? 'Cat' : it.type === 'letter' ? { 'א': 'Letter_Alef', 'מ': 'Letter_Mem', 'ת': 'Letter_Tav' }[it.letter] : 'Star';
      const o = this.prop(name); const holder = new THREE.Group(); holder.add(o); holder.position.copy(this.cellPos(it.x, it.z));
      if (it.type === 'letter') { o.position.y = 0.55; const l = new THREE.PointLight(0xffc860, 5, 3.4, 2); l.position.set(0, 1.5, 0.5); holder.add(l); /* well clear of the letter: a light inside polished gold produces invalid pixels */ }
      if (it.type === 'cat') o.rotation.y = -0.6;
      this.board.add(holder); this.items[i] = { ...it, holder, o, home: holder.position.clone() }; holder.userData.touch = { kind: 'item', o: holder, it: this.items[i], drag: true };
      tiles.push({ o: holder, d: holder.position.length() + 0.6, block: true });
    });
    // fit camera + shadows to the board
    const s = Math.max(this.w, this.h + 0.5);
    this.camBase.set(0, 2.3 + s * 0.8, 3.6 + s * 1.2); this.camTarget.set(0, 0.3, s * 0.16);
    const sc = this.moon.shadow.camera; const half = s * 0.75 + 1.5; sc.left = -half; sc.right = half; sc.top = half; sc.bottom = -half; sc.updateProjectionMatrix();
    this.placeGolem(true);
    // entrance: tiles rise out of the dais in a ripple
    if (!instant) {
      this.actor.visible = false;
      await Promise.all(tiles.map(({ o, d, block }) => {
        const y = o.position.y; o.position.y = y - 1.4; o.visible = false;
        return this.wait(d * 0.09 + (block ? 0.25 : 0)).then(() => { o.visible = true; if (!block && Math.random() < 0.5) audio.play('stone_place', { volume: 0.25, rate: rand(0.6, 0.9) }); return this.tween(0.55, (t) => { o.position.y = y - 1.4 * (1 - t); }, E.back); });
      }));
      this.actor.visible = true; this.actor.scale.setScalar(0.001);
      audio.play('putdown', { volume: 0.7 });
      await this.tween(0.6, (t) => this.actor.scale.setScalar(Math.max(t, 0.001)), E.elastic);
    }
  }

  placeGolem(hard) {
    const L = this.level; this.gx = L.start.x; this.gz = L.start.z; this.gdir = L.start.dir;
    this.actor.position.copy(this.cellPos(this.gx, this.gz)); this.g.angle = this.dirAngle(this.gdir);
    this.actor.rotation.set(0, this.g.angle, 0); this.actor.scale.setScalar(1); this.actor.visible = true;
    Object.assign(this.g, { squash: 1, lean: 0, hopY: 0, tilt: 0, roll: 0, awake: false });
    if (hard) { this.g.rune = 0.12; this.g.eye = 0; }
    for (const n of JOINTS) this.pose[n].set(0, 0, 0);
    this.setPose(SLEEP); this.carrying = null; this.hold.clear();
  }

  // Put everything back after a failed run (with a little magic poof).
  async resetRun() {
    this.puff(this.actor.position.clone().setY(0.5), 0x3ff5e0, 26, 1.6);
    audio.play('whoosh_ui', { volume: 0.6 });
    await this.tween(0.25, (t) => this.actor.scale.setScalar(1 - t * 0.999), E.in);
    this.clearFx();
    for (const it of this.items) { it.holder.visible = true; it.holder.position.copy(it.home); it.holder.rotation.set(0, 0, 0); it.holder.scale.setScalar(1); if (it.holder.parent !== this.board) this.board.add(it.holder); it.o.visible = true; if (it.alt) { it.alt.removeFromParent(); it.alt = null; } it.o.position.y = it.type === 'letter' ? 0.55 : 0; it.o.rotation.set(0, it.type === 'cat' ? -0.6 : 0, 0); }
    for (const k in this.blocks) this.blocks[k].rotation.z = 0;
    this.placeGolem(true);
    this.puff(this.actor.position.clone().setY(0.5), 0x3ff5e0, 26, 1.6);
    await this.tween(0.45, (t) => this.actor.scale.setScalar(Math.max(t, 0.001)), E.back);
  }

  async awaken() {
    this.g.awake = true; audio.play('awaken');
    this.gv('rune', 1, 0.9, E.out); this.gv('eye', 1, 0.7, E.out);
    this.ring(this.actor.position, 0x3ff5e0);
    await this.poseTo(Object.fromEntries(JOINTS.map((n) => [n, [0, 0, 0]])), 0.7, E.back);
    audio.play('golem_grunt', { volume: 0.8 });
    await this.wait(0.15);
  }
  async sleep() { this.g.awake = false; audio.play('sleep', { volume: 0.6 }); this.gv('rune', 0.12, 0.8); this.gv('eye', 0, 0.8); await this.poseTo(SLEEP, 0.8); }

  // ---------- event playback ----------
  async play(events, onEvent = () => {}) {
    for (const ev of events) {
      onEvent(ev);
      const fn = this['ev_' + ev.type];
      if (fn) await fn.call(this, ev);
    }
  }

  async ev_loop() { this.g.rune = 1.6; this.gv('rune', 1, 0.3); await this.wait(0.08); }

  async ev_step(ev) {
    const from = this.actor.position.clone(), to = this.cellPos(ev.x, ev.z);
    const side = (this.stepSide = !this.stepSide) ? 1 : -1; const D = 0.46;
    const carry = !!this.carrying;
    this.tween(D, (t) => {
      const sw = Math.sin(t * Math.PI);
      this.pose.LegL.x = -side * sw * 0.75; this.pose.LegR.x = side * sw * 0.75;
      if (!carry) { this.pose.ArmL_Upper.x = side * sw * 0.55; this.pose.ArmR_Upper.x = -side * sw * 0.55; }
      this.pose.Torso.z = side * sw * 0.07; this.pose.Head.z = -side * sw * 0.06; this.g.lean = sw * 0.12;
    }, E.lin);
    await this.tween(D, (t) => { this.actor.position.lerpVectors(from, to, E.inOut(t)); this.g.hopY = Math.sin(t * Math.PI) * 0.13; }, E.lin);
    this.gx = ev.x; this.gz = ev.z; this.land(0.5);
    await this.wait(0.07);
  }
  land(power = 0.5) {
    audio.play('step', { volume: 0.55 + power * 0.4 });
    this.shake = Math.max(this.shake, power * 0.11);
    this.g.squash = 1 - 0.14 * power * 2; this.tween(0.38, (t) => { this.g.squash = lerp(1 - 0.14 * power * 2, 1, t); }, E.elastic);
    this.puff(this.actor.position.clone().setY(0.03), 0xb9a58c, 7, 0.7, true);
  }

  async ev_turn(ev) {
    const from = this.g.angle, to = from + (ev.right ? -1 : 1) * Math.PI / 2;
    audio.play('turn', { volume: 0.6, rate: rand(0.92, 1.08) });
    this.tween(0.42, (t) => { this.pose.Head.y = Math.sin(t * Math.PI) * (ev.right ? -0.5 : 0.5); this.pose.Torso.y = Math.sin(t * Math.PI) * (ev.right ? -0.18 : 0.18); }, E.lin);
    await this.tween(0.42, (t) => { this.g.angle = lerp(from, to, t); this.g.hopY = Math.sin(t * Math.PI) * 0.04; }, E.back);
    this.gdir = ev.dir; this.shake = Math.max(this.shake, 0.025);
    await this.wait(0.06);
  }

  async ev_sense(ev) {
    audio.play('ui_tap', { volume: 0.5, rate: ev.blocked ? 0.7 : 1.3 });
    this.g.eye = 2.2; this.gv('eye', 1, 0.35);
    const d = DIRS[this.gdir]; const p = this.actor.position.clone().add(new THREE.Vector3(d[0] * 0.55, 0.6, d[1] * 0.55));
    this.puff(p, ev.blocked ? 0xff6a4a : 0x3ff5e0, 6, 0.5);
    await this.poseTo({ Torso: [0.22, 0, 0], Head: [0.25, 0, 0] }, 0.14, E.out);
    await this.poseTo({ Torso: [0, 0, 0], Head: [0, 0, 0] }, 0.14);
  }

  async ev_bonk(ev) {
    const from = this.actor.position.clone(), to = from.clone().lerp(this.cellPos(ev.x, ev.z), 0.36);
    const block = this.blocks[`${ev.x},${ev.z}`];
    this.poseTo({ LegL: [-0.7, 0, 0], ArmL_Upper: [0.5, 0, 0], ArmR_Upper: [-0.5, 0, 0] }, 0.2);
    await this.tween(0.22, (t) => { this.actor.position.lerpVectors(from, to, t); this.g.lean = t * 0.3; }, E.in);
    audio.play(block?.name === 'Block_Books' ? 'bonk_books' : 'bonk'); audio.play('golem_oops', { delay: 0.25 });
    this.shake = 0.3; this.g.squash = 0.72; this.stars(this.actor.position.clone().setY(1.45));
    this.puff(to.clone().setY(0.7), 0xd8c8b0, 16, 1.4);
    if (block) this.tween(0.9, (t) => { block.rotation.z = Math.sin(t * 16) * 0.07 * (1 - t); }, E.lin);
    this.tween(0.5, (t) => { this.g.squash = lerp(0.72, 1, t); }, E.elastic);
    await this.tween(0.45, (t) => { this.actor.position.lerpVectors(to, from, t); this.g.lean = lerp(0.3, -0.35, t); this.g.hopY = Math.sin(t * Math.PI) * 0.18; }, E.out);
    this.land(0.8);
    // sits down dazed
    this.poseTo({ LegL: [-1.3, 0, 0.2], LegR: [-1.3, 0, -0.2], ArmL_Upper: [0.2, 0, 0.5], ArmR_Upper: [0.2, 0, -0.5], Head: [0.15, 0, 0.25], Torso: [-0.12, 0, 0] }, 0.35, E.bounce);
    await this.tween(0.35, (t) => { this.g.lean = lerp(-0.35, -0.1, t); this.g.hopY = -0.2 * t; }, E.bounce);
    this.dizzy(1.2); await this.wait(1.0);
  }
  dizzy(dur) { this.tween(dur, (t) => { this.pose.Head.z = Math.sin(t * 14) * 0.22 * (1 - t * 0.5); this.g.eye = 0.5 + 0.5 * Math.sin(t * 40); }, E.lin); }

  async ev_trip(ev) {
    const from = this.actor.position.clone(), edge = from.clone().lerp(this.cellPos(ev.x, ev.z), 0.42);
    await this.tween(0.3, (t) => { this.actor.position.lerpVectors(from, edge, t); this.pose.LegL.x = -Math.sin(t * Math.PI) * 0.7; }, E.out);
    // teeter, windmill arms, look at the player
    audio.play('golem_huh', { volume: 0.9 });
    this.poseTo({ Head: [-0.25, 0, 0] }, 0.2);
    await this.tween(0.85, (t) => { const w = t * 15; this.pose.ArmL_Upper.set(Math.sin(w) * 1.6 - 0.6, 0, 0.7); this.pose.ArmR_Upper.set(Math.sin(w + 2) * 1.6 - 0.6, 0, -0.7); this.g.lean = 0.12 + Math.sin(t * 9) * 0.1 + t * 0.2; }, E.lin);
    audio.play('fall', { volume: 0.7 });
    const land = edge.clone().lerp(this.cellPos(ev.x, ev.z), 0.75);
    await this.tween(0.42, (t) => { this.actor.position.lerpVectors(edge, land, t); this.g.lean = lerp(0.42, Math.PI / 2, t); this.g.hopY = -0.2 * t + 0.3 * t; }, E.in);
    audio.play('bonk', { volume: 0.9, rate: 0.8 }); audio.play('golem_oops', { delay: 0.35 });
    this.shake = 0.38; this.puff(land.clone().setY(0), 0xb9a58c, 22, 1.8, true);
    this.poseTo({ ArmL_Upper: [-2.6, 0, 0.5], ArmR_Upper: [-2.6, 0, -0.5], LegL: [0.2, 0, 0.3], LegR: [0.2, 0, -0.3] }, 0.2);
    await this.tween(0.5, (t) => { this.g.hopY = 0.1 + Math.abs(Math.sin(t * 7)) * 0.08 * (1 - t); }, E.lin);
    await this.wait(0.6);
  }

  async ev_grabair() {
    audio.play('pickup', { volume: 0.4 });
    await this.poseTo(REACH, 0.3, E.out);
    await this.poseTo({ ...CARRY, Head: [0.45, 0, 0] }, 0.25);
    audio.play('golem_huh', { volume: 0.7 }); await this.wait(0.45);
    await this.neutral(0.3);
  }
  async ev_shrug() {
    audio.play('golem_huh', { volume: 0.7 });
    await this.poseTo({ ArmL_Upper: [0, 0, 0.7], ArmR_Upper: [0, 0, -0.7], Head: [0, 0, 0.3] }, 0.25, E.back);
    await this.wait(0.3); await this.neutral(0.25);
  }

  async ev_pickup(ev) {
    const it = this.items[ev.item];
    await this.poseTo(REACH, 0.32, E.out);
    audio.play('pickup');
    // hand the item over to the golem's hold point without a visual jump
    this.hold.attach(it.holder);
    const from = it.holder.position.clone(), fromQ = it.holder.quaternion.clone(), idQ = new THREE.Quaternion();
    this.carrying = it;
    if (ev.kind === 'cat') {
      const awake = this.prop('Cat_Awake'); awake.rotation.y = Math.PI; it.o.visible = false; it.holder.add(awake); it.alt = awake;
      audio.play('cat_meow', { delay: 0.15 });
    }
    this.tween(0.4, (t) => { it.holder.position.lerpVectors(from, new THREE.Vector3(0, 0, 0), t); it.holder.quaternion.slerpQuaternions(fromQ, idQ, t); });
    await this.poseTo(CARRY, 0.4, E.back);
    if (ev.kind === 'cat') {
      await this.poseTo({ Head: [0.5, 0, 0.2] }, 0.25); audio.play('golem_huh');
      await this.tween(1.0, (t) => { it.holder.rotation.z = Math.sin(t * 22) * 0.12; this.pose.Head.z = 0.2 * Math.cos(t * 6); }, E.lin);
    } else { audio.play('golem_grunt', { volume: 0.6 }); await this.wait(0.1); }
  }

  async ev_put(ev) {
    const it = this.carrying; const target = this.cellPos(ev.x, ev.z);
    await this.poseTo(REACH, 0.32);
    this.board.attach(it.holder); const from = it.holder.position.clone(), fq = it.holder.quaternion.clone(), iq = new THREE.Quaternion();
    await this.tween(0.25, (t) => { it.holder.position.lerpVectors(from, target, t); it.holder.quaternion.slerpQuaternions(fq, iq, t); }, E.in);
    audio.play('putdown'); this.puff(target.clone().setY(0.03), 0xb9a58c, 6, 0.6, true);
    this.carrying = null; await this.neutral(0.3);
  }

  async smashAt(it, pos, toss) {
    this.board.attach(it.holder); const from = it.holder.position.clone();
    await this.tween(toss ? 0.5 : 0.3, (t) => { it.holder.position.lerpVectors(from, pos, t); it.holder.position.y += Math.sin(t * Math.PI) * (toss ? 0.9 : 0.1) + (1 - t) * 0; it.holder.rotation.x = t * (toss ? 5 : 1.2); }, toss ? E.lin : E.in);
    it.holder.visible = false; audio.play('jug_smash'); this.shake = 0.16;
    this.shards(pos); this.puff(pos.clone().setY(0.1), 0xc98a5a, 18, 1.5);
  }
  async ev_dropsmash(ev) {
    const it = this.carrying; const c = this.cellPos(ev.x, ev.z);
    const solid = !!this.blocks[`${ev.x},${ev.z}`];
    await this.poseTo(REACH, 0.3);
    this.carrying = null; this.neutral(0.3);
    await this.smashAt(it, solid ? this.actor.position.clone().lerp(c, 0.5).setY(0) : c.setY(-0.18), false);
    audio.play('golem_oops', { delay: 0.2 });
    await this.poseTo({ Head: [0.5, 0, 0], ArmL_Upper: [0, 0, 0.4], ArmR_Upper: [0, 0, -0.4] }, 0.3); await this.wait(0.9);
  }
  async ev_kick(ev) {
    const it = this.items[ev.item]; const from = this.actor.position.clone(), mid = from.clone().lerp(this.cellPos(ev.x, ev.z), 0.4);
    await this.tween(0.25, (t) => { this.actor.position.lerpVectors(from, mid, t); this.pose.LegR.x = -t * 1.1; }, E.in);
    audio.play('bonk', { volume: 0.5, rate: 1.5 });
    const d = DIRS[this.gdir]; const far = this.cellPos(ev.x, ev.z).add(new THREE.Vector3(d[0] * 1.6, -0.1, d[1] * 1.6));
    this.tween(0.5, (t) => { this.actor.position.lerpVectors(mid, from, t); this.pose.LegR.x = -1.1 * (1 - t); }, E.out);
    await this.smashAt(it, far, true);
    audio.play('golem_oops'); await this.poseTo({ Head: [0.4, 0, 0] }, 0.3); await this.wait(0.8);
  }
  async ev_bumpcat(ev) {
    const it = this.items[ev.item]; const from = this.actor.position.clone(), mid = from.clone().lerp(this.cellPos(ev.x, ev.z), 0.3);
    await this.tween(0.22, (t) => this.actor.position.lerpVectors(from, mid, t), E.in);
    const awake = this.prop('Cat_Awake'); it.o.visible = false; it.holder.add(awake); it.alt = awake; awake.lookAt(this.actor.position.clone().setY(0).sub(it.holder.position));
    audio.play('cat_meow'); this.stars(it.holder.position.clone().setY(0.8));
    this.tween(0.5, (t) => { it.holder.position.y = Math.sin(t * Math.PI) * 0.5; }, E.lin);
    await this.tween(0.35, (t) => { this.actor.position.lerpVectors(mid, from, t); this.g.lean = -0.3 * Math.sin(t * Math.PI); this.g.hopY = Math.sin(t * Math.PI) * 0.2; }, E.out);
    this.land(0.6); audio.play('golem_oops');
    await this.poseTo({ ArmL_Upper: [-1.2, 0, 0.6], ArmR_Upper: [-1.2, 0, -0.6], Head: [-0.2, 0, 0] }, 0.2); await this.wait(0.9);
  }

  async ev_collect(ev) {
    const it = this.items[ev.item];
    audio.play('letter_collect', { rate: 1 + (ev.count - 1) * 0.12 });
    this.g.rune = 2.4; this.gv('rune', 1, 0.6);
    this.puff(it.holder.position.clone().setY(0.6), 0xffd060, 18, 1.4);
    this.poseTo({ ArmL_Upper: [-2.7, 0, 0.3], ArmR_Upper: [-2.7, 0, -0.3], Head: [-0.3, 0, 0] }, 0.25, E.back);
    await this.tween(0.55, (t) => { it.o.position.y = 0.55 + t * 1.3; it.o.rotation.y = t * 9; it.holder.scale.setScalar(1 - t * 0.999); }, E.in);
    it.holder.visible = false;
    await this.neutral(0.2);
  }

  async ev_dizzy() {
    audio.play('golem_huh');
    const a0 = this.g.angle;
    await this.tween(1.3, (t) => { this.g.angle = a0 + t * Math.PI * 4; this.g.lean = Math.sin(t * 10) * 0.12; }, E.inOut);
    this.g.angle = a0; this.poseTo({ LegL: [-1.3, 0, 0.2], LegR: [-1.3, 0, -0.2], Head: [0.15, 0, 0.25] }, 0.3, E.bounce);
    this.tween(0.3, (t) => { this.g.hopY = -0.2 * t; }); this.stars(this.actor.position.clone().setY(1.45));
    audio.play('bonk', { volume: 0.5 }); this.dizzy(1.2); await this.wait(1.1);
  }

  async ev_win() {
    const L = this.level;
    if (this.candle) {
      audio.play('candle_light'); if (this.candle.flame) { this.candle.flame.visible = true; this.flames.push({ mesh: this.candle.flame, base: this.candle.flame.scale.clone(), seed: 3 }); }
      this.tween(0.8, (t) => { this.candle.light.intensity = t * CANDLE_LIGHT; }, E.out);
      const wp = this.candle.o.getWorldPosition(new THREE.Vector3()); this.puff(wp.setY(wp.y + 0.5), 0xffb060, 20, 1.2);
    }
    if (this.plant) {
      audio.play('plant_bloom'); const { wilted, bloom } = this.plant; bloom.visible = true; bloom.scale.setScalar(0.01);
      const wp = bloom.getWorldPosition(new THREE.Vector3()); this.puff(wp.setY(wp.y + 0.4), 0x7dffa0, 30, 1.6);
      this.tween(0.9, (t) => { bloom.scale.setScalar(Math.max(t, 0.01)); wilted.scale.setScalar(Math.max(1 - t * 1.4, 0.001)); }, E.elastic);
    }
    for (const m of this.goalGlow) this.tween(1.2, (t) => { m.emissiveIntensity = 3 + Math.sin(t * Math.PI) * 9; }, E.lin);
    this.ring(this.actor.position, L.goal === 'collect' ? 0xffd060 : 0x3ff5e0);
    await this.wait(0.35);
    // face the player and celebrate
    const a0 = this.g.angle; let a1 = 0; while (a1 - a0 > Math.PI) a1 -= Math.PI * 2; while (a0 - a1 > Math.PI) a1 += Math.PI * 2;
    await this.tween(0.35, (t) => { this.g.angle = lerp(a0, a1, t); }, E.back);
    audio.play('golem_happy'); this.gv('rune', 2.2, 0.3);
    for (let i = 0; i < 3; i++) {
      this.poseTo({ ArmL_Upper: [-2.9, 0, 0.45], ArmR_Upper: [-2.9, 0, -0.45], ArmL_Lower: [-0.3, 0, 0], ArmR_Lower: [-0.3, 0, 0], Head: [-0.3, 0, 0] }, 0.16, E.out);
      await this.tween(0.42, (t) => { this.g.hopY = Math.sin(t * Math.PI) * 0.42; this.g.squash = 1 + Math.sin(t * Math.PI) * 0.12; }, E.lin);
      this.land(0.9); this.confetti(this.actor.position.clone().setY(1.2));
      this.poseTo({ ArmL_Upper: [-2.2, 0, 0.9], ArmR_Upper: [-2.2, 0, -0.9] }, 0.1);
      await this.wait(0.1);
    }
    this.gv('rune', 1.2, 0.6); await this.wait(0.2);
  }

  // ---------- particles & fx ----------
  buildDust() {
    const n = 420, pos = new Float32Array(n * 3), seed = new Float32Array(n);
    for (let i = 0; i < n; i++) { pos[i * 3] = rand(-9, 9); pos[i * 3 + 1] = rand(0.2, 7); pos[i * 3 + 2] = rand(-8, 7); seed[i] = Math.random(); }
    const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3)); geo.setAttribute('seed', new THREE.BufferAttribute(seed, 1));
    this.dustMat = new THREE.ShaderMaterial({
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { uTime: { value: 0 }, uPx: { value: 1 } },
      vertexShader: `attribute float seed; uniform float uTime; uniform float uPx; varying float vA;
        void main(){ vec3 p = position; float t = uTime * (0.04 + seed * 0.05);
          p.x += sin(t * 3.1 + seed * 40.0) * 0.7; p.y = mod(p.y + t * 1.4, 7.0) + 0.1; p.z += cos(t * 2.3 + seed * 17.0) * 0.7;
          vec4 mv = modelViewMatrix * vec4(p, 1.0); gl_Position = projectionMatrix * mv;
          gl_PointSize = uPx * (10.0 + seed * 26.0) / -mv.z; vA = (0.25 + 0.75 * abs(sin(uTime * 0.6 + seed * 30.0))) * smoothstep(-9.0, 2.0, -p.x + p.z * 0.2 + 3.0); }`,
      fragmentShader: `varying float vA; void main(){ float d = length(gl_PointCoord - 0.5); float a = (1.0 - smoothstep(0.0, 0.5, d)); gl_FragColor = vec4(vec3(0.75, 0.86, 1.0) * a * vA * 0.5, 1.0); }`,
    });
    const pts = new THREE.Points(geo, this.dustMat); pts.frustumCulled = false; this.scene.add(pts);
  }
  addFx(obj, life, update) { this.scene.add(obj); this.fx.push({ obj, life, t: 0, update }); }
  clearFx() { for (const f of this.fx) { f.obj.removeFromParent(); } this.fx = []; }
  sprite(color, size) {
    if (!this.sparkTex) { const c = document.createElement('canvas'); c.width = c.height = 64; const x = c.getContext('2d'); const gr = x.createRadialGradient(32, 32, 0, 32, 32, 32); gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.35, 'rgba(255,255,255,0.45)'); gr.addColorStop(1, 'rgba(255,255,255,0)'); x.fillStyle = gr; x.fillRect(0, 0, 64, 64); this.sparkTex = new THREE.CanvasTexture(c); }
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.sparkTex, color, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })); s.scale.setScalar(size); return s;
  }
  puff(pos, color, n, spread, ground = false) {
    for (let i = 0; i < n; i++) {
      const dusty = ground; const s = this.sprite(color, dusty ? rand(0.25, 0.5) : rand(0.08, 0.22)); if (dusty) { s.material.blending = THREE.NormalBlending; s.material.opacity = 0.35; } else s.material.color.multiplyScalar(2.5);
      s.position.copy(pos); const v = new THREE.Vector3(rand(-1, 1), ground ? rand(0.1, 0.6) : rand(-0.3, 1.2), rand(-1, 1)).multiplyScalar(spread);
      const o0 = s.material.opacity, s0 = s.scale.x;
      this.addFx(s, rand(0.5, 1.0), (k, dt) => { s.position.addScaledVector(v, dt); v.multiplyScalar(1 - dt * 2.5); if (!ground) v.y -= dt * 0.8; s.material.opacity = o0 * (1 - k); s.scale.setScalar(s0 * (1 + k * (ground ? 2 : 0))); });
    }
  }
  ring(pos, color, size = 5) {
    const m = new THREE.Mesh(new THREE.RingGeometry(0.35, 0.42, 64), new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(3), transparent: true, side: THREE.DoubleSide, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false }));
    m.rotation.x = -Math.PI / 2; m.position.copy(pos).setY(0.03);
    this.addFx(m, 0.9, (k) => { m.scale.setScalar(1 + k * size); m.material.opacity = 1 - k; });
  }
  stars(pos) {
    for (let i = 0; i < 4; i++) {
      const s = this.prop('Star'); s.scale.setScalar(0.38); const a0 = i * Math.PI / 2; s.traverse((o) => { o.castShadow = false; });
      this.addFx(s, 1.9, (k) => { const a = a0 + k * 11; s.position.set(pos.x + Math.cos(a) * 0.32, pos.y + Math.sin(k * 20 + i) * 0.03, pos.z + Math.sin(a) * 0.32); s.rotation.y = a * 2; s.scale.setScalar(0.38 * Math.min(1, (1 - k) * 4) * Math.min(1, k * 8)); });
    }
  }
  shards(pos) {
    for (let i = 0; i < 9; i++) {
      const s = this.prop(`JugShard_${(i % 5) + 1}`); s.position.copy(pos).setY(Math.max(pos.y, 0) + 0.1);
      const v = new THREE.Vector3(rand(-1, 1), rand(1.2, 2.6), rand(-1, 1)), rot = new THREE.Vector3(rand(-8, 8), rand(-8, 8), rand(-8, 8)); const floor = pos.y < -0.05 ? -0.19 : 0.02;
      this.addFx(s, 60, (k, dt) => { if (s.position.y <= floor && v.y <= 0) { s.position.y = floor; return; } v.y -= dt * 9; s.position.addScaledVector(v, dt); s.rotation.x += rot.x * dt; s.rotation.z += rot.z * dt; if (s.position.y < floor) { s.position.y = floor; v.y *= -0.3; v.x *= 0.5; v.z *= 0.5; if (Math.abs(v.y) < 0.4) v.set(0, 0, 0); } });
    }
  }
  confetti(pos) {
    const cols = [0x3ff5e0, 0xffd060, 0xff7aa8, 0x9ad7ff, 0xffffff];
    for (let i = 0; i < 26; i++) {
      const s = this.sprite(cols[i % cols.length], rand(0.07, 0.16)); s.material.color.multiplyScalar(2.2); s.position.copy(pos);
      const v = new THREE.Vector3(rand(-1.6, 1.6), rand(1.5, 4.2), rand(-1.6, 1.6));
      this.addFx(s, rand(0.9, 1.6), (k, dt) => { v.y -= dt * 5; v.multiplyScalar(1 - dt * 0.8); s.position.addScaledVector(v, dt); s.material.opacity = 1 - k * k; });
    }
  }

  // Slow cinematic push-in used on the title screen and intro.
  setCinematic(on) {
    this.cinematic = on;
    if (on) this.g.angle = 0.12; // title: he dozes facing the player, workshop behind him
    else { const a0 = this.g.angle, a1 = this.dirAngle(this.gdir); this.tween(0.9, (t) => { this.g.angle = lerp(a0, a1, t); }, E.inOut); }
  }

  // ---------- touch & play: poke, drag and nudge things (never changes the puzzle) ----------
  setupInput() {
    const cv = this.canvas; this.ray = new THREE.Raycaster(); this.grab = null; this.down = null;
    this.orbitUser = 0; this.liftUser = 0; this.orbitHold = 0; this.headYaw = 0; this.headPitch = 0; this.interactive = false;
    const ndc = (e) => new THREE.Vector2((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
    cv.addEventListener('pointerdown', (e) => {
      try { cv.setPointerCapture(e.pointerId); } catch { /* fine */ }
      const hit = this.interactive && !this.cinematic ? this.pick(ndc(e)) : null;
      this.down = { x: e.clientX, y: e.clientY, lx: e.clientX, ly: e.clientY, moved: false, hit };
      if (hit && hit.drag && !hit.busy) this.startGrab(hit);
    });
    cv.addEventListener('pointermove', (e) => {
      const d = this.down; if (!d) return;
      if (Math.hypot(e.clientX - d.x, e.clientY - d.y) > 7) d.moved = true;
      const dx = e.clientX - d.lx, dy = e.clientY - d.ly; d.lx = e.clientX; d.ly = e.clientY;
      if (this.grab) this.moveGrab(ndc(e));
      else if (d.moved && !this.cinematic) { this.orbitUser = clamp(this.orbitUser - dx * 0.005, -0.75, 0.75); this.liftUser = clamp(this.liftUser + dy * 0.02, -1.6, 2.6); this.orbitHold = 3; }
    });
    const up = () => { const d = this.down; this.down = null; if (!d) return; if (this.grab) this.endGrab(!d.moved); else if (d.hit && !d.moved && !d.hit.busy) this.poke(d.hit); };
    cv.addEventListener('pointerup', up); cv.addEventListener('pointercancel', up);
  }
  pick(ndc) {
    this.ray.setFromCamera(ndc, this.camera);
    for (const h of this.ray.intersectObjects([this.board, this.actor], true)) {
      let o = h.object; let vis = true;
      for (let p = o; p; p = p.parent) if (!p.visible) vis = false;
      if (!vis) continue;
      while (o && !o.userData.touch) o = o.parent;
      if (o) return o.userData.touch;
    }
    return null;
  }
  groundPoint(ndc, y) {
    this.ray.setFromCamera(ndc, this.camera);
    return this.ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), -y), new THREE.Vector3());
  }
  startGrab(hit) {
    const golem = hit.kind === 'golem';
    const home = golem ? this.cellPos(this.gx, this.gz) : hit.it.home.clone();
    this.grab = { hit, home, target: home.clone(), vel: new THREE.Vector3(), lift: 0 };
    if (golem) { audio.play('golem_huh', { volume: 0.7 }); this.gv('eye', 0.8, 0.25); this.poseTo({ Torso: [0, 0, 0], Head: [-0.25, 0, 0], ArmL_Upper: [0, 0, 1.1], ArmR_Upper: [0, 0, -1.1] }, 0.25, E.back); }
    else if (hit.it.type === 'cat') audio.play('cat_purr', { volume: 0.9 });
    else if (hit.it.type === 'letter') audio.play('letter_collect', { volume: 0.35, rate: 1.3 });
    else audio.play('pickup', { volume: 0.6 });
  }
  moveGrab(ndc) {
    const g = this.grab; const p = this.groundPoint(ndc, 0.45); if (!p) return;
    const d = p.sub(g.home).setY(0); const len = d.length(); const max = 0.62;
    if (len > 0.001) d.multiplyScalar((max * (1 - Math.exp(-len / max))) / len); // rubber band
    g.target.copy(g.home).add(d);
  }
  endGrab(tap) {
    const g = this.grab; if (!g) return; this.grab = null; const { hit, home } = g; const o = hit.o; hit.busy = true;
    const from = o.position.clone(); const lift0 = g.lift; const golem = hit.kind === 'golem';
    const rx = o.rotation.x, rz = o.rotation.z;
    this.tween(0.42, (t) => {
      o.position.x = lerp(from.x, home.x, t); o.position.z = lerp(from.z, home.z, t);
      const y = lift0 * (1 - t) + Math.sin(t * Math.PI) * 0.12;
      if (golem) this.g.hopY = y; else { o.position.y = home.y + y; o.rotation.x = rx * (1 - t); o.rotation.z = rz * (1 - t); }
    }, E.inOut).then(() => {
      hit.busy = false;
      if (golem) { this.g.hopY = 0; this.land(0.75); if (!this.g.awake) { this.poseTo(SLEEP, 0.6); this.gv('eye', 0, 1.2); } }
      else { o.position.copy(home); audio.play('putdown', { volume: 0.5, rate: hit.it.type === 'letter' ? 1.8 : 1.1 }); this.puff(home.clone().setY(0.03), 0xb9a58c, 5, 0.5, true); if (hit.it.type === 'cat') audio.play('cat_meow', { volume: 0.5, delay: 0.1 }); }
    });
    if (tap) this.poke(hit, true);
  }
  // Snap anything being held back home (called when a run starts).
  releaseGrab() { if (this.grab) { const g = this.grab; this.grab = null; g.hit.o.position.copy(g.home); g.hit.o.rotation.x = g.hit.o.rotation.z = 0; this.g.hopY = 0; } this.down = null; }
  poke(hit, quiet = false) {
    const o = hit.o;
    if (hit.kind === 'tile') {
      const scale = [0, 2, 4, 7, 9, 12, 14, 16]; const semi = scale[(hit.x + hit.z * 3) % scale.length];
      audio.play('stone_place', { volume: 0.55, rate: 0.75 * Math.pow(2, semi / 12) }); // the floor plays like a stone xylophone
      this.tween(0.32, (t) => { o.position.y = -0.05 * Math.sin(t * Math.PI); }, E.out).then(() => { o.position.y = 0; });
      this.ring(o.position, 0x3ff5e0, 1.5);
    } else if (hit.kind === 'block') {
      audio.play('ui_tap', { volume: 0.7, rate: rand(0.55, 0.75) }); hit.busy = true;
      this.puff(o.position.clone().setY(0.95 * (o.userData.sy || 1)), 0xd8c8b0, 5, 0.5);
      this.tween(0.8, (t) => { o.rotation.z = Math.sin(t * 15) * 0.06 * (1 - t); o.scale.y = (o.userData.sy || 1) * (1 + Math.sin(t * 15) * 0.03 * (1 - t)); }, E.lin).then(() => { o.rotation.z = 0; o.scale.y = o.userData.sy || 1; hit.busy = false; });
    } else if (hit.kind === 'item') {
      const type = hit.it.type;
      if (type === 'letter') { if (!quiet) audio.play('star', { volume: 0.6, rate: rand(0.9, 1.3) }); const r0 = hit.it.o.rotation.y; this.spin = { o: hit.it.o, t: 0 }; this.puff(o.position.clone().setY(0.6), 0xffd060, 8, 0.8); this.tween(0.7, (t) => { hit.it.o.rotation.y = r0 + t * Math.PI * 4; }, E.out); }
      else if (type === 'cat') { if (!quiet) audio.play(Math.random() < 0.5 ? 'cat_meow' : 'cat_purr', { volume: 0.8 }); this.tween(0.45, (t) => { hit.it.o.scale.set(1 + Math.sin(t * Math.PI) * 0.12, 1 - Math.sin(t * Math.PI) * 0.18, 1 + Math.sin(t * Math.PI) * 0.12); }, E.lin); }
      else { if (!quiet) audio.play('putdown', { volume: 0.5, rate: 1.7 }); this.tween(0.7, (t) => { hit.it.o.rotation.z = Math.sin(t * 14) * 0.16 * (1 - t); }, E.lin).then(() => { hit.it.o.rotation.z = 0; }); }
    } else if (hit.kind === 'golem') {
      if (!quiet) audio.play('golem_grunt', { volume: 0.8 });
      this.g.squash = 0.84; this.tween(0.5, (t) => { this.g.squash = lerp(0.84, 1, t); }, E.elastic);
      this.g.rune = Math.max(this.g.rune, 1.4); this.gv('rune', this.g.awake ? 1 : 0.12, 1.2);
      if (!this.g.awake) { this.g.eye = 1; this.gv('eye', 0, 1.6, E.in); }
      this.shake = Math.max(this.shake, 0.03);
    }
  }

  // ---------- frame ----------
  resize() {
    const w = innerWidth, h = innerHeight; this.renderer.setSize(w, h, false); this.composer.setSize(w, h);
    this.camera.aspect = w / h; this.camera.updateProjectionMatrix(); this.aspect = w / h;
    this.dustMat.uniforms.uPx.value = h * 0.5 * this.renderer.getPixelRatio() / 400;
  }
  frame() {
    const raw = Math.min(this.clock.getDelta(), 0.05); const dt = raw * this.speed; this.time += raw; const T = this.time;
    for (const tw of [...this.tweens]) { tw.t += dt; const k = Math.min(1, tw.t / tw.dur); tw.fn(tw.ease(k)); if (k >= 1) { this.tweens.delete(tw); tw.res(); } }
    for (const f of [...this.fx]) { f.t += dt; const k = Math.min(1, f.t / f.life); f.update(k, dt); if (k >= 1) { f.obj.removeFromParent(); this.fx.splice(this.fx.indexOf(f), 1); } }

    // golem: layered idle on top of the animated pose
    const g = this.g, j = this.j;
    if (j) {
      const br = Math.sin(T * 1.7) * (g.awake ? 0.014 : 0.006);
      g.blink -= raw; if (g.blink < -g.nextBlink) { g.blink = 0.13; g.nextBlink = rand(1.6, 5); }
      const blink = g.blink > 0 ? Math.abs(Math.cos((g.blink / 0.13) * Math.PI)) : 1;
      this.eyes.forEach((e, i) => e.scale.set(this.eyeRest[i].x, this.eyeRest[i].y * lerp(0.12, 1, blink), this.eyeRest[i].z));
      const idleHead = g.awake ? Math.sin(T * 0.6) * 0.07 : 0;
      for (const n of JOINTS) { const r = this.rest[n], p = this.pose[n]; j[n].rotation.set(r.x + p.x, r.y + p.y, r.z + p.z); }
      j.Head.rotation.y += idleHead; j.Torso.rotation.x += br * 2;
      j.ArmL_Upper.rotation.z += br * 3; j.ArmR_Upper.rotation.z -= br * 3;
      // while held: follow the finger with a springy lag and dangle
      if (this.grab) {
        const gr = this.grab, o = gr.hit.o, k2 = 1 - Math.exp(-raw * 14); const px = o.position.x, pz = o.position.z;
        o.position.x = lerp(px, gr.target.x, k2); o.position.z = lerp(pz, gr.target.z, k2); gr.lift = lerp(gr.lift, 0.3, k2);
        const vx = (o.position.x - px) / Math.max(raw, 0.001), vz = (o.position.z - pz) / Math.max(raw, 0.001);
        if (gr.hit.kind === 'golem') { g.hopY = gr.lift; this.pose.LegL.x = Math.sin(T * 9) * 0.35; this.pose.LegR.x = -Math.sin(T * 9) * 0.35; this.pose.LegL.z = 0.12; this.pose.LegR.z = -0.12; }
        else { o.position.y = gr.home.y + gr.lift; o.rotation.z = lerp(o.rotation.z, clamp(-vx * 0.12, -0.5, 0.5), 0.2); o.rotation.x = lerp(o.rotation.x, clamp(vz * 0.12, -0.5, 0.5), 0.2); }
      }
      // the golem's head lazily follows your finger
      let wantYaw = 0, wantPitch = 0;
      if (this.interactive && !this.cinematic && !this.grab) {
        const pt = this.groundPoint(new THREE.Vector2(this.pointer.x, -this.pointer.y), 0.8);
        if (pt) { const loc = this.actor.worldToLocal(pt); wantYaw = clamp(Math.atan2(loc.x, loc.z), -0.8, 0.8) * (g.awake ? 1 : 0.55); wantPitch = clamp((loc.length() - 3) * -0.05, -0.2, 0.15); }
      }
      this.headYaw = lerp(this.headYaw, wantYaw, 1 - Math.exp(-raw * 3)); this.headPitch = lerp(this.headPitch, wantPitch, 1 - Math.exp(-raw * 3));
      j.Head.rotation.y += this.headYaw; j.Head.rotation.x += this.headPitch;
      this.bodyRoot.position.y = this.restY + g.hopY;
      this.bodyRoot.scale.set(1 + (1 - g.squash) * 0.6, g.squash + br, 1 + (1 - g.squash) * 0.6);
      this.bodyRoot.rotation.x = g.lean;
      this.actor.rotation.y = g.angle;
      const flick = 0.9 + 0.1 * Math.sin(T * 9) * Math.sin(T * 3.7);
      for (const m of this.runeMats) m.emissiveIntensity = 3.2 * g.rune * flick;
      for (const m of this.eyeMats) m.emissiveIntensity = 4.5 * g.eye;
      this.runeLight.position.copy(this.actor.position).add(new THREE.Vector3(Math.sin(g.angle) * 0.5, 0.8, Math.cos(g.angle) * 0.5));
      this.runeLight.intensity = 5 * g.rune;
      if (this.carrying && this.carrying.type !== 'cat') this.hold.position.y = 0.62 + g.hopY * 0.2;
    }
    // floating letters, flames, fire flicker
    if (this.items) for (const it of this.items) if (it.type === 'letter' && it.holder.visible && it.holder.scale.x > 0.99) { it.o.position.y = 0.55 + Math.sin(T * 1.8 + it.x) * 0.06; it.o.rotation.y = Math.sin(T * 0.9 + it.z) * 0.5; }
    for (const f of this.flames) { const n = Math.sin(T * 13 + f.seed) * 0.5 + Math.sin(T * 7.3 + f.seed * 2) * 0.5; f.mesh.scale.set(f.base.x * (1 + n * 0.06), f.base.y * (1 + n * 0.14), f.base.z * (1 + n * 0.06)); }
    const fl = 0.86 + 0.14 * Math.sin(T * 11) * Math.sin(T * 4.3) + 0.05 * Math.sin(T * 27);
    this.fire.intensity = 60 * fl; if (this.candle && this.candle.light.intensity > 1) this.candle.light.intensity = CANDLE_LIGHT * (0.9 + 0.1 * Math.sin(T * 15));
    for (const m of this.goalGlow || []) if (m.emissiveIntensity <= 3.05) m.emissiveIntensity = 2.2 + Math.sin(T * 2.4) * 0.8;

    // camera: gentle pointer parallax, breathing drift, impact shake
    const cam = this.camera; const portrait = Math.max(1, 1.25 / this.aspect);
    if (!this.down) { this.orbitHold -= raw; if (this.orbitHold < 0) { const r = Math.exp(-raw * 1.4); this.orbitUser *= r; this.liftUser *= r; } }
    const orbit = this.camOrbit + this.orbitUser + this.pointer.x * 0.14 + Math.sin(T * 0.15) * 0.035;
    const zoom = this.camZoom * portrait * (this.cinematic ? 0.62 + 0.02 * Math.sin(T * 0.2) : 1);
    const want = new THREE.Vector3(Math.sin(orbit) * this.camBase.z * zoom, (this.camBase.y + this.camLift + this.liftUser - this.pointer.y * 0.5) * zoom, Math.cos(orbit) * this.camBase.z * zoom);
    if (this.cinematic) { // title shot: low three-quarter view of the sleeping golem's face
      const a = 0.42 + this.pointer.x * 0.12 + Math.sin(T * 0.13) * 0.06, d = 4.4 * portrait;
      want.set(this.actor.position.x + Math.sin(a) * d, 1.7 - this.pointer.y * 0.25, this.actor.position.z + Math.cos(a) * d);
    }
    if (!this.camPos) { this.camPos = want.clone(); this.lookPos = this.camTarget.clone(); }
    const k = 1 - Math.exp(-raw * 2.2); this.camPos.lerp(want, k);
    const look = this.cinematic ? new THREE.Vector3(this.actor.position.x, 0.75, this.actor.position.z) : this.camTarget; this.lookPos.lerp(look, k);
    cam.position.copy(this.camPos);
    if (this.shake > 0.001) { cam.position.x += rand(-1, 1) * this.shake; cam.position.y += rand(-1, 1) * this.shake; this.shake *= Math.exp(-raw * 9); }
    cam.lookAt(this.lookPos);
    this.dof.cocMaterial.worldFocusDistance = cam.position.distanceTo(this.lookPos);
    this.dof.cocMaterial.worldFocusRange = this.cinematic ? 3 : 8;
    this.dustMat.uniforms.uTime.value = T; if (this.shaftMat) this.shaftMat.uniforms.uTime.value = T;
    this.composer.render(raw);
  }
}

const SLEEP = { Torso: [0.32, 0, 0], Head: [0.5, 0, 0], ArmL_Upper: [0.1, 0, -0.05], ArmR_Upper: [0.1, 0, 0.05], ArmL_Lower: [0, 0, 0], ArmR_Lower: [0, 0, 0], LegL: [0, 0, 0], LegR: [0, 0, 0], Hips: [0, 0, 0], HandL: [0, 0, 0], HandR: [0, 0, 0] };
const REACH = { Torso: [0.5, 0, 0], Head: [-0.1, 0, 0], ArmL_Upper: [-1.0, 0, -0.25], ArmR_Upper: [-1.0, 0, 0.25], ArmL_Lower: [-0.35, 0, 0], ArmR_Lower: [-0.35, 0, 0] };
const CARRY = { Torso: [0.05, 0, 0], Head: [0.1, 0, 0], ArmL_Upper: [-1.15, 0, -0.3], ArmR_Upper: [-1.15, 0, 0.3], ArmL_Lower: [-0.5, 0, 0], ArmR_Lower: [-0.5, 0, 0] };
