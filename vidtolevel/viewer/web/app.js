import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const dom = {
  viewport: document.querySelector("#viewport"),
  emptyState: document.querySelector("#empty-state"),
  projectName: document.querySelector("#project-name"),
  projectSelect: document.querySelector("#project-select"),
  layerPoints: document.querySelector("#layer-points"),
  layerMesh: document.querySelector("#layer-mesh"),
  layerCameras: document.querySelector("#layer-cameras"),
  layerPath: document.querySelector("#layer-path"),
  colorMode: document.querySelector("#color-mode"),
  pointSize: document.querySelector("#point-size"),
  meshMode: document.querySelector("#mesh-mode"),
  meshOpacity: document.querySelector("#mesh-opacity"),
  frustumScale: document.querySelector("#frustum-scale"),
  selectionBody: document.querySelector("#selection-body"),
  metricCameras: document.querySelector("#metric-cameras"),
  metricPoints: document.querySelector("#metric-points"),
  metricVisibleCameras: document.querySelector("#metric-visible-cameras"),
  metricCoverage: document.querySelector("#metric-coverage"),
  diagnosticBody: document.querySelector("#diagnostic-body"),
  coverageCanvas: document.querySelector("#coverage-canvas"),
  timelineRange: document.querySelector("#timeline-range"),
  playToggle: document.querySelector("#play-toggle"),
  statusProject: document.querySelector("#status-project"),
  statusStage: document.querySelector("#status-stage"),
  statusLive: document.querySelector("#status-live"),
  statusCameras: document.querySelector("#status-cameras"),
  statusPoints: document.querySelector("#status-points"),
};

const state = {
  projects: [],
  activeProject: null,
  cameras: [],
  visibleCameraCount: 0,
  playing: false,
  playTimer: null,
  pointObject: null,
  meshObject: null,
  meshFillObject: null,
  meshWireObject: null,
  cameraGroup: new THREE.Group(),
  frustumGroup: new THREE.Group(),
  pathLine: null,
  pathIssueLine: null,
  selectedMarker: null,
  jobSocket: null,
  jobReconnectTimer: null,
  projectSocket: null,
  projectReconnectTimer: null,
  snapshotSignature: "",
  snapshotRefreshing: false,
};

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x111315);

const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(dom.viewport.clientWidth, dom.viewport.clientHeight);
dom.viewport.appendChild(renderer.domElement);

const camera = new THREE.PerspectiveCamera(
  55,
  dom.viewport.clientWidth / Math.max(dom.viewport.clientHeight, 1),
  0.01,
  100000,
);
camera.position.set(2, 2, 4);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.screenSpacePanning = true;
const grid = new THREE.GridHelper(20, 20, 0x4a5259, 0x2a3035);
grid.material.transparent = true;
grid.material.opacity = 0.55;
scene.add(grid);

scene.add(new THREE.AmbientLight(0xffffff, 0.8));
state.cameraGroup.name = "camera-markers";
state.frustumGroup.name = "camera-frustums";
scene.add(state.cameraGroup);
scene.add(state.frustumGroup);

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const markerGeometry = new THREE.SphereGeometry(0.035, 12, 8);
const markerMaterial = new THREE.MeshBasicMaterial({ color: 0xe8a84f });
const selectedMarkerMaterial = new THREE.MeshBasicMaterial({ color: 0xee6a5f });
const previewMeshMaterial = new THREE.MeshBasicMaterial({
  color: 0x86b9c8,
  transparent: true,
  opacity: 0.42,
  side: THREE.DoubleSide,
  depthWrite: false,
});
const previewMeshWireMaterial = new THREE.LineBasicMaterial({
  color: 0xb9eef0,
  transparent: true,
  opacity: 0.72,
  depthWrite: false,
});
const frustumMaterial = new THREE.LineBasicMaterial({ color: 0x4cc9b0, transparent: true, opacity: 0.68 });
const pathMaterial = new THREE.LineBasicMaterial({ color: 0xe8a84f, transparent: true, opacity: 0.9 });
const pathIssueMaterial = new THREE.LineBasicMaterial({ color: 0xee6a5f, transparent: true, opacity: 1.0 });

