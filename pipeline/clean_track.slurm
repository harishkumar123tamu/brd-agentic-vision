#!/bin/bash
#SBATCH --job-name=brd_track
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=logs/track_%j.out
source $SCRATCH/brd/env.sh
python code/clean_track.py
