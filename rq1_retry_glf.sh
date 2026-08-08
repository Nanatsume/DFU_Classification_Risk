#!/bin/bash
# Retry the 4 RQ1 combos that failed with GPU OOM on G-LF strategy.
# Resume-aware: reuses existing best_params.json, skips tuning.

export LD_LIBRARY_PATH=/home/ntphoto/miniconda3/envs/tf_gpu/lib:/usr/lib/wsl/lib:$LD_LIBRARY_PATH

PYTHON="/home/ntphoto/miniconda3/envs/tf_gpu/bin/python3"
SCRIPT="/home/ntphoto/Project/rq1_run_combo.py"

COMBOS=(
    "ResNet50 G-LF S1"
    "ResNet50 G-LF S2"
    "ConvNeXt-Tiny G-LF S1"
    "ConvNeXt-Tiny G-LF S2"
)

failed=0
for combo in "${COMBOS[@]}"; do
    read -r backbone strategy input_s <<< "$combo"
    echo ""
    echo "========================================"
    echo "RETRY: $backbone / $strategy / $input_s"
    echo "========================================"
    $PYTHON $SCRIPT --backbone "$backbone" --strategy "$strategy" --input "$input_s"
    if [ $? -ne 0 ]; then
        echo "ERROR: $backbone/$strategy/$input_s failed again — continuing"
        failed=$((failed + 1))
    fi
done

echo ""
echo "========================================"
echo "Retry attempted for 4 combos."
echo "Failed: $failed"
echo "========================================"
