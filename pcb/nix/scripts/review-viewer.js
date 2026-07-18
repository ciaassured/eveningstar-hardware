import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/addons/libs/meshopt_decoder.module.js";

function disposeObject(object) {
  object.traverse((child) => {
    child.geometry?.dispose();
    const materials = Array.isArray(child.material) ? child.material : [child.material];
    materials.filter(Boolean).forEach((material) => {
      Object.values(material).forEach((value) => {
        if (value?.isTexture) value.dispose();
      });
      material.dispose();
    });
  });
}

export class HardwareViewer {
  constructor(container, onViewChange) {
    this.container = container;
    this.onViewChange = onViewChange;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xe9edf2);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.1;
    this.renderer.domElement.setAttribute("aria-label", "Interactive hardware comparison view");
    container.append(this.renderer.domElement);

    this.status = document.createElement("div");
    this.status.className = "viewer-status";
    container.append(this.status);

    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x627084, 2.1));
    const keyLight = new THREE.DirectionalLight(0xffffff, 3.2);
    keyLight.position.set(5, 8, 6);
    this.scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0xc9ddff, 1.4);
    fillLight.position.set(-5, 2, -4);
    this.scene.add(fillLight);

    this.camera = null;
    this.controls = null;
    this.content = null;
    this.kind = "model";
    this.bounds = null;
    this.initialState = null;
    this.loadSequence = 0;

    this.resizeObserver = new ResizeObserver(() => this.resize());
    this.resizeObserver.observe(container);
  }

  setStatus(message) {
    this.status.textContent = message;
    this.status.hidden = !message;
  }

  replaceCamera(camera, allowRotation) {
    this.controls?.dispose();
    this.camera = camera;
    if (camera.isPerspectiveCamera) {
      camera.aspect = Math.max(this.container.clientWidth, 1) / Math.max(this.container.clientHeight, 1);
      camera.updateProjectionMatrix();
    }
    this.controls = new OrbitControls(camera, this.renderer.domElement);
    this.controls.enableDamping = false;
    this.controls.screenSpacePanning = true;
    this.controls.enableRotate = allowRotation;
    if (!allowRotation) {
      this.controls.mouseButtons.LEFT = THREE.MOUSE.PAN;
      this.controls.mouseButtons.RIGHT = THREE.MOUSE.PAN;
      this.controls.touches.ONE = THREE.TOUCH.PAN;
      this.controls.touches.TWO = THREE.TOUCH.DOLLY_PAN;
    }
    this.controls.addEventListener("change", () => {
      this.render();
      this.onViewChange?.(this.getViewState());
    });
  }

  clearContent() {
    if (this.content) {
      this.scene.remove(this.content);
      disposeObject(this.content);
      this.content = null;
    }
  }

  async load(asset) {
    const sequence = ++this.loadSequence;
    this.setStatus("Loading…");
    this.clearContent();

    try {
      await this.loadModel(asset.url);
      if (sequence !== this.loadSequence) return;
      this.setStatus("");
      this.resize();
      this.initialState = this.getViewState();
      this.render();
    } catch (error) {
      if (sequence !== this.loadSequence) return;
      this.setStatus(`Could not load this view: ${error.message}`);
      throw error;
    }
  }

  async loadModel(url) {
    const gltf = await new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).loadAsync(url);
    this.content = gltf.scene;
    this.scene.add(this.content);
    this.bounds = new THREE.Box3().setFromObject(this.content);

    const size = this.bounds.getSize(new THREE.Vector3());
    const radius = Math.max(size.length() / 2, 0.001);
    const camera = new THREE.PerspectiveCamera(36, 1, radius / 100, radius * 100);
    this.replaceCamera(camera, true);
    this.controls.minDistance = radius * 0.08;
    this.controls.maxDistance = radius * 20;
    this.setPreset("isometric");
  }

  setPreset(preset) {
    if (!this.camera || !this.bounds) return;
    const center = this.bounds.getCenter(new THREE.Vector3());
    const size = this.bounds.getSize(new THREE.Vector3());
    const radius = Math.max(size.length() / 2, 0.001);
    const distance = radius / Math.sin(THREE.MathUtils.degToRad(this.camera.fov / 2)) * 1.05;
    const directions = {
      isometric: new THREE.Vector3(1, 0.85, 1),
      top: new THREE.Vector3(0, 1, 0.001),
      bottom: new THREE.Vector3(0, -1, 0.001),
      front: new THREE.Vector3(0, 0.12, 1),
      back: new THREE.Vector3(0, 0.12, -1),
    };
    const direction = (directions[preset] || directions.isometric).normalize();
    this.camera.position.copy(center).addScaledVector(direction, distance);
    this.camera.up.set(0, 1, 0);
    this.controls.target.copy(center);
    this.camera.lookAt(center);
    this.camera.updateProjectionMatrix();
    this.controls.update();
    this.render();
  }

  reset() {
    if (this.initialState) this.applyViewState(this.initialState);
  }

  getViewState() {
    if (!this.camera || !this.controls) return null;
    return {
      kind: this.kind,
      position: this.camera.position.toArray(),
      quaternion: this.camera.quaternion.toArray(),
      zoom: this.camera.zoom,
      target: this.controls.target.toArray(),
    };
  }

  applyViewState(state) {
    if (!state || state.kind !== this.kind || !this.camera || !this.controls) return;
    this.camera.position.fromArray(state.position);
    this.camera.quaternion.fromArray(state.quaternion);
    this.camera.zoom = state.zoom;
    this.controls.target.fromArray(state.target);
    this.camera.updateProjectionMatrix();
    this.controls.update();
    this.render();
  }

  resize() {
    const width = Math.max(this.container.clientWidth, 1);
    const height = Math.max(this.container.clientHeight, 1);
    this.renderer.setSize(width, height, false);
    if (!this.camera) return;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.render();
  }

  render() {
    if (this.camera) this.renderer.render(this.scene, this.camera);
  }
}

