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

function prepareModelMaterials(object) {
  const adjusted = new Set();
  object.traverse((child) => {
    const materials = Array.isArray(child.material) ? child.material : [child.material];
    materials.filter(Boolean).forEach((material) => {
      if (adjusted.has(material) || !material.isMeshStandardMaterial) return;
      adjusted.add(material);
      if (material.transparent && material.opacity >= 0.95 && material.roughness >= 0.75) {
        material.color.setRGB(0.008, 0.04, 0.015);
        material.opacity = 1;
        material.transparent = false;
        material.depthWrite = true;
        material.needsUpdate = true;
      }
      if (
        material.transparent
        && material.opacity >= 0.89
        && material.opacity <= 0.91
        && Math.min(material.color.r, material.color.g, material.color.b) > 0.9
      ) {
        material.userData.reviewLayer = "silkscreen";
        material.side = THREE.FrontSide;
        material.color.setRGB(0, 0, 0);
        material.emissive.setRGB(1, 1, 1);
        material.emissiveIntensity = 0.8;
        material.depthWrite = false;
        material.polygonOffset = true;
        material.polygonOffsetFactor = -2;
        material.polygonOffsetUnits = -2;
        material.needsUpdate = true;
      }
      if (
        material.transparent
        && material.opacity >= 0.8
        && material.opacity < 0.9
        && material.color.g > material.color.r
        && material.color.g > material.color.b
      ) {
        material.userData.reviewLayer = "soldermask";
        material.color.multiplyScalar(0.4);
        material.opacity = 0.74;
        material.depthWrite = false;
      }
      const peak = Math.max(material.color.r, material.color.g, material.color.b);
      const minimumPeak = 0.05;
      if (peak >= minimumPeak) return;
      if (peak > 0.0001) material.color.multiplyScalar(minimumPeak / peak);
      else material.color.setRGB(minimumPeak, minimumPeak, minimumPeak);
    });
    const layers = materials.filter(Boolean).map((material) => material.userData.reviewLayer);
    if (layers.includes("soldermask")) child.renderOrder = 1;
    if (layers.includes("silkscreen")) child.renderOrder = 2;
  });
}

export class HardwareViewer {
  constructor(container, onViewChange) {
    this.container = container;
    this.onViewChange = onViewChange;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xc4c7d6);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.AgXToneMapping;
    this.renderer.toneMappingExposure = 0.9;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.domElement.setAttribute("aria-label", "Interactive hardware comparison view");
    this.renderer.domElement.draggable = false;
    container.append(this.renderer.domElement);

    this.status = document.createElement("div");
    this.status.className = "viewer-status";
    container.append(this.status);

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
    if (this.camera) this.scene.remove(this.camera);
    this.camera = camera;
    this.updateProjection(camera);
    const lightTarget = new THREE.Object3D();
    lightTarget.position.set(0, 0, -1);
    const headlight = new THREE.DirectionalLight(0xffffff, 0.45);
    headlight.position.set(0, 0.4, 0.8);
    headlight.target = lightTarget;
    const sideKey = new THREE.DirectionalLight(0xfff3e6, 8.0);
    sideKey.position.set(2.2, 1.4, 0.75);
    sideKey.target = lightTarget;
    sideKey.castShadow = true;
    sideKey.shadow.mapSize.set(2048, 2048);
    this.shadowLight = sideKey;
    const cameraFill = new THREE.DirectionalLight(0xdde8ff, 3.0);
    cameraFill.position.set(-2, -1, 0.45);
    cameraFill.target = lightTarget;
    camera.add(headlight, sideKey, cameraFill, lightTarget);
    this.scene.add(camera);
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
    prepareModelMaterials(this.content);
    this.content.traverse((child) => {
      if (!child.isMesh) return;
      child.castShadow = true;
      child.receiveShadow = true;
    });
    this.scene.add(this.content);
    this.bounds = new THREE.Box3().setFromObject(this.content);

