# Flang Lowering Patterns Reference

This document serves as a Flang developer reference guide, documenting the lowering patterns of Fortran constructs discovered via the Flang Multi-Stage Compilation Pipeline Tracer.

## C01: Whole-array assignment

**Fortran Source:**
```fortran
A(:) = B(:) + C(:)
```

**Pattern Observations:**
- **Parse Tree:** Encoded as an `OmpMapClause` or generic assignment statement, depending on context, fundamentally an `AssignmentStmt` with a `Variable` expression mapped to `Designator`.
- **HLFIR:** In HLFIR, this doesn't explicitly emit a loop immediately! It creates an `hlfir.expr` representing the element-wise addition, and an `hlfir.assign` to assign the result.
- **FIR:** FIR expands this into a full scalarized `fir.do_loop` (array slice operations) with boundary conditions extracted via `fir.array_load` and `fir.array_merge_store`.
- **LLVM IR:** The `fir.do_loop` translates cleanly into LLVM IR `br` blocks. Metadata `!flang.srcrange` confirms its provenance perfectly to the exact line.

*(Other constructs will be detailed here)*
