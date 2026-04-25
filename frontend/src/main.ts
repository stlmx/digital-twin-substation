import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';
import * as THREE from 'three';
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader.js';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

type ProjectStatus = 'created' | 'queued' | 'running' | 'succeeded' | 'failed';

interface Project {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  status: ProjectStatus;
  image_count: number;
  artifacts: {
    splat_url?: string;
    splat_filename?: string;
    point_cloud_url?: string;
    point_cloud_filename?: string;
    point_count?: number;
  };
  error?: string | null;
}

let projects: Project[] = [];
let selectedProject: Project | null = null;
let viewer: any = null;
let pointCloudState: {
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  controlsCleanup: () => void;
  animationId: number;
} | null = null;

const app = document.querySelector<HTMLDivElement>('#app');
if (!app) throw new Error('Missing app root');

app.innerHTML = `
  <main class="shell">
    <section class="sidebar">
      <div class="brand">
        <span class="brand-mark"></span>
        <div>
          <h1>Substation Twin</h1>
          <p>三维重建任务台</p>
        </div>
      </div>

      <form id="upload-form" class="panel">
        <label>
          场景名称
          <input name="name" value="substation-scene" />
        </label>
        <label>
          图片集
          <input name="files" type="file" accept="image/*" multiple />
        </label>
        <div class="grid-2">
          <label>
            GPU
            <input name="gpu_ids" placeholder="0 或 0,1" />
          </label>
          <label>
            迭代
            <input name="max_num_iterations" type="number" value="30000" min="100" step="100" />
          </label>
        </div>
        <label>
          方法
          <select name="method">
            <option value="vggt-colmap">vggt-colmap</option>
            <option value="vggt-colmap-ba">vggt-colmap-ba</option>
            <option value="splatfacto">splatfacto</option>
            <option value="splatfacto-big">splatfacto-big</option>
          </select>
        </label>
        <button type="submit">启动重建</button>
      </form>

      <div class="section-head">
        <h2>项目</h2>
        <button id="refresh-button" class="ghost">刷新</button>
      </div>
      <div id="project-list" class="project-list"></div>
    </section>

    <section class="workspace">
      <header class="workspace-head">
        <div>
          <p class="eyebrow">Gaussian Splat Viewer</p>
          <h2 id="viewer-title">选择一个已完成项目</h2>
        </div>
        <span id="status-pill" class="status muted">idle</span>
      </header>
      <div id="viewer" class="viewer">
        <div class="empty">等待重建结果</div>
      </div>
      <div class="logs">
        <div class="section-head">
          <h2>流水线日志</h2>
          <button id="log-button" class="ghost">更新日志</button>
        </div>
        <pre id="log-output"></pre>
      </div>
    </section>
  </main>
`;

const uploadForm = document.querySelector<HTMLFormElement>('#upload-form')!;
const projectList = document.querySelector<HTMLDivElement>('#project-list')!;
const refreshButton = document.querySelector<HTMLButtonElement>('#refresh-button')!;
const logButton = document.querySelector<HTMLButtonElement>('#log-button')!;
const logOutput = document.querySelector<HTMLPreElement>('#log-output')!;
const viewerElement = document.querySelector<HTMLDivElement>('#viewer')!;
const viewerTitle = document.querySelector<HTMLHeadingElement>('#viewer-title')!;
const statusPill = document.querySelector<HTMLSpanElement>('#status-pill')!;

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

function artifactUrl(path: string): string {
  if (path.startsWith('http')) return path;
  return `${API_BASE}${path}`;
}

function statusClass(status: ProjectStatus): string {
  if (status === 'succeeded') return 'ok';
  if (status === 'failed') return 'bad';
  if (status === 'running' || status === 'queued') return 'active';
  return 'muted';
}

async function fetchProjects() {
  const response = await fetch(apiUrl('/api/projects'));
  projects = await response.json();
  renderProjects();
}