class DocumentViewer {
  constructor(container, onViewChange) {
    this.container = container;
    this.onViewChange = onViewChange;
    this.image = new Image();
    this.image.className = "native-document";
    this.image.alt = "";
    this.image.draggable = false;
    container.append(this.image);

    this.status = document.createElement("div");
    this.status.className = "viewer-status";
    container.append(this.status);

    this.zoom = 1;
    this.panX = 0;
    this.panY = 0;
    this.naturalWidth = 1;
    this.naturalHeight = 1;
    this.loadSequence = 0;
    this.drag = null;

    container.addEventListener("wheel", (event) => this.onWheel(event), { passive: false });
    container.addEventListener("pointerdown", (event) => this.onPointerDown(event));
    container.addEventListener("pointermove", (event) => this.onPointerMove(event));
    container.addEventListener("pointerup", (event) => this.onPointerUp(event));
    container.addEventListener("pointercancel", (event) => this.onPointerUp(event));
    this.resizeObserver = new ResizeObserver(() => this.render());
    this.resizeObserver.observe(container);
  }

  setStatus(message) {
    this.status.textContent = message;
    this.status.hidden = !message;
  }

  async load(asset) {
    const sequence = ++this.loadSequence;
    this.setStatus("Loading…");
    try {
      await new Promise((resolve, reject) => {
        this.image.onload = resolve;
        this.image.onerror = () => reject(new Error("document could not be loaded"));
        this.image.src = asset.url;
      });
      if (sequence !== this.loadSequence) return;
      this.naturalWidth = this.image.naturalWidth || 1;
      this.naturalHeight = this.image.naturalHeight || 1;
      this.setStatus("");
      this.reset();
    } catch (error) {
      if (sequence !== this.loadSequence) return;
      this.setStatus(`Could not load this view: ${error.message}`);
      throw error;
    }
  }

  onWheel(event) {
    event.preventDefault();
    const bounds = this.container.getBoundingClientRect();
    const cursorX = event.clientX - bounds.left - bounds.width / 2;
    const cursorY = event.clientY - bounds.top - bounds.height / 2;
    const previousZoom = this.zoom;
    this.zoom = THREE.MathUtils.clamp(this.zoom * Math.exp(-event.deltaY * 0.0015), 0.1, 40);
    const ratio = this.zoom / previousZoom;
    this.panX = cursorX - (cursorX - this.panX) * ratio;
    this.panY = cursorY - (cursorY - this.panY) * ratio;
    this.changed();
  }

