/**
 * Original, illustrative blower assembly. No manufacturer CAD is embedded.
 * Three.js is loaded from the self-hosted MIT distribution only near the scene.
 * Nothing here changes native scroll, order controls or focus.
 */

const clamp = (value, min = 0, max = 1) => Math.max(min, Math.min(max, value));
const smooth = (value) => {
  const t = clamp(value);
  return t * t * (3 - 2 * t);
};
const segment = (progress, from, to) => smooth((progress - from) / (to - from));
const resolveElement = (value, scope = document) =>
  typeof value === "string" ? scope.querySelector(value) : value;

/**
 * @param {{canvas: HTMLCanvasElement|string, section?: HTMLElement|string,
 * container?: HTMLElement|string, poster?: HTMLElement|string,
 * toggle?: HTMLButtonElement|string, onProgress?: Function,
 * onReady?: Function, onError?: Function}} options
 * @returns {{ready: Promise<boolean>, destroy: Function, setStatic: Function,
 * refresh: Function, setProgress: Function, getState: Function}}
 */
export function initBlowerScene(options = {}) {
  const canvas = resolveElement(options.canvas);
  const section = resolveElement(options.section || options.container) || canvas?.parentElement;
  const poster = resolveElement(options.poster, section || document);
  const toggle = resolveElement(options.toggle, section || document)
    || section?.querySelector("[data-motion-toggle]");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const mobileLayout = window.matchMedia("(max-width: 767px)");
  let renderer, scene, camera, assembly, parts, rotors, environment;
  let destroyed = false, initialized = false, initializing = false;
  let manuallyStatic = false, unavailable = false, onScreen = true;
  let raf = 0, progress = 0, targetProgress = 0, lastFrame = 0;
  let resizeObserver, nearObserver, visibleObserver;
  let pendingSize = true, lastWidth = 0, lastHeight = 0;
  let forcedProgress = null;
  const listenerRemovers = [];
  let resolveReady;
  const ready = new Promise((resolve) => { resolveReady = resolve; });

  const listen = (target, type, handler, opts) => {
    target?.addEventListener(type, handler, opts);
    listenerRemovers.push(() => target?.removeEventListener(type, handler, opts));
  };
  const isStatic = () => manuallyStatic || reducedMotion.matches || unavailable;

  function showPoster(reason = "static") {
    if (canvas) { canvas.style.opacity = "0"; canvas.setAttribute("aria-hidden", "true"); }
    if (poster) poster.style.opacity = "1";
    if (section) {
      section.dataset.motionState = reason;
      section.dataset.motionActive = "false";
    }
    if (toggle) {
      toggle.setAttribute("aria-pressed", String(manuallyStatic || reducedMotion.matches));
      toggle.textContent = reducedMotion.matches ? "Анимация отключена" : "Включить анимацию";
      toggle.disabled = reducedMotion.matches || unavailable;
    }
  }

  function updateToggle() {
    if (!toggle) return;
    const staticMode = isStatic();
    toggle.setAttribute("aria-pressed", String(staticMode));
    toggle.textContent = reducedMotion.matches
      ? "Анимация отключена"
      : staticMode ? "Включить анимацию" : "Статичный вид";
    toggle.disabled = reducedMotion.matches || unavailable;
  }

  function measureProgress() {
    if (!section || forcedProgress !== null) return forcedProgress ?? 0;
    const rect = section.getBoundingClientRect();
    const viewport = window.innerHeight;
    if (mobileLayout.matches) {
      // Deliberately short, unpinned touch story. The wrapper remains normal flow.
      return clamp((viewport * 0.78 - rect.top) / (viewport * 0.78 + rect.height * 0.45));
    }
    const travel = rect.height - viewport;
    return travel > 80
      ? clamp(-rect.top / travel)
      : clamp((viewport * 0.6 - rect.top) / (rect.height + viewport * 0.3));
  }

  function requestFrame() {
    if (!destroyed && initialized && !raf && onScreen && !document.hidden && !isStatic()) {
      raf = requestAnimationFrame(renderFrame);
    }
  }

  function onScroll() {
    targetProgress = measureProgress();
    requestFrame();
  }

  function resize() {
    pendingSize = true;
    targetProgress = measureProgress();
    requestFrame();
  }

  function resizeRenderer() {
    const bounds = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.round(bounds.width));
    const height = Math.max(1, Math.round(bounds.height));
    if (width !== lastWidth || height !== lastHeight || pendingSize) {
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, mobileLayout.matches ? 1.25 : 1.65));
      renderer.setSize(width, height, false);
      lastWidth = width; lastHeight = height; pendingSize = false;
    }
  }

  function renderFrame(time) {
    raf = 0;
    if (destroyed || !initialized || !onScreen || document.hidden || isStatic()) return;
    const elapsed = lastFrame ? Math.min(time - lastFrame, 250) : 16;
    lastFrame = time;
    const delta = targetProgress - progress;
    progress = Math.abs(delta) < 0.0003 ? targetProgress : progress + delta * (1 - Math.exp(-elapsed / 72));
    if (Math.abs(targetProgress - progress) < 0.0003) progress = targetProgress;
    resizeRenderer();
    const desktop = !mobileLayout.matches;
    const open = segment(progress, 0.25, 0.56) * (1 - segment(progress, 0.71, 0.94));
    const turn = segment(progress, 0.045, 0.255);
    const approach = segment(progress, 0.94, 1);
    // The assembled product fills the stage; the view gently widens only to make
    // room for the exploded parts. Orthographic projection keeps the axis level.
    const halfWidth = desktop ? 5.6 + 3.5 * open : 5.3 + 1.6 * open;
    const halfHeight = halfWidth / (lastWidth / lastHeight);
    camera.left = -halfWidth; camera.right = halfWidth;
    camera.top = halfHeight; camera.bottom = -halfHeight;
    camera.updateProjectionMatrix();
    // No camera roll, diagonal axis or wandering parts during exploded rest.
    assembly.rotation.set(0, (desktop ? 0.68 : 0.24) * (1 - turn), 0);
    assembly.position.y = -0.13 - approach * 0.06;
    assembly.scale.setScalar(desktop ? 1 : 0.92);
    for (const part of parts) {
      const separation = desktop ? 1 : 0.61;
      part.mesh.position.x = part.x + part.offset * open * separation;
    }
    rotors.children.forEach((rotor, index) => {
      rotor.rotation.x = (index ? -1 : 1) * (open * 0.7 + turn * 0.18);
    });
    // A short photo-to-model crossfade makes the high fidelity poster the entry state.
    const modelOpacity = segment(progress, 0.035, 0.13);
    canvas.style.opacity = String(modelOpacity);
    if (poster) poster.style.opacity = String(1 - modelOpacity);
    const phase = progress < 0.25 ? "turning"
      : progress < 0.56 ? "disassembling"
      : progress < 0.71 ? "exploded"
      : progress < 0.94 ? "reassembling" : "assembled";
    section.dataset.motionState = phase;
    section.dataset.motionActive = "true";
    section.style.setProperty("--assembly-progress", String(progress));
    section.style.setProperty("--assembly-explosion", String(open));
    renderer.render(scene, camera);
    options.onProgress?.(progress, { phase, explosion: open, mobile: !desktop });
    section.dispatchEvent(new CustomEvent("blower:progress", {
      detail: { progress, phase, explosion: open, mobile: !desktop },
    }));
    if (Math.abs(targetProgress - progress) > 0.0003) requestFrame();
  }

  async function initialize() {
    if (initializing || initialized || destroyed || !canvas || !section || isStatic()) return;
    initializing = true;
    try {
      const THREE = await import("../vendor/three/three.module.js");
      if (destroyed || isStatic()) { initializing = false; return; }
      renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: "low-power" });
      renderer.setClearColor(0xffffff, 0);
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 0.95;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      scene = new THREE.Scene();
      camera = new THREE.OrthographicCamera(-9.1, 9.1, 5.1, -5.1, 0.1, 70);
      camera.position.set(0, 1.25, 18);
      camera.lookAt(0, 0.1, 0);
      // A local neutral studio environment, no remote image or tracking request.
      const studio = new THREE.Scene();
      studio.background = new THREE.Color(0x657587);
      const wall = new THREE.Mesh(new THREE.BoxGeometry(25, 18, 24), new THREE.MeshBasicMaterial({ color: 0x77818b, side: THREE.BackSide }));
      studio.add(wall);
      const panel = (w, h, x, y, z, color = 0xffffff) => {
        const item = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color, side: THREE.DoubleSide }));
        item.position.set(x, y, z); item.lookAt(0, 0, 0); studio.add(item);
      };
      panel(10, 8, -8, 6, 5); panel(12, 6, 9, 5, -3, 0xe3edff); panel(14, 5, 0, 8, 0);
      const pmrem = new THREE.PMREMGenerator(renderer);
      environment = pmrem.fromScene(studio, 0.07);
      scene.environment = environment.texture;
      pmrem.dispose();
      studio.traverse((item) => { item.geometry?.dispose(); item.material?.dispose(); });
      scene.add(new THREE.HemisphereLight(0xffffff, 0x64768c, 1.3));
      const key = new THREE.DirectionalLight(0xffffff, 3.6);
      key.position.set(-4, 8, 6); key.castShadow = true;
      key.shadow.mapSize.set(1024, 1024);
      key.shadow.camera.left = -11; key.shadow.camera.right = 11;
      key.shadow.camera.top = 7; key.shadow.camera.bottom = -7;
      key.shadow.normalBias = 0.02; key.shadow.bias = -0.0002;
      scene.add(key);
      const fill = new THREE.DirectionalLight(0xa4c7ff, 1.8); fill.position.set(6, 3, -5); scene.add(fill);
      const floor = new THREE.Mesh(new THREE.PlaneGeometry(55, 35), new THREE.ShadowMaterial({ opacity: 0.13 }));
      floor.rotation.x = -Math.PI / 2; floor.position.y = -1.88; floor.receiveShadow = true; scene.add(floor);
      const model = buildAssembly(THREE);
      assembly = model.assembly; parts = model.parts; rotors = model.rotors;
      scene.add(assembly);
      initialized = true; initializing = false;
      targetProgress = measureProgress(); progress = targetProgress;
      section.dataset.motionReady = "true";
      updateToggle(); requestFrame();
      options.onReady?.(true); resolveReady(true);
    } catch (error) {
      initializing = false; unavailable = true;
      disposeRenderer(); showPoster("unavailable");
      options.onError?.(error); options.onReady?.(false); resolveReady(false);
    }
  }

  function disposeRenderer() {
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    const geometries = new Set(), materials = new Set();
    scene?.traverse((item) => {
      if (item.geometry) geometries.add(item.geometry);
      if (Array.isArray(item.material)) item.material.forEach((mat) => materials.add(mat));
      else if (item.material) materials.add(item.material);
    });
    geometries.forEach((item) => item.dispose());
    materials.forEach((item) => item.dispose());
    environment?.dispose(); renderer?.dispose();
    initialized = false;
  }

  function setStatic(value = true) {
    manuallyStatic = Boolean(value);
    if (isStatic()) {
      if (raf) cancelAnimationFrame(raf);
      raf = 0; showPoster();
    } else {
      updateToggle(); initialize(); onScroll();
    }
  }

  if (!canvas || !section) { resolveReady(false); return { ready, destroy() {}, setStatic() {}, refresh() {}, setProgress() {}, getState: () => ({ available: false }) }; }
  canvas.setAttribute("aria-hidden", "true");
  showPoster(reducedMotion.matches ? "reduced-motion" : "loading");
  listen(toggle, "click", () => setStatic(!manuallyStatic));
  listen(window, "scroll", onScroll, { passive: true });
  listen(window, "resize", resize, { passive: true });
  listen(document, "visibilitychange", () => {
    if (document.hidden && raf) { cancelAnimationFrame(raf); raf = 0; }
    else { lastFrame = 0; onScroll(); }
  });
  listen(canvas, "webglcontextlost", (event) => {
    event.preventDefault(); unavailable = true; disposeRenderer(); showPoster("unavailable"); options.onReady?.(false);
  });
  listen(reducedMotion, "change", () => {
    if (reducedMotion.matches) { if (raf) cancelAnimationFrame(raf); raf = 0; showPoster("reduced-motion"); }
    else { updateToggle(); initialize(); onScroll(); }
  });
  listen(mobileLayout, "change", resize);
  if ("ResizeObserver" in window) { resizeObserver = new ResizeObserver(resize); resizeObserver.observe(canvas); }
  if ("IntersectionObserver" in window) {
    nearObserver = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) { initialize(); nearObserver.disconnect(); }
    }, { rootMargin: "450px 0px" });
    nearObserver.observe(section);
    visibleObserver = new IntersectionObserver((entries) => {
      onScreen = entries.some((entry) => entry.isIntersecting);
      if (!onScreen && raf) { cancelAnimationFrame(raf); raf = 0; }
      else { lastFrame = 0; onScroll(); }
    });
    visibleObserver.observe(section);
  } else initialize();
  if (reducedMotion.matches) resolveReady(false);

  return {
    ready,
    setStatic,
    refresh: resize,
    // Useful for deterministic visual QA or a separate explicitly wired control.
    setProgress(value) { forcedProgress = value === null ? null : clamp(Number(value) || 0); onScroll(); },
    getState: () => ({
      progress, targetProgress, available: initialized, static: isStatic(), phase: section.dataset.motionState,
      render: renderer ? { calls: renderer.info.render.calls, triangles: renderer.info.render.triangles,
        geometries: renderer.info.memory.geometries, textures: renderer.info.memory.textures } : null,
    }),
    destroy() {
      if (destroyed) return;
      destroyed = true;
      nearObserver?.disconnect(); visibleObserver?.disconnect(); resizeObserver?.disconnect();
      listenerRemovers.forEach((remove) => remove());
      disposeRenderer(); showPoster("static"); resolveReady(false);
      section.style.removeProperty("--assembly-progress"); section.style.removeProperty("--assembly-explosion");
      delete section.dataset.motionReady;
    },
  };
}

