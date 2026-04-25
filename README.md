# Substation Twin Reconstruction

面向变电站智能巡检的三维场景重建原型系统。第一阶段聚焦：

- 上传变电站照片或视频抽帧后的图片集；
- 在服务器端优先调用 VGGT 这类前馈式 3D foundation model 做几何重建；
- 导出 COLMAP 重建结果和浏览器可查看的 `.ply` 点云；
- 可选再接 Nerfstudio Splatfacto 做 3DGS 精修；
- 在浏览器中进行交互式三维查看。

后续模块会在这个基础上叠加设备语义对象、可交互操作、规程知识库和巡检智能体。

## Architecture

```text
Browser UI
  - upload images
  - watch reconstruction logs
  - view exported Gaussian Splat
        |
        v
FastAPI backend
  - project/job management
  - image storage
  - pipeline orchestration
        |
        v
VGGT / COLMAP / optional Nerfstudio
  - feed-forward camera/depth/point prediction
  - COLMAP-style export
  - optional splatfacto refinement
```

## Server Setup: Feed-Forward VGGT First

Recommended for your 8x4090 server:

```bash
bash scripts/setup_server_vggt.sh
```

The default method is `vggt-colmap`: it does not train a scene-specific 3DGS model. It calls VGGT as a feed-forward geometry foundation model, exports COLMAP-style reconstruction files, converts `points3D.bin` to browser-viewable `points.ply`, then serves the result in the web UI.

The setup script uses a HuggingFace mirror by default:

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

You can override it before running the script if your server uses another mirror.
It also preloads `facebook/VGGT-1B` through `huggingface_hub.snapshot_download`. To skip this step:

```bash
SUBTWIN_PRELOAD_VGGT=0 bash scripts/setup_server_vggt.sh
```

## Run

Backend:

```bash
bash scripts/start_backend.sh
```

Frontend:

```bash
bash scripts/start_frontend.sh http://YOUR_SERVER_IP:8000
```

Open:

```text
http://YOUR_SERVER_IP:5173
```

## Run Beijing Substation Images on Server

After copying this repository and the `变电站图像/北京变电站` folder to your server:

```bash
source .venv/bin/activate
export SUBTWIN_DATA_DIR=/data/substation-twin
export SUBTWIN_VGGT_REPO=$PWD/third_party/vggt
export SUBTWIN_PYTHON_BIN=$PWD/.venv/bin/python
export HF_ENDPOINT=https://hf-mirror.com

python scripts/import_and_run.py "变电站图像/北京变电站" \
  --name beijing-substation-room \
  --method vggt-colmap \
  --gpu-ids 0
```

Then start the backend/frontend and open the generated project in the browser.

If you want VGGT to run bundle adjustment after the feed-forward prediction, use:

```bash
python scripts/import_and_run.py "变电站图像/北京变电站" \
  --name beijing-substation-room-ba \
  --method vggt-colmap-ba \
  --gpu-ids 0
```

## Capture Tips

For a convincing substation scene, prefer a short walking or UAV video and extract frames, or capture 50-300 photos:

- cover the same equipment from multiple angles;
- avoid large exposure changes;
- keep overlap between adjacent views;
- include stable background structure;
- avoid heavy motion blur and reflective close-ups.

With only a few photos, the system can generate a partial scene, but invisible backsides and occluded equipment need later semantic asset completion.

## References

- VGGT official repository: https://github.com/facebookresearch/vggt
- Nerfstudio Splatfacto documents `ns-train splatfacto --data <data>` and `ns-export gaussian-splat`: https://docs.nerf.studio/nerfology/methods/splat.html
- COLMAP command-line reconstruction workflow: https://colmap.github.io/cli.html
- Three.js GaussianSplats3D browser viewer: https://github.com/mkkellogg/GaussianSplats3D
