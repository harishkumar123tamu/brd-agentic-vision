#!/bin/bash
#SBATCH --job-name=brd_clips
#SBATCH --time=00:45:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --output=logs/clips_%j.out
source $SCRATCH/brd/env.sh
python code/evidence_clips.py 3