init();
animate();

async function init() {
  bindControls();
  connectJobSocket();
  await loadProjects();
}

function bindControls() {
  window.addEventListener("resize", resize);
  renderer.domElement.addEventListener("pointerdown", selectCamera);

  dom.projectSelect.addEventListener("change", async () => {
    const project = state.projects.find((item) => item.id === dom.projectSelect.value);
    if (project) {
      await loadProject(project);
    }
  });

  dom.layerPoints.addEventListener("change", updateLayerVisibility);
  dom.layerMesh.addEventListener("change", updateLayerVisibility);
  dom.layerCameras.addEventListener("change", updateLayerVisibility);
  dom.layerPath.addEventListener("change", updateLayerVisibility);
  dom.colorMode.addEventListener("change", reloadPointCloud);
  dom.pointSize.addEventListener("input", () => {
    if (state.pointObject) {
      state.pointObject.material.size = Number(dom.pointSize.value) / 100;
    }
  });
  dom.meshMode.addEventListener("change", updateMeshDisplay);
  dom.meshOpacity.addEventListener("input", updateMeshDisplay);
  dom.frustumScale.addEventListener("input", rebuildCameraGraphics);
  dom.timelineRange.addEventListener("input", () => setVisibleCameraCount(Number(dom.timelineRange.value) + 1));
  dom.playToggle.addEventListener("click", togglePlayback);
}

async function loadProjects() {
  setStatus("Loading projects", "Static viewer");
  const response = await fetch("/api/projects");
  state.projects = await response.json();

  dom.projectSelect.replaceChildren();
  for (const project of state.projects) {
    const option = document.createElement("option");
    option.value = project.id;
    option.textContent = project.name;
    dom.projectSelect.append(option);
  }

  if (state.projects.length === 0) {
    state.activeProject = null;
    closeProjectSocket();
    clearSceneData();
    dom.emptyState.classList.remove("hidden");
    setStatus("No project", "Waiting for sparse model");
    return;
  }

  await loadProject(state.projects[0]);
}

async function loadProject(project, options = {}) {
  const reconnectSocket = options.reconnectSocket ?? true;
  state.activeProject = project;
  dom.emptyState.classList.add("hidden");
  dom.projectSelect.value = project.id;
  dom.projectName.textContent = project.root;
  setStatus(project.name, "Loading cameras");

  clearSceneData();

  const [statusResponse, cameraResponse, pointsResponse, coverageResponse] = await Promise.all([
    fetch(`/api/${project.id}/status`),
    fetch(`/api/${project.id}/cameras`),
    fetch(pointsUrl(project.id)),
    fetch(`/api/${project.id}/coverage?cell_size=1`),
  ]);
  const status = await statusResponse.json();
  const cameraPayload = await cameraResponse.json();
  const coverage = await coverageResponse.json();

  state.snapshotSignature = status.modelSignature || state.snapshotSignature;
  state.cameras = cameraPayload.cameras;
  state.visibleCameraCount = state.cameras.length;
  dom.timelineRange.max = Math.max(state.cameras.length - 1, 0);
  dom.timelineRange.value = Math.max(state.cameras.length - 1, 0);

  await buildPointCloud(pointsResponse);
  await loadMeshPreview(status.meshUrl || "", status.meshFormat || "", status.meshResourceUrl || "");
  rebuildCameraGraphics();
  drawCoverage(coverage);
  updateMetrics(status, coverage);
  frameScene(status.bounds);
  setStatus(project.name, "Loaded");
  if (reconnectSocket) {
    connectProjectSocket(project.id);
  }
}

