# Pipeline: reproduce all results from the raw video

All commands run on TAMU HPRC **Grace** (Slurm). Paths assume the project folder `$SCRATCH/brd`.

## 1. Environment

```bash
module purge
module load GCCcore/13.3.0 Python/3.12.3 FFmpeg          # Python 3.12.3, FFmpeg 7.0.2
python -m venv $SCRATCH/brd/venv && source $SCRATCH/brd/venv/bin/activate
pip install ultralytics==8.4.213 lap pandas pyarrow scipy opencv-python-headless tqdm \
            transformers accelerate qwen-vl-utils
export HF_HOME=$SCRATCH/brd/hf
python -c "from ultralytics import YOLO; YOLO('yolo11m.pt')"                       # detector weights
python -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen2.5-VL-7B-Instruct')"
```
`pipeline/env.sh` repeats the module + venv lines; `source` it after every login.

## 2. Data

The event video (Google Drive, *Agentic Computer Vision Hackathon Dataset*) is copied to the cluster with rclone
(read-only Drive access), on a data-transfer node:
```bash
rclone copy gdrive: $SCRATCH/brd/raw --drive-root-folder-id <dataset-folder-id> --transfers 8
find $SCRATCH/brd/raw -iname "*.avi" | sort > clips.txt          # 1,749 clips, 153 GB
```
Facts about the video that the pipeline relies on:
- 5-minute `.Avi` clips, 3 cameras x 2 days, midnight to midnight. Name = `Event` + start time `YYYYMMDDHHMMSS` + camera code.
- Camera codes: **003 = Cam 03 = Back cam (whole pen)**, **006 = Cam 01 = Front cam 1 (from the bunk down the pen)**,
  **017 = Cam 02 = Front cam 2 (bunk close-up)**. Cam 01/03: 4000x3000; Cam 02: 2592x1944; 30 fps; fisheye lenses; night = infrared.
- Video is HEVC with a non-standard codec tag (`GHEC`); every ffmpeg call forces the decoder: `ffmpeg -c:v hevc -i ...`.
- Keyframes every 2 s; detection uses keyframes only (one sample per 2 s = 30 per minute).

## 3. Run the pipeline (in order)

| # | Command | What it does | Output | Run time |
|---|---|---|---|---|
| 1 | `sbatch --gres=gpu:1 pipeline/detect.slurm` | YOLO11m on every keyframe (2000 px decode, 1280 px inference, animal classes, conf >= 0.15). Job array of 18 tasks x 100 clips; resumable | `out/det/*.parquet` (1,749 files) | ~1 h wall clock on A100/RTX/T4 GPUs |
| 2 | `sbatch pipeline/clean_track.slurm` | Keep cow-like classes conf >= 0.25, merge duplicate boxes (NMS), drop boxes outside our pen (`ground_truth/zones.json`), link boxes into per-camera tracks | `out/tracks_cam.parquet`, `out/track_summary.csv` | ~10 min CPU |
| 3 | `sbatch pipeline/cow_ids.slurm` | Closed-set tracker: exactly 10 cows (C01-C10) on Cam 03, Hungarian matching to 10 persistent slots, continuous across both days; logs possible ID-swap moments | `out/ids_cam03.parquet`, `out/id_events_cam03.csv` | ~5 min |
| 4 | `sbatch pipeline/link_bunk.slurm` | Carry Cam 03 IDs to Cam 01 / Cam 02 for cows at the feed bunk (order along the bunk, nearest frame within 2 s) | `out/ids_cam01.parquet`, `out/ids_cam02.parquet`, `out/link_summary.csv` | ~3 min |
| 5 | `sbatch pipeline/id_check.slurm` | ID-check frames every 30 min on each camera | `out/id_check/<cam>/*.jpg` (288) | ~10 min |
| 6 | `sbatch pipeline/activity.slurm` | Rule-based behavior per cow per minute (bunk / waterer zones, motion, perspective-corrected posture) -> bouts; time budgets; Level 2 features + BRD risk score | `out/activity.csv`, `out/activity_minutes.csv`, `out/time_budget.csv`, `out/brd_features.csv`, `out/brd_risk.csv` | ~5 min |
| 7 | `sbatch pipeline/evidence_clips.slurm` | 3 evidence clips (15 s, H.264, cow boxed) per top-3 risk cow | `out/clips/*.mp4`, `out/clips/index.csv` | ~2 min |
| 8 | `sbatch pipeline/agent.slurm` | Agentic VLM loop (plan -> tools -> answer -> self-check -> re-answer) on selected cow-minutes and ID-swap moments; saves full traces | `out/traces/<case>/trace.json`, `trace.md`, images | ~1 min per case on one A100 |

Helper scripts: `pipeline/draw_dets.py` (draw detections on frames), `pipeline/zones.json` (pen / feed bunk / waterer polygons,
drawn by hand on noon reference frames).

## 4. Models and versions

| Component | Model / tool | Version | Source / licence |
|---|---|---|---|
| Detector | YOLO11m, COCO-pretrained, used off-the-shelf (no fine-tuning) | ultralytics 8.4.213 | Ultralytics (public weights) |
| Vision-language model (agent) | Qwen2.5-VL-7B-Instruct, bf16 | via transformers | Hugging Face `Qwen/Qwen2.5-VL-7B-Instruct` (public) |
| Deep learning | PyTorch | 2.15.0 + CUDA 13.2 | |
| Matching | SciPy `linear_sum_assignment` (Hungarian) | 1.18.1 | |
| Video | FFmpeg | 7.0.2 | |
| Compute | TAMU HPRC Grace (A100 40 GB, RTX 6000, T4 GPUs; CPU nodes) | | |

## 5. Outside resources and AI tools
- Public pretrained models only (YOLO11m COCO weights, Qwen2.5-VL-7B-Instruct). No outside datasets.
- Event data stays private: no video or full frames are published; the repository holds code, tables, downsized ID-check frames and short evidence clips for the judges.
- AI assistance: an AI assistant (Claude, Anthropic) was used to help plan the work, write and debug pipeline code, and draft documentation. All results were run and checked by the team.

## 6. Observed vs estimated
- **Observed:** a cow box detected in a frame; a cow inside the bunk/waterer zone; frame-to-frame movement.
- **Estimated:** cow identity when cows were close together or hidden (`id_source` != `observed_continuous`); behavior in minutes with few observations; lying vs standing from box shape; all behavior in minutes where the cow was not visible (`other_not_visible`).
- `activity.csv` carries an `evidence` column (observed / estimated) per bout; ID files carry `id_source` and `id_conf`.
