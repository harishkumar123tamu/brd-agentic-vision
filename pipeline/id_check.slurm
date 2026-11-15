#!/bin/bash
#SBATCH --job-name=brd_idcheck
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --output=logs/idcheck_%j.out
source $SCRATCH/brd/env.sh
python code/id_check_frames.py
