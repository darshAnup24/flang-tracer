# Troubleshooting Guide

1. **Test Failure on Stage 0**
   If `pytest tests/test_stage0.py` fails, ensure that your `flang-new --ftrace-pipeline` output correctly generates `stage0.pt.json` and places it in the expected directory.

2. **Metadata Loss in LLVM IR**
   If correlation coverage drops below 85% in Phase 3, it's likely MLIR stripped `loc()` attributes during the FIR to LLVM translation. Check if `FIRToLLVMPass` correctly applied `!flang.srcrange`.

3. **1-to-N Splitting Issues**
   If a WHERE block is tracing to too few HLFIR operations, check the grouping logic in `ftrace/engine.py`. It should group by the common `!flang.construct_id` attribute.
