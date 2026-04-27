#!/usr/bin/env bash
# Run a python script with tf_gpu conda env + CUDA pip wheels on LD_LIBRARY_PATH.
# Usage: ./run_gpu.sh train_efficientnet.py
set -euo pipefail

CONDA_ENV=/home/ntphoto/miniconda3/envs/tf_gpu
PY=$CONDA_ENV/bin/python
NVIDIA_ROOT=$CONDA_ENV/lib/python3.11/site-packages/nvidia

LD_PATH=""
for d in "$NVIDIA_ROOT"/*/lib; do
    LD_PATH="$LD_PATH:$d"
done
export LD_LIBRARY_PATH="${LD_PATH#:}${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

exec "$PY" -u "$@"
