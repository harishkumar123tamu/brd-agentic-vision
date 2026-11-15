#!/bin/bash
#SBATCH --job-name=brd_act
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --output=logs/act_%j.out
source $SCRATCH/brd/env.sh
python code/activity.py && python code/brd_risk.py
