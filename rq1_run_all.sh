#!/bin/bash
# Run all 48 RQ1 combinations sequentially.
# Resume-safe: completed combos (metrics.json exists) are skipped automatically.
#
# Usage:
#   bash run_all_rq1.sh
#   bash run_all_rq1.sh 2>&1 | tee run_all_rq1.log

export LD_LIBRARY_PATH=/home/ntphoto/miniconda3/envs/tf_gpu/lib:/usr/lib/wsl/lib:$LD_LIBRARY_PATH

PYTHON="/home/ntphoto/miniconda3/envs/tf_gpu/bin/python3"
SCRIPT="/home/ntphoto/Project/rq1_run_combo.py"

BACKBONES=("EfficientNetB0" "ResNet50" "ConvNeXt-Tiny")
STRATEGIES=("FT" "LP" "G-LF" "G-FL" "LP-FT" "L1-SP" "L2-SP" "Auto-RGN")
INPUTS=("S1" "S2")

total=0
failed=0

for backbone in "${BACKBONES[@]}"; do
    for strategy in "${STRATEGIES[@]}"; do
        for input_s in "${INPUTS[@]}"; do
            total=$((total + 1))
            echo ""
            echo "========================================"
            echo "[$total/48]  $backbone / $strategy / $input_s"
            echo "========================================"
            $PYTHON $SCRIPT --backbone "$backbone" --strategy "$strategy" --input "$input_s"
            if [ $? -ne 0 ]; then
                echo "ERROR: $backbone/$strategy/$input_s failed — continuing"
                failed=$((failed + 1))
            fi
        done
    done
done

echo ""
echo "========================================"
echo "All 48 combinations attempted."
echo "Failed: $failed"
echo "========================================"
