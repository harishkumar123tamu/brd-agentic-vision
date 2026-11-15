#!/bin/bash
#SBATCH --job-name=brd_ids
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=logs/ids_%j.out
source $SCRATCH/brd/env.sh
python code/cow_ids.py "Cam 03"
