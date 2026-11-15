#!/bin/bash
#SBATCH --job-name=brd_agent
#SBATCH --time=01:00:00
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --gres=gpu:a100:1
#SBATCH --output=logs/agent_%j.out
source $SCRATCH/brd/env.sh
export HF_HUB_OFFLINE=1
python code/agent.py ${N:-8}