function buildAssembly(T) {
  const assembly = new T.Group();
  const blue = new T.MeshStandardMaterial({ color: 0x07365d, roughness: 0.31, metalness: 0.64 });
  const darkBlue = new T.MeshStandardMaterial({ color: 0x03233f, roughness: 0.34, metalness: 0.68 });
  const edgeBlue = new T.MeshStandardMaterial({ color: 0x10436c, roughness: 0.3, metalness: 0.67 });
  const silver = new T.MeshStandardMaterial({ color: 0x9eaebc, roughness: 0.23, metalness: 0.91 });
  const bolts = new T.MeshStandardMaterial({ color: 0x9ba8ae, roughness: 0.25, metalness: 0.88 });
  const black = new T.MeshStandardMaterial({ color: 0x101923, roughness: 0.45, metalness: 0.33 });
  const inner = new T.MeshStandardMaterial({ color: 0x273f52, roughness: 0.42, metalness: 0.56, side: T.DoubleSide });
  const parts = [];
  function mesh(geometry, material, parent, x = 0, y = 0, z = 0) {
    const object = new T.Mesh(geometry, material);
    object.position.set(x, y, z); object.castShadow = true; object.receiveShadow = true;
    parent.add(object); return object;
  }
  function group(x, offset) {
    const item = new T.Group(); item.position.x = x; assembly.add(item);
    parts.push({ mesh: item, x, offset }); return item;
  }
  function cylinder(radius, length, material, parent, x = 0, y = 0, z = 0, sides = 56) {
    const item = mesh(new T.CylinderGeometry(radius, radius, length, sides), material, parent, x, y, z);
    item.rotation.z = -Math.PI / 2; return item;
  }
  function box(w, h, d, material, parent, x = 0, y = 0, z = 0) { return mesh(new T.BoxGeometry(w, h, d), material, parent, x, y, z); }
  function ring(radius, hole, length, material, parent, x, y = 0, z = 0, boltHoles = false) {
    const shape = new T.Shape(); shape.absarc(0, 0, radius, 0, Math.PI * 2, false);
    const opening = new T.Path(); opening.absarc(0, 0, hole, 0, Math.PI * 2, true); shape.holes.push(opening);
    if (boltHoles) for (let i = 0; i < 8; i++) {
      const angle = i / 8 * Math.PI * 2;
      const cut = new T.Path(); cut.absarc(Math.cos(angle) * radius * 0.78, Math.sin(angle) * radius * 0.78, 0.065, 0, Math.PI * 2, true); shape.holes.push(cut);
    }
    const geometry = new T.ExtrudeGeometry(shape, { depth: length, bevelEnabled: true, bevelSegments: 2, steps: 1, bevelSize: 0.023, bevelThickness: 0.023, curveSegments: 36 });
    geometry.translate(0, 0, -length / 2); geometry.rotateY(Math.PI / 2);
    return mesh(geometry, material, parent, x, y, z);
  }
  function casting(width, height, length, material, parent, x = 0, y = 0, z = 0, hollow = false) {
    const shape = roundedShape(T, width, height, 0.26);
    if (hollow) {
      const hole = roundedShape(T, width - 0.31, height - 0.31, 0.19, true);
      shape.holes.push(hole);
    }
    const geometry = new T.ExtrudeGeometry(shape, { depth: length, steps: 1, bevelEnabled: true, bevelSegments: 3, bevelSize: 0.055, bevelThickness: 0.055, curveSegments: 12 });
    geometry.translate(0, 0, -length / 2); geometry.rotateY(Math.PI / 2);
    return mesh(geometry, material, parent, x, y, z);
  }
  function bolt(x, y, z, parent, axis = "x") {
    const item = cylinder(0.076, 0.085, bolts, parent, x, y, z, 6);
    if (axis === "y") item.rotation.z = 0;
    if (axis === "z") item.rotation.set(Math.PI / 2, 0, 0);
    return item;
  }

  // Structural foundation remains horizontal while components travel on X only.
  const base = group(0, 0);
  box(8.2, 0.24, 2.28, darkBlue, base, 0.3, -1.5);
  for (const z of [-1.03, 1.03]) {
    box(8.3, 0.28, 0.15, edgeBlue, base, 0.3, -1.41, z);
    box(8.3, 0.075, 0.23, edgeBlue, base, 0.3, -1.26, z);
  }
  for (const x of [-3.4, 3.65]) for (const z of [-0.87, 0.87]) {
    cylinder(0.22, 0.17, black, base, x, -1.8, z).rotation.z = 0;
    cylinder(0.14, 0.23, silver, base, x, -1.68, z).rotation.z = 0;
    bolt(x, -1.35, z, base, "y");
  }
  for (const x of [-1.65, 0.4, 2.3, 3.35]) for (const z of [-0.62, 0.62]) {
    box(0.4, 0.3, 0.4, blue, base, x, -1.15, z);
  }

  const intake = group(-2.5, -4.6);
  ring(0.73, 0.59, 0.48, blue, intake, 0.04);
  ring(1.03, 0.59, 0.19, silver, intake, -0.28, 0, 0, true);
  ring(0.68, 0.59, 0.5, inner, intake, 0.04);
  ring(0.86, 0.55, 0.15, blue, intake, 0.31);

  const cover = group(-2.05, -3.48);
  casting(2.0, 2.22, 0.21, blue, cover);
  ring(0.74, 0.55, 0.25, edgeBlue, cover, -0.16);
  for (const y of [-0.88, 0.88]) for (const z of [-0.71, 0.71]) bolt(-0.16, y, z, cover);

  const casing = group(-0.65, -2.6);
  casting(2.0, 2.22, 2.6, blue, casing, 0, 0, 0, true);
  // Cast ribs have thickness and shadow instead of painted texture stripes.
  for (let i = 0; i < 7; i++) casting(2.11, 2.31, 0.09, edgeBlue, casing, -1.11 + i * 0.37, 0, 0, true);
  box(1.4, 0.12, 1.32, blue, casing, 0, 1.22);
  box(0.97, 0.26, 0.94, darkBlue, casing, 0, 1.34);
  for (const x of [-0.51, 0.51]) for (const z of [-0.48, 0.48]) bolt(x, 1.29, z, casing, "y");
  const eye = mesh(new T.TorusGeometry(0.15, 0.037, 10, 28), silver, casing, 0.22, 1.62, 0);
  eye.rotation.y = Math.PI / 2;
  // Two small machined bearing housings make the casting mechanically legible.
  for (const y of [-0.44, 0.44]) cylinder(0.27, 0.12, darkBlue, casing, 1.36, y);

  const rotorPart = group(-0.62, 1.05);
  const rotors = new T.Group(); rotorPart.add(rotors);
  for (let i = 0; i < 2; i++) {
    const rotor = new T.Group(); rotor.position.y = i ? -0.43 : 0.43;
    rotors.add(rotor);
    mesh(helicalRotor(T, 2.44, i ? -1 : 1), silver, rotor);
    cylinder(0.12, 3.36, silver, rotor);
    for (const x of [-1.3, 1.3]) cylinder(0.2, 0.13, bolts, rotor, x);
  }

  const rear = group(0.87, 2.31);
  casting(2, 2.22, 0.23, blue, rear);
  for (const y of [-0.43, 0.43]) {
    cylinder(0.31, 0.13, edgeBlue, rear, 0.2, y);
    cylinder(0.14, 0.15, silver, rear, 0.28, y);
  }
  for (const y of [-0.88, 0.88]) for (const z of [-0.72, 0.72]) bolt(0.18, y, z, rear);

  const coupling = group(1.64, 3.02);
  cylinder(0.17, 0.98, silver, coupling);
  cylinder(0.38, 0.3, silver, coupling, -0.25);
  cylinder(0.37, 0.3, silver, coupling, 0.25);
  cylinder(0.35, 0.12, black, coupling);
  for (let i = 0; i < 6; i++) {
    const angle = i / 6 * Math.PI * 2;
    bolt(0.4, Math.cos(angle) * 0.26, Math.sin(angle) * 0.26, coupling);
  }

  const motor = group(3.15, 3.95);
  cylinder(0.75, 1.88, darkBlue, motor);
  cylinder(0.8, 0.17, edgeBlue, motor, -0.97);
  cylinder(0.81, 0.22, blue, motor, 1.0);
  for (let i = 0; i < 28; i++) {
    const angle = i / 28 * Math.PI * 2;
    const rib = box(1.72, 0.068, 0.11, blue, motor, 0, Math.cos(angle) * 0.785, Math.sin(angle) * 0.785);
    rib.rotation.x = angle;
  }
  box(0.81, 0.39, 0.8, blue, motor, -0.2, 1.0);
  box(0.84, 0.066, 0.83, edgeBlue, motor, -0.2, 1.24);
  for (const x of [-0.49, 0.07]) for (const z of [-0.28, 0.28]) bolt(x, 1.3, z, motor, "y");
  // Actual open spokes/grille over a dark fan recess, with a machined centre.
  cylinder(0.71, 0.018, black, motor, 1.126);
  ring(0.79, 0.68, 0.06, blue, motor, 1.16);
  for (let i = 0; i < 4; i++) {
    const g = mesh(new T.TorusGeometry(0.2 + i * 0.14, 0.013, 5, 40), blue, motor, 1.18);
    g.rotation.y = Math.PI / 2;
  }
  for (let i = 0; i < 12; i++) {
    const a = i / 12 * Math.PI * 2;
    const spoke = box(0.025, 1.41, 0.023, blue, motor, 1.185); spoke.rotation.x = a;
  }
  cylinder(0.17, 0.06, edgeBlue, motor, 1.21);
  for (const x of [-0.63, 0.64]) for (const z of [-0.49, 0.49]) box(0.32, 0.34, 0.26, blue, motor, x, -0.9, z);
  // Merge same-material solids per moving part, preserving individual rotor rigs.
  // This keeps the original detail while avoiding a draw call for every bolt/rib.
  for (const part of parts) if (part.mesh !== rotorPart) mergePartMeshes(T, part.mesh);
  for (const rotor of rotors.children) mergePartMeshes(T, rotor);
  return { assembly, parts, rotors };
}