function renderProjects() {
  projectList.innerHTML = '';
  if (!projects.length) {
    projectList.innerHTML = '<div class="empty-list">还没有项目</div>';
    return;
  }

  for (const project of projects) {
    const item = document.createElement('button');
    item.className = `project-item ${selectedProject?.id === project.id ? 'selected' : ''}`;
    item.innerHTML = `
      <span>
        <strong>${project.name}</strong>
        <small>${project.image_count} images · ${new Date(project.updated_at).toLocaleString()}</small>
      </span>
      <em class="${statusClass(project.status)}">${project.status}</em>
    `;
    item.addEventListener('click', () => selectProject(project));
    projectList.appendChild(item);
  }
}

async function selectProject(project: Project) {
  selectedProject = project;
  renderProjects();
  viewerTitle.textContent = project.name;
  statusPill.textContent = project.status;
  statusPill.className = `status ${statusClass(project.status)}`;
  await fetchLogs();

  if (project.status === 'succeeded' && project.artifacts?.splat_url) {
    await loadSplat(artifactUrl(project.artifacts.splat_url));
  } else if (project.status === 'succeeded' && project.artifacts?.point_cloud_url) {
    await loadPointCloud(artifactUrl(project.artifacts.point_cloud_url));
  } else {
    resetViewer(project.error ?? '等待重建完成');
  }
}

function resetViewer(message: string) {
  if (pointCloudState) {
    cancelAnimationFrame(pointCloudState.animationId);
    pointCloudState.controlsCleanup();
    pointCloudState.renderer.dispose();
    pointCloudState = null;
  }
  if (viewer) {
    try {
      viewer.dispose?.();
    } catch {
      // The third-party viewer has different dispose behavior across versions.
    }
    viewer = null;
  }
  viewerElement.innerHTML = `<div class="empty">${message}</div>`;
}

async function loadSplat(url: string) {
  resetViewer('正在加载场景');
  viewerElement.innerHTML = '';

  viewer = new (GaussianSplats3D as any).Viewer({
    rootElement: viewerElement,
    cameraUp: [0, -1, -0.25],
    initialCameraPosition: [0, -8, 4],
    initialCameraLookAt: [0, 0, 0],
    gpuAcceleratedSort: true,
    sharedMemoryForWorkers: false
  });

  await viewer.addSplatScene(url, {
    progressiveLoad: true,
    splatAlphaRemovalThreshold: 5
  });
  viewer.start();
}

async function loadPointCloud(url: string) {
  resetViewer('正在加载点云');
  viewerElement.innerHTML = '';

  const width = viewerElement.clientWidth || 960;
  const height = viewerElement.clientHeight || 540;
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(width, height);
  renderer.setClearColor(0x111715, 1);
  viewerElement.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(60, width / height, 0.01, 10000);
  camera.position.set(0, -4, 2);

  const geometry = await new PLYLoader().loadAsync(url);
  geometry.computeBoundingSphere();
  geometry.computeVertexNormals();
  const material = new THREE.PointsMaterial({
    size: 0.02,
    vertexColors: geometry.hasAttribute('color'),
    color: geometry.hasAttribute('color') ? 0xffffff : 0xdfeae4,
    sizeAttenuation: true
  });
  const points = new THREE.Points(geometry, material);
  scene.add(points);

  const sphere = geometry.boundingSphere;
  if (sphere) {
    points.position.sub(sphere.center);
    camera.position.set(0, -Math.max(sphere.radius * 2.2, 2), Math.max(sphere.radius * 0.7, 1));
    camera.lookAt(0, 0, 0);
  }

  const cleanup = attachMouseOrbit(renderer.domElement, camera);
  const resizeObserver = new ResizeObserver(() => {
    const nextWidth = viewerElement.clientWidth || 960;
    const nextHeight = viewerElement.clientHeight || 540;
    camera.aspect = nextWidth / nextHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(nextWidth, nextHeight);
  });
  resizeObserver.observe(viewerElement);

  const animate = () => {
    const animationId = requestAnimationFrame(animate);
    if (pointCloudState) pointCloudState.animationId = animationId;
    renderer.render(scene, camera);
  };
  const animationId = requestAnimationFrame(animate);
  pointCloudState = {
    renderer,
    scene,
    camera,
    animationId,
    controlsCleanup: () => {
      resizeObserver.disconnect();
      cleanup();
    }
  };
}