async function reloadPointCloud() {
  if (!state.activeProject) {
    return;
  }
  setStatus(state.activeProject.name, `Loading ${dom.colorMode.value} colors`);
  if (state.pointObject) {
    scene.remove(state.pointObject);
    state.pointObject.geometry.dispose();
    state.pointObject.material.dispose();
    state.pointObject = null;
  }
  const response = await fetch(pointsUrl(state.activeProject.id));
  await buildPointCloud(response);
  updateLayerVisibility();
  setStatus(state.activeProject.name, "Loaded");
}

function pointsUrl(projectId) {
  const params = new URLSearchParams({ color_mode: dom.colorMode.value });
  return `/api/${projectId}/points?${params.toString()}`;
}

function clearSceneData() {
  if (state.pointObject) {
    scene.remove(state.pointObject);
    state.pointObject.geometry.dispose();
    state.pointObject.material.dispose();
    state.pointObject = null;
  }
  if (state.meshObject) {
    scene.remove(state.meshObject);
    disposeObjectTree(state.meshObject);
    state.meshObject = null;
    state.meshFillObject = null;
    state.meshWireObject = null;
  }
  state.cameraGroup.clear();
  state.frustumGroup.clear();
  if (state.pathLine) {
    scene.remove(state.pathLine);
    state.pathLine.geometry.dispose();
    state.pathLine = null;
  }
  if (state.pathIssueLine) {
    scene.remove(state.pathIssueLine);
    state.pathIssueLine.geometry.dispose();
    state.pathIssueLine = null;
  }
  state.selectedMarker = null;
  dom.selectionBody.textContent = "None";
}

async function buildPointCloud(response) {
  const count = Number(response.headers.get("X-VidToLevel-Point-Count") || "0");
  const stride = Number(response.headers.get("X-VidToLevel-Point-Stride") || "15");
  const buffer = await response.arrayBuffer();
  const view = new DataView(buffer);
  const positions = new Float32Array(count * 3);
  const colors = new Uint8Array(count * 3);

  for (let index = 0; index < count; index += 1) {
    const offset = index * stride;
    positions[index * 3] = view.getFloat32(offset, true);
    positions[index * 3 + 1] = view.getFloat32(offset + 4, true);
    positions[index * 3 + 2] = view.getFloat32(offset + 8, true);
    colors[index * 3] = view.getUint8(offset + 12);
    colors[index * 3 + 1] = view.getUint8(offset + 13);
    colors[index * 3 + 2] = view.getUint8(offset + 14);
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.Uint8BufferAttribute(colors, 3, true));
  geometry.computeBoundingSphere();

  const material = new THREE.PointsMaterial({
    size: Number(dom.pointSize.value) / 100,
    vertexColors: true,
    sizeAttenuation: true,
  });
  state.pointObject = new THREE.Points(geometry, material);
  scene.add(state.pointObject);
}

async function loadMeshPreview(meshUrl, meshFormat = "", meshResourceUrl = "") {
  if (!meshUrl) {
    return;
  }
  setStatus(state.activeProject?.name || "Project", "Loading mesh");
  const format = meshFormat || meshUrl.split("?")[0].split(".").pop().toLowerCase();
  if (format === "glb" || format === "gltf") {
    await loadGltfMeshPreview(meshUrl, meshResourceUrl);
    return;
  }
  await loadObjMeshPreview(meshUrl);
}

async function loadObjMeshPreview(meshUrl) {
  const response = await fetch(meshUrl);
  if (!response.ok) {
    return;
  }
  const text = await response.text();
  const geometry = parseObjGeometry(text);
  if (!geometry) {
    return;
  }
  const group = new THREE.Group();
  group.name = "preview-mesh";

  const fill = new THREE.Mesh(geometry, previewMeshMaterial.clone());
  fill.name = "preview-mesh-fill";
  const wire = new THREE.LineSegments(
    new THREE.WireframeGeometry(geometry),
    previewMeshWireMaterial.clone(),
  );
  wire.name = "preview-mesh-wire";

  registerMeshPreview(group, fill, wire);
}

