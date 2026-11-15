#!/bin/bash
#SBATCH --job-name=brd_det
#SBATCH --time=02:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --gres=gpu:a100:1
#SBATCH --output=logs/det_%A_%a.out
#SBATCH --array=0-17

# 1749 clips / 100 per task = 18 tasks (0-17). Each task skips clips already done.
module purge
module load GCCcore/13.3.0 Python/3.12.3 FFmpeg
source $SCRATCH/brd/venv/bin/activate
cd $SCRATCH/brd
N=${N:-100}
python code/detect.py clips.txt $((SLURM_ARRAY_TASK_ID * N)) $N out/det