function attachMouseOrbit(canvas: HTMLCanvasElement, camera: THREE.PerspectiveCamera) {
  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  let yaw = 0;
  let pitch = 0.35;
  let distance = camera.position.length();

  const updateCamera = () => {
    const x = distance * Math.cos(pitch) * Math.sin(yaw);
    const y = -distance * Math.cos(pitch) * Math.cos(yaw);
    const z = distance * Math.sin(pitch);
    camera.position.set(x, y, z);
    camera.lookAt(0, 0, 0);
  };

  const onPointerDown = (event: PointerEvent) => {
    dragging = true;
    lastX = event.clientX;
    lastY = event.clientY;
    canvas.setPointerCapture(event.pointerId);
  };
  const onPointerMove = (event: PointerEvent) => {
    if (!dragging) return;
    const dx = event.clientX - lastX;
    const dy = event.clientY - lastY;
    lastX = event.clientX;
    lastY = event.clientY;
    yaw -= dx * 0.006;
    pitch = Math.max(-1.3, Math.min(1.3, pitch + dy * 0.004));
    updateCamera();
  };
  const onPointerUp = () => {
    dragging = false;
  };
  const onWheel = (event: WheelEvent) => {
    event.preventDefault();
    distance = Math.max(0.2, distance * (event.deltaY > 0 ? 1.1 : 0.9));
    updateCamera();
  };

  canvas.addEventListener('pointerdown', onPointerDown);
  canvas.addEventListener('pointermove', onPointerMove);
  canvas.addEventListener('pointerup', onPointerUp);
  canvas.addEventListener('wheel', onWheel, { passive: false });
  updateCamera();

  return () => {
    canvas.removeEventListener('pointerdown', onPointerDown);
    canvas.removeEventListener('pointermove', onPointerMove);
    canvas.removeEventListener('pointerup', onPointerUp);
    canvas.removeEventListener('wheel', onWheel);
  };
}

async function fetchLogs() {
  if (!selectedProject) return;
  const response = await fetch(apiUrl(`/api/projects/${selectedProject.id}/logs`));
  const data = await response.json();
  logOutput.textContent = data.logs ?? '';
  logOutput.scrollTop = logOutput.scrollHeight;
}

uploadForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(uploadForm);
  const gpuIds = String(formData.get('gpu_ids') ?? '').trim();
  if (!gpuIds) formData.delete('gpu_ids');

  const response = await fetch(apiUrl('/api/projects'), {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    alert(error.detail ?? '上传失败');
    return;
  }

  const created = await response.json();
  await fetchProjects();
  const project = projects.find((item) => item.id === created.id);
  if (project) await selectProject(project);
});

refreshButton.addEventListener('click', fetchProjects);
logButton.addEventListener('click', fetchLogs);

setInterval(async () => {
  await fetchProjects();
  if (selectedProject) {
    const updated = projects.find((project) => project.id === selectedProject?.id);
    if (updated) {
      const changed = updated.status !== selectedProject.status || updated.artifacts?.splat_url !== selectedProject.artifacts?.splat_url;
      selectedProject = updated;
      statusPill.textContent = updated.status;
      statusPill.className = `status ${statusClass(updated.status)}`;
      await fetchLogs();
      if (changed && updated.status === 'succeeded' && updated.artifacts?.splat_url) {
        await loadSplat(artifactUrl(updated.artifacts.splat_url));
      } else if (changed && updated.status === 'succeeded' && updated.artifacts?.point_cloud_url) {
        await loadPointCloud(artifactUrl(updated.artifacts.point_cloud_url));
      }
    }
  }
}, 5000);

fetchProjects();