function mergePartMeshes(T, part) {
  part.updateMatrixWorld(true);
  const inverse = part.matrixWorld.clone().invert(), groups = new Map();
  const originals = [];
  part.traverse((object) => {
    if (!object.isMesh || Array.isArray(object.material)) return;
    if (!groups.has(object.material)) groups.set(object.material, []);
    groups.get(object.material).push(object); originals.push(object);
  });
  for (const [material, objects] of groups) {
    const positions = [], normals = [], indices = [];
    for (const object of objects) {
      const geometry = object.geometry;
      const transform = new T.Matrix4().multiplyMatrices(inverse, object.matrixWorld);
      const normalTransform = new T.Matrix3().getNormalMatrix(transform);
      const source = geometry.getAttribute("position"), sourceNormal = geometry.getAttribute("normal");
      const offset = positions.length / 3, vertex = new T.Vector3(), normal = new T.Vector3();
      for (let i = 0; i < source.count; i++) {
        vertex.fromBufferAttribute(source, i).applyMatrix4(transform);
        positions.push(vertex.x, vertex.y, vertex.z);
        normal.fromBufferAttribute(sourceNormal, i).applyNormalMatrix(normalTransform);
        normals.push(normal.x, normal.y, normal.z);
      }
      if (geometry.index) for (let i = 0; i < geometry.index.count; i++) indices.push(geometry.index.getX(i) + offset);
      else for (let i = 0; i < source.count; i++) indices.push(i + offset);
    }
    const geometry = new T.BufferGeometry();
    geometry.setAttribute("position", new T.Float32BufferAttribute(positions, 3));
    geometry.setAttribute("normal", new T.Float32BufferAttribute(normals, 3));
    geometry.setIndex(indices); geometry.computeBoundingSphere();
    const merged = new T.Mesh(geometry, material); merged.castShadow = true; merged.receiveShadow = true;
    part.add(merged);
  }
  for (const object of originals) { object.removeFromParent(); object.geometry.dispose(); }
}