  onPointerDown(event) {
    if (event.button !== 0) return;
    this.drag = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
    this.container.setPointerCapture(event.pointerId);
    this.container.classList.add("dragging");
  }

  onPointerMove(event) {
    if (!this.drag || this.drag.pointerId !== event.pointerId) return;
    this.panX += event.clientX - this.drag.x;
    this.panY += event.clientY - this.drag.y;
    this.drag.x = event.clientX;
    this.drag.y = event.clientY;
    this.changed();
  }

  onPointerUp(event) {
    if (!this.drag || this.drag.pointerId !== event.pointerId) return;
    this.drag = null;
    this.container.classList.remove("dragging");
    if (this.container.hasPointerCapture(event.pointerId)) this.container.releasePointerCapture(event.pointerId);
  }

  changed() {
    this.render();
    this.onViewChange?.(this.getViewState());
  }

  reset() {
    this.zoom = 1;
    this.panX = 0;
    this.panY = 0;
    this.render();
  }

  getViewState() {
    return { kind: "document", scale: this.fitScale() * this.zoom, panX: this.panX, panY: this.panY };
  }

  applyViewState(state) {
    if (!state || state.kind !== "document") return;
    this.zoom = state.scale / this.fitScale();
    this.panX = state.panX;
    this.panY = state.panY;
    this.render();
  }

  resize() {
    this.render();
  }

  setPreset() {}

  fitScale() {
    const width = Math.max(this.container.clientWidth, 1);
    const height = Math.max(this.container.clientHeight, 1);
    return Math.min(width / this.naturalWidth, height / this.naturalHeight) * 0.98;
  }

  render() {
    if (!this.image.complete) return;
    const fit = this.fitScale();
    this.image.style.width = `${this.naturalWidth * fit * this.zoom}px`;
    this.image.style.height = `${this.naturalHeight * fit * this.zoom}px`;
    this.image.style.transform = `translate(-50%, -50%) translate(${this.panX}px, ${this.panY}px)`;
  }
}

class ReviewViewer {
  constructor(container, onViewChange) {
    this.container = container;
    this.onViewChange = onViewChange;
    this.active = null;
    this.documentHost = document.createElement("div");
    this.documentHost.className = "renderer-host document-host";
    this.modelHost = document.createElement("div");
    this.modelHost.className = "renderer-host model-host";
    container.append(this.documentHost, this.modelHost);
    this.documentViewer = new DocumentViewer(this.documentHost, (state) => {
      if (this.active === this.documentViewer) onViewChange(state);
    });
    this.modelViewer = null;
  }

  async load(asset) {
    if (asset.kind === "model" && !this.modelViewer) {
      this.modelViewer = new HardwareViewer(this.modelHost, (state) => {
        if (this.active === this.modelViewer) this.onViewChange(state);
      });
    }
    this.active = asset.kind === "model" ? this.modelViewer : this.documentViewer;
    this.documentHost.hidden = this.active !== this.documentViewer;
    this.modelHost.hidden = this.active !== this.modelViewer;
    this.resize();
    await this.active.load(asset);
  }

  getViewState() {
    return this.active?.getViewState() || null;
  }

  applyViewState(state) {
    this.active?.applyViewState(state);
  }

  reset() {
    this.active?.reset();
  }

  resize() {
    this.active?.resize();
  }

  setPreset(preset) {
    this.active?.setPreset(preset);
  }
}