async function loadGltfMeshPreview(meshUrl, meshResourceUrl) {
  const loader = new GLTFLoader();
  if (meshResourceUrl) {
    loader.setResourcePath(meshResourceUrl);
  }
  const gltf = await new Promise((resolve, reject) => {
    loader.load(meshUrl, resolve, undefined, reject);
  });
  const group = new THREE.Group();
  group.name = "preview-mesh";
  const fill = gltf.scene;
  fill.name = "preview-mesh-fill";
  prepareMeshMaterials(fill);
  const wire = buildWireframeObject(fill);
  wire.name = "preview-mesh-wire";
  registerMeshPreview(group, fill, wire);
}

function registerMeshPreview(group, fill, wire) {
  group.add(fill);
  group.add(wire);
  state.meshObject = group;
  state.meshFillObject = fill;
  state.meshWireObject = wire;
  state.meshObject.renderOrder = -1;
  scene.add(state.meshObject);
  updateLayerVisibility();
}

function disposeObjectTree(object) {
  object.traverse((child) => {
    if (child.geometry) {
      child.geometry.dispose();
    }
    if (child.material) {
      if (Array.isArray(child.material)) {
        for (const material of child.material) {
          material.dispose();
        }
      } else {
        child.material.dispose();
      }
    }
  });
}

function prepareMeshMaterials(object) {
  object.traverse((child) => {
    if (!child.isMesh) {
      return;
    }
    if (child.geometry && !child.geometry.getAttribute("normal")) {
      child.geometry.computeVertexNormals();
    }
    if (!child.material) {
      return;
    }
    if (Array.isArray(child.material)) {
      child.material = child.material.map((material) => material.clone());
    } else {
      child.material = child.material.clone();
    }
    setMaterialSide(child.material, THREE.DoubleSide);
  });
}

function buildWireframeObject(object) {
  const group = new THREE.Group();
  object.updateWorldMatrix(true, true);
  object.traverse((child) => {
    if (!child.isMesh || !child.geometry) {
      return;
    }
    const line = new THREE.LineSegments(
      new THREE.WireframeGeometry(child.geometry),
      previewMeshWireMaterial.clone(),
    );
    line.matrix.copy(child.matrixWorld);
    line.matrixAutoUpdate = false;
    group.add(line);
  });
  return group;
}

function parseObjGeometry(text) {
  const vertices = [];
  const triangles = [];
  const lines = text.split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("v ")) {
      const parts = trimmed.split(/\s+/);
      if (parts.length >= 4) {
        vertices.push([Number(parts[1]), Number(parts[2]), Number(parts[3])]);
      }
    } else if (trimmed.startsWith("f ")) {
      const indices = trimmed
        .split(/\s+/)
        .slice(1)
        .map((token) => resolveObjIndex(token, vertices.length))
        .filter((index) => index !== null);
      for (let index = 1; index < indices.length - 1; index += 1) {
        triangles.push(indices[0], indices[index], indices[index + 1]);
      }
    }
  }

  if (vertices.length === 0 || triangles.length === 0) {
    return null;
  }

  const positions = new Float32Array(triangles.length * 3);
  for (let index = 0; index < triangles.length; index += 1) {
    const vertex = vertices[triangles[index]];
    positions[index * 3] = vertex[0];
    positions[index * 3 + 1] = vertex[1];
    positions[index * 3 + 2] = vertex[2];
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
  return geometry;
}

function resolveObjIndex(token, vertexCount) {
  const raw = Number(token.split("/")[0]);
  if (!Number.isInteger(raw) || raw === 0) {
    return null;
  }
  const index = raw > 0 ? raw - 1 : vertexCount + raw;
  return index >= 0 && index < vertexCount ? index : null;
}