    const size = this.bounds.getSize(new THREE.Vector3());
    const radius = Math.max(size.length() / 2, 0.001);
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, radius / 100, radius * 20);
    camera.userData.fitRadius = radius;
    this.replaceCamera(camera, true);
    const shadowExtent = radius * 1.5;
    this.shadowLight.shadow.camera.left = -shadowExtent;
    this.shadowLight.shadow.camera.right = shadowExtent;
    this.shadowLight.shadow.camera.top = shadowExtent;
    this.shadowLight.shadow.camera.bottom = -shadowExtent;
    this.shadowLight.shadow.camera.near = Math.max(radius / 100, 0.001);
    this.shadowLight.shadow.camera.far = Math.max(radius * 12, 10);
    this.shadowLight.shadow.normalBias = radius * 0.001;
    this.shadowLight.shadow.camera.updateProjectionMatrix();
    this.controls.minDistance = radius * 0.08;
    this.controls.maxDistance = radius * 20;
    this.setPreset("isometric");
  }

  setPreset(preset) {
    if (!this.camera || !this.bounds) return;
    const directions = {
      isometric: new THREE.Vector3(1, 1, 1),
      top: new THREE.Vector3(0, 1, 0.001),
      bottom: new THREE.Vector3(0, -1, 0.001),
      front: new THREE.Vector3(0, 0.12, 1),
      back: new THREE.Vector3(0, 0.12, -1),
    };
    this.setDirection(directions[preset] || directions.isometric);
  }

  setOrbit(azimuth, elevation) {
    const phi = THREE.MathUtils.degToRad(90 - elevation);
    const theta = THREE.MathUtils.degToRad(azimuth);
    this.setDirection(new THREE.Vector3().setFromSphericalCoords(1, phi, theta));
  }

  setDirection(direction) {
    if (!this.camera || !this.bounds) return;
    const center = this.bounds.getCenter(new THREE.Vector3());
    const size = this.bounds.getSize(new THREE.Vector3());
    const radius = Math.max(size.length() / 2, 0.001);
    const distance = this.camera.isPerspectiveCamera
      ? radius / Math.sin(THREE.MathUtils.degToRad(this.camera.fov / 2)) * 1.05
      : radius * 4;
    this.camera.position.copy(center).addScaledVector(direction.clone().normalize(), distance);
    this.camera.up.set(0, 1, 0);
    this.controls.target.copy(center);
    this.camera.lookAt(center);
    this.camera.updateProjectionMatrix();
    this.controls.update();
    this.render();
  }

  setZoom(zoom) {
    if (!this.camera) return;
    this.camera.zoom = THREE.MathUtils.clamp(zoom, 0.1, 10);
    this.camera.updateProjectionMatrix();
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
    this.updateProjection(this.camera, width, height);
    this.render();
  }

  updateProjection(
    camera,
    width = Math.max(this.container.clientWidth, 1),
    height = Math.max(this.container.clientHeight, 1),
  ) {
    const aspect = width / height;
    if (camera.isPerspectiveCamera) {
      camera.aspect = aspect;
    } else if (camera.isOrthographicCamera) {
      const radius = camera.userData.fitRadius || 1;
      const halfHeight = radius * 1.05 * Math.max(1, 1 / aspect);
      camera.left = -halfHeight * aspect;
      camera.right = halfHeight * aspect;
      camera.top = halfHeight;
      camera.bottom = -halfHeight;
    }
    camera.updateProjectionMatrix();
  }

  render() {
    if (this.camera) this.renderer.render(this.scene, this.camera);
  }

  drawTo(context, width, height) {
    if (!this.camera) return false;
    this.render();
    context.drawImage(this.renderer.domElement, 0, 0, width, height);
    return true;
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

  setOrbit() {}

  setZoom() {}

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

  drawTo(context, width, height) {
    if (!this.image.complete) return false;
    const hostWidth = Math.max(this.container.clientWidth, 1);
    const hostHeight = Math.max(this.container.clientHeight, 1);
    const fit = this.fitScale();
    const renderedWidth = this.naturalWidth * fit * this.zoom;
    const renderedHeight = this.naturalHeight * fit * this.zoom;
    const scaleX = width / hostWidth;
    const scaleY = height / hostHeight;
    const left = hostWidth / 2 + this.panX - renderedWidth / 2;
    const top = hostHeight / 2 + this.panY - renderedHeight / 2;
    context.drawImage(
      this.image,
      left * scaleX,
      top * scaleY,
      renderedWidth * scaleX,
      renderedHeight * scaleY,
    );
    return true;
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

  setOrbit(azimuth, elevation) {
    this.active?.setOrbit(azimuth, elevation);
  }

  setZoom(zoom) {
    this.active?.setZoom(zoom);
  }

  drawTo(context, width, height) {
    return this.active?.drawTo(context, width, height) || false;
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
    main, main * { user-select: none; -webkit-user-select: none; }
    main img, main canvas { -webkit-user-drag: none; }
    .toolbar {
      position: absolute; z-index: 10; top: 12px; left: 50%; translate: -50% 0;
      display: flex; gap: 6px; align-items: center; flex-wrap: nowrap; white-space: nowrap;
      max-width: calc(100% - 24px); padding: 6px;
      border: 1px solid #ffffff24; border-radius: 11px;
      background: #111318b8; box-shadow: 0 4px 20px #0006;
      backdrop-filter: blur(12px); opacity: .72; transition: opacity .15s, background .15s;
    }
    .toolbar:hover, .toolbar:focus-within { opacity: 1; background: #111318f2; }
    select, button { border: 1px solid var(--line); border-radius: 7px; background: #1b1f27e6; color: var(--text); padding: 8px 10px; font: inherit; }
    button { cursor: pointer; }
    button:hover { border-color: var(--source); }
    button:disabled, select:disabled { border-color: var(--line); opacity: .36; cursor: default; }
    button, .camera-control, .checkbox { display: inline-flex; align-items: center; gap: 7px; }
    kbd { min-width: 1.45em; padding: 2px 5px; border: 1px solid #ffffff2c; border-radius: 4px; background: #ffffff12; color: var(--muted); font: 600 .7rem ui-monospace, monospace; text-align: center; }
    .checkbox { display: flex; align-items: center; gap: 6px; padding: 7px 3px; color: var(--muted); font-size: .82rem; font-weight: 650; white-space: nowrap; }
    .checkbox input { accent-color: var(--source); }
    .checkbox:has(input:disabled) { opacity: .36; }
    .picker-panel { position: relative; height: 34px; border: 1px solid #ffffff24; border-radius: 7px; background: #1b1f27e6; }
    .view-picker { min-width: 142px; }
    .mode-picker { min-width: 155px; }
    .picker-heading { display: flex; height: 100%; align-items: center; justify-content: space-between; gap: 8px; padding: 5px 8px 5px 10px; font-size: .82rem; font-weight: 650; }
    .current-view { min-width: 0; overflow: hidden; color: var(--text); text-overflow: ellipsis; white-space: nowrap; }
    .picker-list { position: absolute; top: calc(100% + 5px); left: -1px; width: calc(100% + 2px); padding: 5px; border: 1px solid #ffffff24; border-radius: 8px; background: #111318f2; box-shadow: 0 4px 20px #0006; opacity: 0; pointer-events: none; translate: 0 -4px; transition: opacity .12s, translate .12s; }
    .picker-list::before { content: ""; position: absolute; left: -1px; right: -1px; top: -7px; height: 7px; }
    .picker-panel:hover .picker-list, .picker-panel:focus-within .picker-list { opacity: 1; pointer-events: auto; translate: 0 0; }
    .picker-list button { display: block; width: 100%; margin: 2px 0; overflow: hidden; border-color: transparent; background: transparent; padding: 7px 8px; color: var(--muted); font-size: .8rem; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
    .picker-list button:hover { background: #ffffff10; color: var(--text); }
    .picker-list button[aria-selected="true"] { border-color: var(--source); background: #5de4c71b; color: var(--source); }
    .context-toolbar {
      position: absolute; z-index: 9; bottom: 10px; left: 50%; translate: -50% 0;
      display: flex; align-items: center; gap: 6px; max-width: calc(100% - 24px); padding: 6px;
      border: 1px solid #ffffff24; border-radius: 10px; background: #111318b8;
      box-shadow: 0 4px 20px #0005; backdrop-filter: blur(12px); opacity: .66;
      transition: opacity .15s, background .15s;
    }
    .context-toolbar:hover, .context-toolbar:focus-within { opacity: 1; background: #111318f2; }
    .context-label { padding: 0 3px 0 5px; color: var(--muted); font-size: .72rem; font-weight: 750; letter-spacing: .07em; text-transform: uppercase; }
    .context-assets { display: inline-flex; align-items: center; gap: 6px; }
    .context-assets select { min-width: 180px; max-width: min(360px, 55vw); }
    .context-assets button { padding: 7px 8px; }
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
    .comparison-overlay { position: absolute; z-index: 3; inset: 0; display: none; width: 100%; height: 100%; pointer-events: none; }
    .stage.diff .source-layer, .stage.highlight .source-layer { visibility: hidden; }
    .stage.diff .comparison-overlay { display: block; background: #000; }
    .stage.highlight .comparison-overlay { display: block; filter: drop-shadow(0 0 2px #ff2bd6) drop-shadow(0 0 7px #ff2bd6); }
    .slider { position: absolute; z-index: 8; left: 14px; bottom: 70px; width: calc(100% - 28px); height: 18px; margin: 0; appearance: none; background: transparent; opacity: .7; transition: opacity .15s; }
    .slider::-webkit-slider-runnable-track { height: 3px; border-radius: 2px; background: #718096; }
    .slider::-webkit-slider-thumb { width: 16px; height: 16px; margin-top: -6.5px; appearance: none; border: 2px solid #111318; border-radius: 50%; background: var(--source); box-shadow: 0 0 0 1px #ffffff40; }
    .slider::-moz-range-track { height: 3px; border-radius: 2px; background: #718096; }
    .slider::-moz-range-thumb { width: 16px; height: 16px; border: 2px solid #111318; border-radius: 50%; background: var(--source); box-shadow: 0 0 0 1px #ffffff40; }
    .slider:hover, .slider:focus { opacity: 1; }
    @media (max-width: 800px) {
      .toolbar { left: 8px; right: 8px; translate: 0 0; max-width: none; flex-wrap: wrap; white-space: normal; }
      .context-toolbar { left: 8px; right: 8px; translate: 0 0; max-width: none; width: fit-content; }
      .stage.side-by-side { grid-template-columns: 1fr; grid-template-rows: 1fr 1fr; }
    }
  `;
  document.head.append(style);
  document.body.innerHTML = `
    <main>
      <div class="toolbar">
        <div class="picker-panel view-picker" aria-label="Review view">
          <div class="picker-heading"><span class="current-view" id="current-view"></span><span><kbd>←</kbd> <kbd>→</kbd></span></div>
          <div class="picker-list" id="view-list" role="listbox"></div>
        </div>
        <div class="picker-panel mode-picker" aria-label="Comparison mode">
          <div class="picker-heading"><span id="current-mode"></span><span><kbd>↑</kbd> <kbd>↓</kbd></span></div>
          <div class="picker-list" id="mode-list" role="listbox"></div>
        </div>
        <label class="checkbox"><input id="sync" type="checkbox" checked disabled>Sync <kbd>S</kbd></label>
        <button id="reset" type="button">Fit <kbd>F</kbd></button>
        <button id="flip" type="button"><span id="flip-label">Source</span><kbd>Space</kbd></button>
      </div>
      <div class="context-toolbar" id="context-toolbar">
        <span class="context-label" id="context-label"></span>
        <span class="context-assets" id="asset-context">
          <button id="context-previous" type="button" aria-label="Previous item">‹ <kbd>[</kbd></button>
          <select id="context-select" aria-label="View item"></select>
          <button id="context-next" type="button" aria-label="Next item">› <kbd>]</kbd></button>
        </span>
        <span class="camera-control" id="camera-control" hidden><select id="orientation" aria-label="3D preset"><option value="isometric">Isometric</option><option value="top">Top</option><option value="bottom">Bottom</option><option value="front">Front</option><option value="back">Back</option></select><kbd>1–5</kbd></span>
      </div>
      <div class="labels">
        <span class="destination-label" id="destination-label"></span>
        <span class="source-label" id="source-label"></span>
      </div>
      <div class="stage" id="stage">
        <div class="viewer-pane" id="destination-viewer"></div>
        <div class="source-layer" id="source-layer"><div class="viewer-pane" id="source-viewer"></div></div>
        <canvas class="comparison-overlay" id="comparison-overlay" aria-hidden="true"></canvas>
        <div class="divider" id="divider"></div>
      </div>
      <input class="slider" id="slider" type="range" min="0" max="100" value="50" aria-label="Comparison split">
    </main>
  `;

  const viewList = document.querySelector("#view-list");
  const currentView = document.querySelector("#current-view");
  const modeList = document.querySelector("#mode-list");
  const currentMode = document.querySelector("#current-mode");
  const orientationSelect = document.querySelector("#orientation");
  const cameraControl = document.querySelector("#camera-control");
  const contextLabel = document.querySelector("#context-label");
  const assetContext = document.querySelector("#asset-context");
  const contextSelect = document.querySelector("#context-select");
  const contextPrevious = document.querySelector("#context-previous");
  const contextNext = document.querySelector("#context-next");
  const syncCheckbox = document.querySelector("#sync");
  const sourceLayer = document.querySelector("#source-layer");
  const comparisonOverlay = document.querySelector("#comparison-overlay");
  const comparisonContext = comparisonOverlay.getContext("2d");
  const destinationBuffer = document.createElement("canvas");
  const sourceBuffer = document.createElement("canvas");
  const destinationBufferContext = destinationBuffer.getContext("2d", { willReadFrequently: true });
  const sourceBufferContext = sourceBuffer.getContext("2d", { willReadFrequently: true });
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
  let activeViewIndex = 0;
  let activeModeIndex = 0;
  let comparisonFrame = null;

  document.querySelector("#destination-label").textContent = review.destinationLabel;
  document.querySelector("#source-label").textContent = review.sourceLabel;

  const viewDefinitions = [
    {
      id: "schematics",
      name: "Schematics",
      contextName: "Page",
      matches: (asset) => asset.path.startsWith("schematic/svg/"),
    },
    {
      id: "layers",
      name: "PCB layers",
      contextName: "Layer",
      matches: (asset) => asset.path.startsWith("board/svg/"),
    },
    {
      id: "renders",
      name: "PCB renders",
      contextName: "Image",
      matches: (asset) => asset.path.startsWith("renders/"),
    },
    {
      id: "3d",
      name: "Interactive 3D",
      contextName: "Preset",
      matches: (asset) => asset.kind === "model",
    },
  ];
  const reviewViews = viewDefinitions.map((definition) => ({
    ...definition,
    assetIndexes: review.assets
      .map((asset, index) => definition.matches(asset) ? index : -1)
      .filter((index) => index >= 0),
  })).filter((view) => view.assetIndexes.length > 0);
  const viewSelections = reviewViews.map((view) => view.assetIndexes[0]);
  const viewIndexByAsset = new Map();
  reviewViews.forEach((view, viewIndex) => {
    view.assetIndexes.forEach((assetIndex) => viewIndexByAsset.set(assetIndex, viewIndex));
  });
  const contextAssetName = (asset) => asset.name.includes(":")
    ? asset.name.slice(asset.name.indexOf(":") + 1).trim()
    : asset.name;

  const viewButtons = reviewViews.map((view, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.id = `review-view-${index}`;
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", "false");
    button.textContent = view.name;
    button.addEventListener("click", () => {
      setActiveView(index);
      button.blur();
    });
    viewList.append(button);
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
    button.addEventListener("click", () => {
      setMode(index);
      button.blur();
    });
    modeList.append(button);
    return button;
  });
  const activeMode = () => modes[activeModeIndex].id;
  const navigationIsSynchronized = () => activeMode() !== "side-by-side" || syncCheckbox.checked;
  let destinationViewer;
  let sourceViewer;
  destinationViewer = new ReviewViewer(
    document.querySelector("#destination-viewer"),
    (state) => {
      synchronize(sourceViewer, state);
      scheduleComparison();
    },
  );
  sourceViewer = new ReviewViewer(
    document.querySelector("#source-viewer"),
    (state) => {
      synchronize(destinationViewer, state);
      scheduleComparison();
    },
  );

  function synchronize(target, state) {
    if (synchronizing || !navigationIsSynchronized() || !state) return;
    synchronizing = true;
    target.applyViewState(state);
    synchronizing = false;
  }

  function scheduleComparison() {
    if (!["diff", "highlight"].includes(activeMode()) || comparisonFrame !== null) return;
    comparisonFrame = requestAnimationFrame(() => {
      comparisonFrame = null;
      renderComparison();
    });
  }

  function renderComparison() {
    const mode = activeMode();
    if (!["diff", "highlight"].includes(mode)) return;
    const stageWidth = Math.max(stage.clientWidth, 1);
    const stageHeight = Math.max(stage.clientHeight, 1);
    const resolutionScale = Math.min(1, Math.sqrt(1600000 / (stageWidth * stageHeight)));
    const width = Math.max(Math.round(stageWidth * resolutionScale), 1);
    const height = Math.max(Math.round(stageHeight * resolutionScale), 1);
    [comparisonOverlay, destinationBuffer, sourceBuffer].forEach((canvas) => {
      if (canvas.width !== width) canvas.width = width;
      if (canvas.height !== height) canvas.height = height;
    });
    destinationBufferContext.clearRect(0, 0, width, height);
    sourceBufferContext.clearRect(0, 0, width, height);
    if (!destinationViewer.drawTo(destinationBufferContext, width, height)) return;
    if (!sourceViewer.drawTo(sourceBufferContext, width, height)) return;

    const destinationPixels = destinationBufferContext.getImageData(0, 0, width, height).data;
    const sourcePixels = sourceBufferContext.getImageData(0, 0, width, height).data;
    const compared = comparisonContext.createImageData(width, height);
    for (let index = 0; index < compared.data.length; index += 4) {
      const red = Math.abs(destinationPixels[index] - sourcePixels[index]);
      const green = Math.abs(destinationPixels[index + 1] - sourcePixels[index + 1]);
      const blue = Math.abs(destinationPixels[index + 2] - sourcePixels[index + 2]);
      const alpha = Math.abs(destinationPixels[index + 3] - sourcePixels[index + 3]);
      if (mode === "diff") {
        compared.data[index] = red;
        compared.data[index + 1] = green;
        compared.data[index + 2] = blue;
        compared.data[index + 3] = 255;
        continue;
      }
      const difference = Math.max(red, green, blue, alpha);
      const strength = Math.min(255, Math.max(0, difference - 6) * 5);
      compared.data[index] = 255;
      compared.data[index + 1] = 24;
      compared.data[index + 2] = 210;
      compared.data[index + 3] = strength;
    }
    comparisonContext.putImageData(compared, 0, 0);
  }

  async function chooseAsset() {
    const sequence = ++assetSequence;
    const asset = review.assets[activeAssetIndex];
    document.title = `${asset.name} · EveningStar review`;
    try {
      await Promise.all([
        destinationViewer.load({ kind: asset.kind, url: asset.destination }),
        sourceViewer.load({ kind: asset.kind, url: asset.source }),
      ]);
      if (sequence !== assetSequence) return;
      if (asset.kind === "model") {
        destinationViewer.setPreset(orientationSelect.value);
        sourceViewer.setPreset(orientationSelect.value);
        if (requestedOrbit) {
          destinationViewer.setOrbit(requestedOrbit.azimuth, requestedOrbit.elevation);
          sourceViewer.setOrbit(requestedOrbit.azimuth, requestedOrbit.elevation);
        }
        if (requestedZoom) {
          destinationViewer.setZoom(requestedZoom);
          sourceViewer.setZoom(requestedZoom);
        }
      }
      if (navigationIsSynchronized()) sourceViewer.applyViewState(destinationViewer.getViewState());
      document.documentElement.dataset.reviewReady = "true";
      scheduleComparison();
    } catch (error) {
      console.error(error);
    }
  }

  function setSplit(value) {
    const split = Number(value);
    slider.value = split;
    const stageBounds = stage.getBoundingClientRect();
    const sliderBounds = slider.getBoundingClientRect();
    const thumbRadius = 8;
    const trackWidth = Math.max(sliderBounds.width - thumbRadius * 2, 0);
    const splitPosition = sliderBounds.left - stageBounds.left
      + thumbRadius
      + trackWidth * split / 100;
    if (activeMode() === "overlay") {
      const hiddenWidth = Math.max(stageBounds.width - splitPosition, 0);
      sourceLayer.style.clipPath = `inset(0 ${hiddenWidth}px 0 0)`;
    }
    divider.style.left = `${splitPosition}px`;
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
    if (mode !== "overlay") sourceLayer.style.clipPath = "none";
    divider.hidden = mode !== "overlay";
    slider.hidden = mode !== "overlay";
    flip.disabled = mode !== "overlay";
    syncCheckbox.disabled = !sideBySide;
    if (!sideBySide) syncCheckbox.checked = true;
    if (!sideBySide) sourceViewer.applyViewState(destinationViewer.getViewState());
    requestAnimationFrame(() => {
      destinationViewer.resize();
      sourceViewer.resize();
      if (navigationIsSynchronized()) sourceViewer.applyViewState(destinationViewer.getViewState());
      if (mode === "overlay") setSplit(slider.value);
      if (["diff", "highlight"].includes(mode)) scheduleComparison();
    });
  }

  function moveView(delta) {
    setActiveView(activeViewIndex + delta);
  }

  function moveMode(delta) {
    setMode(activeModeIndex + delta);
  }

  function updateViewControls() {
    const view = reviewViews[activeViewIndex];
    const isModel = view.id === "3d";
    currentView.textContent = view.name;
    currentView.title = view.name;
    viewButtons.forEach((button, buttonIndex) => button.setAttribute("aria-selected", String(buttonIndex === activeViewIndex)));
    viewList.setAttribute("aria-activedescendant", viewButtons[activeViewIndex].id);
    contextLabel.textContent = view.contextName;
    assetContext.hidden = isModel;
    cameraControl.hidden = !isModel;
    if (isModel) return;
    contextSelect.replaceChildren(...view.assetIndexes.map((assetIndex) => {
      const option = document.createElement("option");
      option.value = String(assetIndex);
      option.textContent = contextAssetName(review.assets[assetIndex]);
      return option;
    }));
    contextSelect.value = String(activeAssetIndex);
    const onlyOneItem = view.assetIndexes.length <= 1;
    contextPrevious.disabled = onlyOneItem;
    contextNext.disabled = onlyOneItem;
  }

  function setActiveView(index, load = true) {
    activeViewIndex = (index + reviewViews.length) % reviewViews.length;
    activeAssetIndex = viewSelections[activeViewIndex];
    updateViewControls();
    if (load) chooseAsset();
  }

  function setActiveAsset(index, load = true) {
    const viewIndex = viewIndexByAsset.get(index);
    if (viewIndex === undefined) return;
    activeViewIndex = viewIndex;
    activeAssetIndex = index;
    viewSelections[viewIndex] = index;
    updateViewControls();
    if (load) chooseAsset();
  }

  function moveContext(delta) {
    const view = reviewViews[activeViewIndex];
    if (view.id === "3d") {
      orientationSelect.selectedIndex = (
        orientationSelect.selectedIndex + delta + orientationSelect.options.length
      ) % orientationSelect.options.length;
      orientationSelect.dispatchEvent(new Event("change"));
      return;
    }
    const currentIndex = view.assetIndexes.indexOf(activeAssetIndex);
    const nextIndex = (currentIndex + delta + view.assetIndexes.length) % view.assetIndexes.length;
    setActiveAsset(view.assetIndexes[nextIndex]);
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
  contextSelect.addEventListener("change", () => setActiveAsset(Number(contextSelect.value)));
  contextPrevious.addEventListener("click", () => {
    moveContext(-1);
    contextPrevious.blur();
  });
  contextNext.addEventListener("click", () => {
    moveContext(1);
    contextNext.blur();
  });
  slider.addEventListener("input", (event) => {
    showingSource = Number(event.target.value) > 50;
    setSplit(event.target.value);
  });
  flip.addEventListener("click", flipSide);
  reset.addEventListener("click", fitViews);
  document.addEventListener("dragstart", (event) => event.preventDefault(), true);
  document.addEventListener("selectstart", (event) => event.preventDefault(), true);
  document.addEventListener("pointerdown", () => window.getSelection()?.removeAllRanges(), true);
  window.addEventListener("resize", () => requestAnimationFrame(() => {
    setSplit(slider.value);
    scheduleComparison();
  }));
  window.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      event.stopPropagation();
      moveView(event.key === "ArrowLeft" ? -1 : 1);
    } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
      event.preventDefault();
      event.stopPropagation();
      moveMode(event.key === "ArrowUp" ? -1 : 1);
    } else if (event.key.toLowerCase() === "s" && activeMode() === "side-by-side") {
      event.preventDefault();
      syncCheckbox.checked = !syncCheckbox.checked;
      if (syncCheckbox.checked) sourceViewer.applyViewState(destinationViewer.getViewState());
    } else if (event.key.toLowerCase() === "f") {
      event.preventDefault();
      fitViews();
    } else if (event.key === "[" || event.key === "]") {
      event.preventDefault();
      moveContext(event.key === "[" ? -1 : 1);
    } else if (/^[1-5]$/.test(event.key) && !cameraControl.hidden) {
      event.preventDefault();
      orientationSelect.selectedIndex = Number(event.key) - 1;
      orientationSelect.dispatchEvent(new Event("change"));
    } else if (event.key === " " && activeMode() === "overlay") {
      event.preventDefault();
      flipSide();
    }
  }, true);

  const parameters = new URLSearchParams(window.location.search);
  const requestedAzimuth = Number(parameters.get("azimuth"));
  const requestedElevation = Number(parameters.get("elevation"));
  const requestedOrbit = parameters.has("azimuth")
    && parameters.has("elevation")
    && Number.isFinite(requestedAzimuth)
    && Number.isFinite(requestedElevation)
    ? { azimuth: requestedAzimuth, elevation: requestedElevation }
    : null;
  const requestedZoomValue = Number(parameters.get("zoom"));
  const requestedZoom = parameters.has("zoom") && Number.isFinite(requestedZoomValue)
    ? requestedZoomValue
    : null;
  const requestedView = parameters.get("view");
  const requestedIndex = review.assets.findIndex((asset) =>
    asset.path === requestedView || (requestedView === "3d" && asset.kind === "model"),
  );
  const requestedViewIndex = reviewViews.findIndex((view) => view.id === requestedView);
  if (requestedIndex >= 0) setActiveAsset(requestedIndex, false);
  else setActiveView(requestedViewIndex >= 0 ? requestedViewIndex : 0, false);
  const requestedOrientation = parameters.get("orientation") || parameters.get("camera");
  if ([...orientationSelect.options].some((option) => option.value === requestedOrientation)) {
    orientationSelect.value = requestedOrientation;
  }
  const requestedSide = parameters.get("side");
  const requestedSplit = Number(parameters.get("split"));
  const initialSplit = requestedSide === "destination"
    ? 0
    : requestedSide === "source"
      ? 100
      : parameters.has("split") && Number.isFinite(requestedSplit)
        ? THREE.MathUtils.clamp(requestedSplit, 0, 100)
        : 50;
  setSplit(initialSplit);
  const requestedMode = parameters.get("mode") || (parameters.get("layout") === "side-by-side" ? "side-by-side" : "overlay");
  setMode(Math.max(0, modes.findIndex((mode) => mode.id === requestedMode)));
  chooseAsset();
}