export function mountReview(review) {
  const style = document.createElement("style");
  style.textContent = `
    :root {
      color-scheme: dark;
      font-family: Inter, ui-sans-serif, system-ui, sans-serif;
      --bg: #111318; --panel: #1b1f27; --line: #343b49;
      --text: #eef1f6; --muted: #aab2c0;
      --destination: #ffb454; --source: #5de4c7;
    }
    * { box-sizing: border-box; }
    [hidden] { display: none !important; }
    html, body { width: 100%; height: 100%; overflow: hidden; }
    body { margin: 0; background: var(--bg); color: var(--text); }
    main { position: relative; width: 100%; height: 100%; }
    .toolbar {
      position: absolute; z-index: 10; top: 12px; left: 50%; translate: -50% 0;
      display: flex; gap: 6px; align-items: center; flex-wrap: wrap;
      max-width: calc(100% - 24px); padding: 6px;
      border: 1px solid #ffffff24; border-radius: 11px;
      background: #111318b8; box-shadow: 0 4px 20px #0006;
      backdrop-filter: blur(12px); opacity: .72; transition: opacity .15s, background .15s;
    }
    .toolbar:hover, .toolbar:focus-within { opacity: 1; background: #111318f2; }
    select, button { border: 1px solid var(--line); border-radius: 7px; background: #1b1f27e6; color: var(--text); padding: 8px 10px; font: inherit; }
    button { cursor: pointer; }
    button:hover { border-color: var(--source); }
    button, .camera-control, .checkbox { display: inline-flex; align-items: center; gap: 7px; }
    kbd { min-width: 1.45em; padding: 2px 5px; border: 1px solid #ffffff2c; border-radius: 4px; background: #ffffff12; color: var(--muted); font: 600 .7rem ui-monospace, monospace; text-align: center; }
    .checkbox { display: flex; align-items: center; gap: 6px; padding: 7px 3px; color: var(--muted); font-size: .82rem; font-weight: 650; white-space: nowrap; }
    .checkbox input { accent-color: var(--source); }
    .mode-panel { position: relative; min-width: 155px; height: 34px; border: 1px solid #ffffff24; border-radius: 7px; background: #1b1f27e6; }
    .mode-heading { display: flex; height: 100%; align-items: center; justify-content: space-between; gap: 8px; padding: 5px 8px 5px 10px; font-size: .82rem; font-weight: 650; }
    .mode-list { position: absolute; top: calc(100% + 5px); left: -1px; width: calc(100% + 2px); padding: 5px; border: 1px solid #ffffff24; border-radius: 8px; background: #111318f2; box-shadow: 0 4px 20px #0006; opacity: 0; pointer-events: none; translate: 0 -4px; transition: opacity .12s, translate .12s; }
    .mode-panel:hover .mode-list, .mode-panel:focus-within .mode-list { opacity: 1; pointer-events: auto; translate: 0 0; }
    .mode-list button { display: block; width: 100%; margin: 2px 0; border-color: transparent; background: transparent; padding: 7px 8px; color: var(--muted); font-size: .8rem; text-align: left; }
    .mode-list button:hover { background: #ffffff10; color: var(--text); }
    .mode-list button[aria-selected="true"] { border-color: var(--source); background: #5de4c71b; color: var(--source); }
    .view-panel {
      position: absolute; z-index: 9; top: 12px; left: 12px;
      width: min(290px, calc(100% - 24px)); height: 42px; overflow: hidden;
      border: 1px solid #ffffff24; border-radius: 11px;
      background: #111318b8; box-shadow: 0 4px 20px #0006;
      backdrop-filter: blur(12px); opacity: .62; transition: height .18s, opacity .15s, background .15s;
    }
    .view-panel:hover, .view-panel:focus-within { height: calc(100% - 60px); opacity: 1; background: #111318f2; }
    .view-heading { display: flex; align-items: center; justify-content: space-between; padding: 9px 10px 7px; color: var(--muted); font-size: .75rem; font-weight: 750; letter-spacing: .08em; text-transform: uppercase; }
    .current-view { min-width: 0; overflow: hidden; color: var(--text); text-overflow: ellipsis; white-space: nowrap; }
    .view-list { height: calc(100% - 38px); overflow-y: auto; padding: 0 6px 7px; opacity: 0; pointer-events: none; scrollbar-width: thin; transition: opacity .12s; }
    .view-panel:hover .view-list, .view-panel:focus-within .view-list { opacity: 1; pointer-events: auto; }
    .view-list button { display: block; width: 100%; margin: 2px 0; overflow: hidden; border-color: transparent; background: transparent; color: var(--muted); padding: 7px 8px; font-size: .8rem; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
    .view-list button:hover { background: #ffffff10; color: var(--text); }
    .view-list button[aria-selected="true"] { border-color: var(--source); background: #5de4c71b; color: var(--source); }
    .labels { position: absolute; z-index: 7; left: 14px; right: 14px; bottom: 38px; display: flex; justify-content: space-between; gap: 16px; font-size: .8rem; font-weight: 700; pointer-events: none; }
    .labels span { max-width: 46%; overflow: hidden; padding: 5px 8px; border-radius: 6px; background: #111318b8; backdrop-filter: blur(8px); text-overflow: ellipsis; white-space: nowrap; }
    .destination-label { color: var(--destination); }
    .source-label { color: var(--source); text-align: right; }
    .stage { position: absolute; inset: 0; overflow: hidden; background: #e9edf2; }
    .viewer-pane { position: absolute; inset: 0; min-width: 0; overflow: hidden; background: #e9edf2; }
    .renderer-host { position: absolute; inset: 0; overflow: hidden; background: #e9edf2; touch-action: none; cursor: grab; }
    .renderer-host.dragging { cursor: grabbing; }
    .native-document { position: absolute; top: 50%; left: 50%; max-width: none; max-height: none; user-select: none; pointer-events: none; transform-origin: center; }
    .viewer-pane canvas { display: block; width: 100%; height: 100%; touch-action: none; }
    .source-layer { position: absolute; inset: 0; overflow: hidden; clip-path: inset(0 50% 0 0); }
    .source-layer .viewer-pane { position: absolute; inset: 0; }
    .divider { position: absolute; z-index: 4; top: 0; bottom: 0; left: 50%; width: 2px; background: var(--source); box-shadow: 0 0 0 1px #0008; pointer-events: none; }
    .viewer-status { position: absolute; z-index: 3; inset: 50% auto auto 50%; translate: -50% -50%; padding: 8px 11px; border-radius: 7px; background: #111318d9; color: var(--text); font-size: .86rem; pointer-events: none; }
    .stage.side-by-side { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--line); }
    .stage.side-by-side > .viewer-pane, .stage.side-by-side > .source-layer { position: relative; inset: auto; clip-path: none !important; }
    .stage.side-by-side .divider { display: none; }
    .stage.diff .source-layer { mix-blend-mode: difference; }
    .stage.highlight { filter: contrast(2.4) saturate(3); }
    .stage.highlight .source-layer { mix-blend-mode: difference; opacity: .72; }
    .slider { position: absolute; z-index: 8; left: 14px; bottom: 12px; width: calc(100% - 28px); margin: 0; accent-color: var(--source); opacity: .7; transition: opacity .15s; }
    .slider:hover, .slider:focus { opacity: 1; }
    @media (max-width: 800px) {
      .toolbar { left: 8px; right: 8px; translate: 0 0; max-width: none; }
      .view-panel { top: 68px; width: min(250px, calc(100% - 24px)); }
      .view-panel:hover, .view-panel:focus-within { height: calc(100% - 116px); }
      .stage.side-by-side { grid-template-columns: 1fr; grid-template-rows: 1fr 1fr; }
    }
  `;
  document.head.append(style);
  document.body.innerHTML = `
    <main>
      <div class="toolbar">
        <div class="mode-panel" aria-label="Comparison mode">
          <div class="mode-heading"><span id="current-mode"></span><span><kbd>←</kbd> <kbd>→</kbd></span></div>
          <div class="mode-list" id="mode-list" role="listbox"></div>
        </div>
        <span class="camera-control" id="camera-control" hidden><select id="orientation" aria-label="3D camera"><option value="isometric">Isometric</option><option value="top">Top</option><option value="bottom">Bottom</option><option value="front">Front</option><option value="back">Back</option></select><kbd>1–5</kbd></span>
        <label class="checkbox"><input id="sync" type="checkbox" checked disabled>Sync <kbd>S</kbd></label>
        <button id="reset" type="button">Fit <kbd>F</kbd></button>
        <button id="flip" type="button"><span id="flip-label">Source</span><kbd>Space</kbd></button>
      </div>
      <aside class="view-panel" aria-label="Review views">
        <div class="view-heading"><span class="current-view" id="current-view"></span><span><kbd>↑</kbd> <kbd>↓</kbd></span></div>
        <div class="view-list" id="asset-list" role="listbox"></div>
      </aside>
      <div class="labels">
        <span class="destination-label" id="destination-label"></span>
        <span class="source-label" id="source-label"></span>
      </div>
      <div class="stage" id="stage">
        <div class="viewer-pane" id="destination-viewer"></div>
        <div class="source-layer" id="source-layer"><div class="viewer-pane" id="source-viewer"></div></div>
        <div class="divider" id="divider"></div>
      </div>
      <input class="slider" id="slider" type="range" min="0" max="100" value="50" aria-label="Comparison split">
    </main>
  `;

  const assetList = document.querySelector("#asset-list");
  const currentView = document.querySelector("#current-view");
  const modeList = document.querySelector("#mode-list");
  const currentMode = document.querySelector("#current-mode");
  const orientationSelect = document.querySelector("#orientation");
  const cameraControl = document.querySelector("#camera-control");
  const syncCheckbox = document.querySelector("#sync");
  const sourceLayer = document.querySelector("#source-layer");
  const divider = document.querySelector("#divider");
  const stage = document.querySelector("#stage");
  const slider = document.querySelector("#slider");
  const flip = document.querySelector("#flip");
  const flipLabel = document.querySelector("#flip-label");
  const reset = document.querySelector("#reset");
  let showingSource = false;
  let synchronizing = false;
  let assetSequence = 0;
  let activeAssetIndex = 0;
  let activeModeIndex = 0;

  document.querySelector("#destination-label").textContent = review.destinationLabel;
  document.querySelector("#source-label").textContent = review.sourceLabel;
  const viewButtons = review.assets.map((asset, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.id = `review-view-${index}`;
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", "false");
    button.textContent = asset.name;
    button.title = asset.name;
    button.addEventListener("click", () => setActiveAsset(index));
    assetList.append(button);
    return button;
  });
  const modes = [
    { id: "overlay", name: "Overlay / reveal" },
    { id: "side-by-side", name: "Side by side" },
    { id: "diff", name: "Diff" },
    { id: "highlight", name: "Highlight changes" },
  ];
  const modeButtons = modes.map((mode, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.id = `review-mode-${mode.id}`;
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", "false");
    button.textContent = mode.name;
    button.addEventListener("click", () => setMode(index));
    modeList.append(button);
    return button;
  });
  const activeMode = () => modes[activeModeIndex].id;
  const navigationIsSynchronized = () => activeMode() !== "side-by-side" || syncCheckbox.checked;
  let destinationViewer;
  let sourceViewer;
  destinationViewer = new ReviewViewer(
    document.querySelector("#destination-viewer"),
    (state) => synchronize(sourceViewer, state),
  );
  sourceViewer = new ReviewViewer(
    document.querySelector("#source-viewer"),
    (state) => synchronize(destinationViewer, state),
  );

  function synchronize(target, state) {
    if (synchronizing || !navigationIsSynchronized() || !state) return;
    synchronizing = true;
    target.applyViewState(state);
    synchronizing = false;
  }

  async function chooseAsset() {
    const sequence = ++assetSequence;
    const asset = review.assets[activeAssetIndex];
    cameraControl.hidden = asset.kind !== "model";
    document.title = `${asset.name} · EveningStar review`;
    try {
      await Promise.all([
        destinationViewer.load({ kind: asset.kind, url: asset.destination }),
        sourceViewer.load({ kind: asset.kind, url: asset.source }),
      ]);
      if (sequence === assetSequence && navigationIsSynchronized()) {
        sourceViewer.applyViewState(destinationViewer.getViewState());
      }
    } catch (error) {
      console.error(error);
    }
  }

  function setSplit(value) {
    const split = Number(value);
    if (activeMode() === "overlay") sourceLayer.style.clipPath = `inset(0 ${100 - split}% 0 0)`;
    divider.style.left = `${split}%`;
    slider.value = split;
  }

  function flipSide() {
    if (activeMode() !== "overlay") return;
    showingSource = !showingSource;
    setSplit(showingSource ? 100 : 0);
    flipLabel.textContent = showingSource ? "Destination" : "Source";
  }

  function setMode(index) {
    activeModeIndex = (index + modes.length) % modes.length;
    const mode = activeMode();
    const sideBySide = mode === "side-by-side";
    stage.classList.toggle("side-by-side", sideBySide);
    stage.classList.toggle("diff", mode === "diff");
    stage.classList.toggle("highlight", mode === "highlight");
    currentMode.textContent = modes[activeModeIndex].name;
    modeButtons.forEach((button, buttonIndex) => button.setAttribute("aria-selected", String(buttonIndex === activeModeIndex)));
    modeList.setAttribute("aria-activedescendant", modeButtons[activeModeIndex].id);
    sourceLayer.style.clipPath = mode === "overlay" ? `inset(0 ${100 - Number(slider.value)}% 0 0)` : "none";
    divider.hidden = mode !== "overlay";
    slider.hidden = mode !== "overlay";
    flip.hidden = mode !== "overlay";
    syncCheckbox.disabled = !sideBySide;
    if (!sideBySide) syncCheckbox.checked = true;
    if (!sideBySide) sourceViewer.applyViewState(destinationViewer.getViewState());
    requestAnimationFrame(() => {
      destinationViewer.resize();
      sourceViewer.resize();
      if (navigationIsSynchronized()) sourceViewer.applyViewState(destinationViewer.getViewState());
    });
  }

  function moveView(delta) {
    const count = review.assets.length;
    setActiveAsset((activeAssetIndex + delta + count) % count);
  }

  function moveMode(delta) {
    setMode(activeModeIndex + delta);
  }

  function setActiveAsset(index, load = true) {
    activeAssetIndex = index;
    currentView.textContent = review.assets[index].name;
    currentView.title = review.assets[index].name;
    viewButtons.forEach((button, buttonIndex) => button.setAttribute("aria-selected", String(buttonIndex === index)));
    assetList.setAttribute("aria-activedescendant", viewButtons[index].id);
    viewButtons[index].scrollIntoView({ block: "nearest" });
    if (load) chooseAsset();
  }

  function fitViews() {
    destinationViewer.reset();
    sourceViewer.reset();
    if (navigationIsSynchronized()) sourceViewer.applyViewState(destinationViewer.getViewState());
  }

  syncCheckbox.addEventListener("change", () => {
    if (syncCheckbox.checked) sourceViewer.applyViewState(destinationViewer.getViewState());
  });
  orientationSelect.addEventListener("change", () => {
    destinationViewer.setPreset(orientationSelect.value);
    sourceViewer.setPreset(orientationSelect.value);
    if (navigationIsSynchronized()) sourceViewer.applyViewState(destinationViewer.getViewState());
  });
  slider.addEventListener("input", (event) => {
    showingSource = Number(event.target.value) > 50;
    setSplit(event.target.value);
  });
  flip.addEventListener("click", flipSide);
  reset.addEventListener("click", fitViews);
  window.addEventListener("keydown", (event) => {
    const editing = ["INPUT", "SELECT"].includes(event.target.tagName);
    if (editing || (event.target.tagName === "BUTTON" && [" ", "Enter"].includes(event.key))) return;
    if (event.key === "ArrowUp" || event.key === "ArrowDown") {
      event.preventDefault();
      moveView(event.key === "ArrowUp" ? -1 : 1);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      moveMode(event.key === "ArrowLeft" ? -1 : 1);
    } else if (event.key.toLowerCase() === "s" && activeMode() === "side-by-side") {
      syncCheckbox.checked = !syncCheckbox.checked;
      if (syncCheckbox.checked) sourceViewer.applyViewState(destinationViewer.getViewState());
    } else if (event.key.toLowerCase() === "f") {
      fitViews();
    } else if (/^[1-5]$/.test(event.key) && !cameraControl.hidden) {
      orientationSelect.selectedIndex = Number(event.key) - 1;
      orientationSelect.dispatchEvent(new Event("change"));
    } else if (event.key === " " && activeMode() === "overlay") {
      event.preventDefault();
      flipSide();
    }
  });

  const parameters = new URLSearchParams(window.location.search);
  const requestedView = parameters.get("view");
  const requestedIndex = review.assets.findIndex((asset) =>
    asset.path === requestedView || (requestedView === "3d" && asset.kind === "model"),
  );
  setActiveAsset(requestedIndex >= 0 ? requestedIndex : 0, false);
  setSplit(50);
  const requestedMode = parameters.get("mode") || (parameters.get("layout") === "side-by-side" ? "side-by-side" : "overlay");
  setMode(Math.max(0, modes.findIndex((mode) => mode.id === requestedMode)));
  chooseAsset();
}
