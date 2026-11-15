#!/bin/bash
#SBATCH --job-name=brd_link
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=logs/link_%j.out
source $SCRATCH/brd/env.sh
python code/link_bunk.py
