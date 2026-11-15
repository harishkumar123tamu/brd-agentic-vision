module purge
module load GCCcore/13.3.0 Python/3.12.3 FFmpeg
source $SCRATCH/brd/venv/bin/activate
cd $SCRATCH/brd
export HF_HOME=$SCRATCH/brd/hf