function roundedShape(T, width, height, radius, reverse = false) {
  const shape = reverse ? new T.Path() : new T.Shape();
  const x = -width / 2, y = -height / 2, r = radius;
  // Three triangulation handles the opposite orientation for the inner hole.
  shape.moveTo(x + r, y);
  shape.lineTo(x + width - r, y);
  shape.quadraticCurveTo(x + width, y, x + width, y + r);
  shape.lineTo(x + width, y + height - r);
  shape.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  shape.lineTo(x + r, y + height);
  shape.quadraticCurveTo(x, y + height, x, y + height - r);
  shape.lineTo(x, y + r);
  shape.quadraticCurveTo(x, y, x + r, y);
  shape.closePath();
  return shape;
}

function helicalRotor(T, length, direction) {
  const axial = 40, radial = 60, positions = [], indices = [];
  for (let i = 0; i <= axial; i++) {
    const t = i / axial, x = (t - 0.5) * length;
    for (let j = 0; j <= radial; j++) {
      const angle = j / radial * Math.PI * 2;
      const radius = 0.295 + 0.085 * Math.cos(3 * (angle - direction * t * 1.08));
      positions.push(x, Math.cos(angle) * radius, Math.sin(angle) * radius);
      if (i < axial && j < radial) {
        const a = i * (radial + 1) + j, b = a + radial + 1;
        indices.push(a, a + 1, b, b, a + 1, b + 1);
      }
    }
  }
  // Closed end faces, not hollow tube stand-ins.
  for (const end of [0, axial]) {
    const center = positions.length / 3;
    positions.push((end / axial - 0.5) * length, 0, 0);
    for (let j = 0; j < radial; j++) {
      const a = end * (radial + 1) + j;
      if (end === 0) indices.push(center, a, a + 1);
      else indices.push(center, a + 1, a);
    }
  }
  const geometry = new T.BufferGeometry();
  geometry.setAttribute("position", new T.Float32BufferAttribute(positions, 3));
  geometry.setIndex(indices); geometry.computeVertexNormals();
  return geometry;
}