function rebuildCameraGraphics() {
  state.cameraGroup.clear();
  state.frustumGroup.clear();
  if (state.pathLine) {
    scene.remove(state.pathLine);
    state.pathLine.geometry.dispose();
    state.pathLine = null;
  }
  if (state.pathIssueLine) {
    scene.remove(state.pathIssueLine);
    state.pathIssueLine.geometry.dispose();
    state.pathIssueLine = null;
  }

  const visible = state.cameras.slice(0, state.visibleCameraCount);
  const scale = computeFrustumScale() * (Number(dom.frustumScale.value) / 20);
  const pathPositions = [];
  const pathIssuePositions = [];
  let previousPosition = null;

  for (const item of visible) {
    const position = new THREE.Vector3(...item.position);
    const marker = new THREE.Mesh(markerGeometry, markerMaterial.clone());
    marker.position.copy(position);
    marker.userData.camera = item;
    state.cameraGroup.add(marker);

    if (previousPosition) {
      const target = item.pathIssueAfterPrevious ? pathIssuePositions : pathPositions;
      target.push(previousPosition.x, previousPosition.y, previousPosition.z, position.x, position.y, position.z);
    }
    previousPosition = position;

    const line = makeFrustumLine(item, scale);
    state.frustumGroup.add(line);
  }

  if (pathPositions.length > 0) {
    state.pathLine = makePathLine(pathPositions, pathMaterial);
    scene.add(state.pathLine);
  }
  if (pathIssuePositions.length > 0) {
    state.pathIssueLine = makePathLine(pathIssuePositions, pathIssueMaterial);
    scene.add(state.pathIssueLine);
  }

  updateLayerVisibility();
  dom.metricVisibleCameras.textContent = String(visible.length);
  dom.statusCameras.textContent = `${visible.length}/${state.cameras.length} cameras`;
}

function makePathLine(vertices, material) {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
  return new THREE.LineSegments(geometry, material);
}

function makeFrustumLine(item, scale) {
  const fovX = item.fovX || Math.PI / 3;
  const fovY = item.fovY || Math.PI / 4;
  const z = scale;
  const halfWidth = Math.tan(fovX / 2) * z;
  const halfHeight = Math.tan(fovY / 2) * z;
  const local = [
    [0, 0, 0],
    [-halfWidth, -halfHeight, z],
    [halfWidth, -halfHeight, z],
    [halfWidth, halfHeight, z],
    [-halfWidth, halfHeight, z],
  ];
  const edges = [
    [0, 1],
    [0, 2],
    [0, 3],
    [0, 4],
    [1, 2],
    [2, 3],
    [3, 4],
    [4, 1],
  ];
  const points = local.map((point) => transformCameraPoint(item, point));
  const vertices = [];
  for (const [a, b] of edges) {
    vertices.push(points[a].x, points[a].y, points[a].z, points[b].x, points[b].y, points[b].z);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
  return new THREE.LineSegments(geometry, frustumMaterial);
}

function transformCameraPoint(item, localPoint) {
  const rotation = item.rotationCameraToWorld;
  const x = localPoint[0];
  const y = localPoint[1];
  const z = localPoint[2];
  return new THREE.Vector3(
    item.position[0] + rotation[0] * x + rotation[1] * y + rotation[2] * z,
    item.position[1] + rotation[3] * x + rotation[4] * y + rotation[5] * z,
    item.position[2] + rotation[6] * x + rotation[7] * y + rotation[8] * z,
  );
}

function setVisibleCameraCount(count) {
  state.visibleCameraCount = Math.max(0, Math.min(count, state.cameras.length));
  rebuildCameraGraphics();
}

function togglePlayback() {
  state.playing = !state.playing;
  dom.playToggle.textContent = state.playing ? "Pause" : "Play";
  if (!state.playing) {
    window.clearInterval(state.playTimer);
    state.playTimer = null;
    return;
  }
  state.playTimer = window.setInterval(() => {
    const next = Number(dom.timelineRange.value) + 1;
    const value = next > Number(dom.timelineRange.max) ? 0 : next;
    dom.timelineRange.value = value;
    setVisibleCameraCount(value + 1);
  }, 180);
}

function selectCamera(event) {
  const bounds = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
  pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(state.cameraGroup.children, false);
  if (hits.length === 0) {
    return;
  }
  if (state.selectedMarker) {
    state.selectedMarker.material.color.copy(markerMaterial.color);
  }
  const marker = hits[0].object;
  marker.material.color.copy(selectedMarkerMaterial.color);
  state.selectedMarker = marker;
  const item = marker.userData.camera;
  const thumbnail = item.thumbnailUrl
    ? `<img class="selection-thumb" src="${escapeAttribute(item.thumbnailUrl)}" alt="" />`
    : "";
  const issues = item.pathIssueReasons?.length
    ? `<br /><span class="selection-warning">Path issue: ${item.pathIssueReasons.map(escapeHtml).join(", ")}</span>`
    : "";
  dom.selectionBody.innerHTML = `
    ${thumbnail}
    <strong>${escapeHtml(item.name)}</strong>
    Image ID ${item.id}<br />
    Camera ${item.cameraId} / ${escapeHtml(item.model)}<br />
    ${item.registeredPointCount.toLocaleString()} observed points<br />
    ${item.width} x ${item.height}${issues}
  `;
}

function updateLayerVisibility() {
  if (state.pointObject) {
    state.pointObject.visible = dom.layerPoints.checked;
  }
  if (state.meshObject) {
    state.meshObject.visible = dom.layerMesh.checked;
  }
  updateMeshDisplay();
  state.cameraGroup.visible = dom.layerCameras.checked;
  state.frustumGroup.visible = dom.layerCameras.checked;
  if (state.pathLine) {
    state.pathLine.visible = dom.layerPath.checked;
  }
  if (state.pathIssueLine) {
    state.pathIssueLine.visible = dom.layerPath.checked;
  }
}

function updateMeshDisplay() {
  if (!state.meshObject) {
    return;
  }
  const enabled = dom.layerMesh.checked;
  const mode = dom.meshMode.value;
  const opacity = Number(dom.meshOpacity.value) / 100;
  state.meshObject.visible = enabled;
  if (state.meshFillObject) {
    state.meshFillObject.visible = enabled && (mode === "shaded" || mode === "both");
    setObjectOpacity(state.meshFillObject, opacity);
  }
  if (state.meshWireObject) {
    state.meshWireObject.visible = enabled && (mode === "wire" || mode === "both");
    setObjectOpacity(state.meshWireObject, Math.min(1.0, opacity + 0.25));
  }
}

function setObjectOpacity(object, opacity) {
  object.traverse((child) => {
    if (child.material) {
      setMaterialOpacity(child.material, opacity);
    }
  });
}

function setMaterialOpacity(materialOrList, opacity) {
  const materials = Array.isArray(materialOrList) ? materialOrList : [materialOrList];
  for (const material of materials) {
    material.transparent = opacity < 1 || material.transparent;
    material.opacity = opacity;
    material.depthWrite = opacity >= 1;
    material.needsUpdate = true;
  }
}

function setMaterialSide(materialOrList, side) {
  const materials = Array.isArray(materialOrList) ? materialOrList : [materialOrList];
  for (const material of materials) {
    material.side = side;
    material.needsUpdate = true;
  }
}

function updateMetrics(status, coverage) {
  dom.metricCameras.textContent = status.cameraCount.toLocaleString();
  dom.metricPoints.textContent = status.pointCount.toLocaleString();
  dom.metricVisibleCameras.textContent = String(state.visibleCameraCount);
  dom.metricCoverage.textContent = coverage.cells.length.toLocaleString();
  dom.statusProject.textContent = state.activeProject?.name || "Project";
  dom.statusPoints.textContent = `${status.pointCount.toLocaleString()} points`;
  renderDiagnostics(status.diagnostics || {});
}

function renderDiagnostics(summary) {
  const cameraCount = Number(summary.cameraCount || 0);
  if (cameraCount === 0) {
    dom.diagnosticBody.textContent = "No cameras";
    return;
  }

  const issueCount = Number(summary.issueCount || 0);
  const reasons = summary.reasonCounts || {};
  const largeGapCount = Number(reasons.large_gap || 0);
  const weakObservationCount = Number(reasons.weak_observations || 0);
  const maxDistance = Number(summary.maxDistanceFromPrevious || 0);
  const headline = issueCount === 0 ? "Path OK" : `${issueCount.toLocaleString()} path issues`;

  dom.diagnosticBody.innerHTML = `
    <strong>${escapeHtml(headline)}</strong>
    <div class="diagnostic-row"><span>Large gaps</span><b>${largeGapCount.toLocaleString()}</b></div>
    <div class="diagnostic-row"><span>Weak observations</span><b>${weakObservationCount.toLocaleString()}</b></div>
    <div class="diagnostic-row"><span>Max gap</span><b>${maxDistance.toFixed(2)}</b></div>
  `;
}

function drawCoverage(coverage) {
  const canvas = dom.coverageCanvas;
  const context = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.floor(canvas.clientWidth * ratio));
  const height = Math.max(1, Math.floor(canvas.clientHeight * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  context.fillStyle = "#111315";
  context.fillRect(0, 0, canvas.width, canvas.height);

  const cells = coverage.cells || [];
  if (!cells.length) {
    return;
  }
  const minX = Math.min(...cells.map((cell) => cell.x));
  const maxX = Math.max(...cells.map((cell) => cell.x));
  const minZ = Math.min(...cells.map((cell) => cell.z));
  const maxZ = Math.max(...cells.map((cell) => cell.z));
  const maxCount = Math.max(...cells.map((cell) => cell.point_count));
  const cellW = canvas.width / Math.max(1, maxX - minX + 1);
  const cellH = canvas.height / Math.max(1, maxZ - minZ + 1);
  for (const cell of cells) {
    const color = heatColor(Math.log1p(cell.point_count) / Math.log1p(maxCount || 1));
    context.fillStyle = color;
    context.fillRect(
      (cell.x - minX) * cellW,
      canvas.height - (cell.z - minZ + 1) * cellH,
      Math.max(1, cellW),
      Math.max(1, cellH),
    );
  }
}

function heatColor(ratio) {
  const red = Math.floor(238 - ratio * 162);
  const green = Math.floor(106 + ratio * 95);
  const blue = Math.floor(95 + ratio * 81);
  return `rgb(${red}, ${green}, ${blue})`;
}

function frameScene(bounds) {
  const center = new THREE.Vector3(...bounds.center);
  const diagonal = Math.max(boundsDiagonal(bounds), 1);
  grid.scale.setScalar(Math.max(diagonal / 20, 0.2));
  grid.position.copy(center);
  grid.position.y = bounds.min[1];
  controls.target.copy(center);
  camera.near = Math.max(diagonal / 10000, 0.001);
  camera.far = diagonal * 100;
  camera.position.copy(center).add(new THREE.Vector3(diagonal * 0.7, diagonal * 0.45, diagonal * 0.9));
  camera.updateProjectionMatrix();
  controls.update();
}

function computeFrustumScale() {
  if (state.pointObject?.geometry.boundingSphere) {
    return Math.max(state.pointObject.geometry.boundingSphere.radius * 0.08, 0.08);
  }
  return 0.2;
}

function boundsDiagonal(bounds) {
  const dx = bounds.max[0] - bounds.min[0];
  const dy = bounds.max[1] - bounds.min[1];
  const dz = bounds.max[2] - bounds.min[2];
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

function setStatus(project, stage) {
  dom.statusProject.textContent = project;
  dom.statusStage.textContent = stage;
}

function connectJobSocket() {
  if (state.jobSocket) {
    state.jobSocket.close();
  }
  window.clearTimeout(state.jobReconnectTimer);

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${protocol}//${window.location.host}/ws/jobs`;
  const socket = new WebSocket(url);
  state.jobSocket = socket;
  dom.statusLive.textContent = "Live connecting";

  socket.addEventListener("open", () => {
    dom.statusLive.textContent = "Live connected";
  });
  socket.addEventListener("message", (event) => {
    try {
      updateLiveJobs(JSON.parse(event.data));
    } catch {
      dom.statusLive.textContent = "Live payload error";
    }
  });
  socket.addEventListener("close", () => {
    if (state.jobSocket === socket) {
      dom.statusLive.textContent = "Live reconnecting";
      state.jobReconnectTimer = window.setTimeout(connectJobSocket, 2000);
    }
  });
  socket.addEventListener("error", () => {
    dom.statusLive.textContent = "Live error";
  });
}

function connectProjectSocket(projectId) {
  closeProjectSocket();

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const url = `${protocol}//${window.location.host}/ws/${encodeURIComponent(projectId)}`;
  const socket = new WebSocket(url);
  state.projectSocket = socket;

  socket.addEventListener("message", (event) => {
    try {
      updateSparseSnapshot(JSON.parse(event.data));
    } catch {
      dom.statusLive.textContent = "Sparse payload error";
    }
  });
  socket.addEventListener("close", () => {
    if (state.projectSocket === socket && state.activeProject?.id === projectId) {
      state.projectReconnectTimer = window.setTimeout(() => connectProjectSocket(projectId), 2000);
    }
  });
}

function closeProjectSocket() {
  if (state.projectSocket) {
    state.projectSocket.close();
    state.projectSocket = null;
  }
  window.clearTimeout(state.projectReconnectTimer);
  state.projectReconnectTimer = null;
}

async function updateSparseSnapshot(payload) {
  if (!state.activeProject || payload.project !== state.activeProject.id) {
    return;
  }
  if (payload.type === "sparse_snapshot_error") {
    dom.statusLive.textContent = "Sparse: waiting for stable snapshot";
    return;
  }
  const signature = payload.signature || "";
  if (!signature || signature === state.snapshotSignature) {
    return;
  }
  state.snapshotSignature = signature;
  const diff = payload.diff || {};
  if (diff.initial === false) {
    const cameraDelta = Number(diff.cameraCountDelta || 0);
    const pointDelta = Number(diff.pointCountDelta || 0);
    dom.statusLive.textContent = `Sparse: ${formatDelta(cameraDelta)} cameras · ${formatDelta(pointDelta)} points`;
  } else {
    dom.statusLive.textContent = `Sparse: ${payload.cameraCount} cameras · refreshing`;
  }
  if (state.snapshotRefreshing) {
    return;
  }
  state.snapshotRefreshing = true;
  try {
    await loadProject(state.activeProject, { reconnectSocket: false });
  } finally {
    state.snapshotRefreshing = false;
  }
}

function updateLiveJobs(payload) {
  const jobs = payload.jobs || [];
  const events = payload.events || [];
  if (events.length > 0) {
    const event = events[0];
    const stage = [event.stage, event.event].filter(Boolean).join("/");
    const label = [event.job_id, stage, event.message].filter(Boolean).join(" · ");
    dom.statusLive.textContent = `Live: ${label}`;
    return;
  }
  if (jobs.length === 0) {
    dom.statusLive.textContent = "Live: no jobs";
    return;
  }
  const job = jobs[0];
  const label = [job.id, job.status, job.message].filter(Boolean).join(" · ");
  dom.statusLive.textContent = `Live: ${label}`;
}

function formatDelta(value) {
  if (value > 0) {
    return `+${value.toLocaleString()}`;
  }
  return value.toLocaleString();
}

function resize() {
  const width = dom.viewport.clientWidth;
  const height = Math.max(dom.viewport.clientHeight, 1);
  renderer.setSize(width, height);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate() {
  window.requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const map = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    };
    return map[char];
  });
}

function escapeAttribute(value) {
  return escapeHtml(value);
}
