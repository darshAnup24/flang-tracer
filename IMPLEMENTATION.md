# Implementation (LLVM Details)

## Flang Compiler Invocation

The `CompilerInterface` class (`ftrace/compiler_interface.py`) invokes `flang` (or `flang-new`) with stage-specific flags:

| Stage | Flag | Output |
|-------|------|--------|
| Parse Tree | `-fc1 -fdebug-dump-parse-tree` | AST text walk with indented construct nodes |
| Semantics | `-fc1 -fdebug-dump-symbols` | Symbol table with types and scopes |
| HLFIR | `-fc1 -O0 -emit-hlfir` | High-Level FIR MLIR text |
| FIR | `-fc1 -O0 -emit-fir` | Lowered FIR MLIR text |
| LLVM IR | `-fc1 -O0 -emit-llvm` | LLVM IR text (with `!dbg` when `-g` used) |

The `-fc1` flag runs the Flang frontend only (no linking). `-O0` prevents optimization from obscuring line-level provenance.

## MLIR Location Tracking

### HLFIR / FIR (`loc()` attributes)

MLIR operations carry optional `loc()` attributes:

```mlir
%0 = fir.load %1 : !fir.ref<i32> loc("input.f90":12:5)
```

The parsers extract these with regex and convert them to integer source lines:

```python
_LOC_PAT = re.compile(r'loc\(["\'].*?["\']?\s*:(\d+)\s*:\s*(\d+)\)')
```

When available, these provide exact line-column provenance for every IR operation.

## LLVM IR Debug Metadata Resolution

The `LLVMParser` resolves `!dbg` references in two passes:

### Pass 1: Build DILocation Map

Scans all lines for `!DILocation` metadata records:

```llvm
!42 = !DILocation(line: 12, column: 5, scope: !7)
```

Stores in `self._dilocn: Dict[str, Dict]` mapping `"42"` → `{line: 12, column: 5}`.

### Pass 2: Resolve Instructions

For each LLVM instruction with a `!dbg !N` reference, looks up the DILocation record:

```python
m_dbg = self._DBG_REF_PAT.search(stripped)
if m_dbg:
    ref = m_dbg.group(1)
    if ref in self._dilocn:
        src_line = self._dilocn[ref]['line']
```

This produces instructions annotated with their original source line:

```python
{
    'line': '%val = load i32, i32* %ptr, !dbg !42',
    'src_line': 12,
    'src_col': 5,
    'debug_loc': '12:5',
}
```

## One-to-Many Mapping

The key challenge: a single Fortran source line (e.g., `A(:) = B(:) + C(:)`) expands to many FIR operations and many more LLVM instructions.

FTrace handles this by grouping all IR operations whose `loc()` (or `!dbg`) line falls within the construct's source line range:

```python
def _find_fir(self, c: ConstructID) -> List[IROperation]:
    start, end = c.line_range
    by_loc = [op for op in self.fir_ops
              if op.src_line and start <= op.src_line <= end]
    return by_loc
```

This naturally produces the correct one-to-many mapping without heuristics.

## Parse Tree Source Resolution

The `ParseTreeParser` resolves AST node text back to source lines using graduated matching:

1. **MLIR `loc()` attribute** (from parse tree dump) — exact if available.
2. **Exact substring match** — normalized construct text matched against normalized source lines.
3. **Token-based best match** — Jaccard-like token overlap score (threshold: 0.5).
4. **Fallback** — `(0, 0)` range, construct is dropped.

## Symbol Table Extraction

The `SemanticsParser` parses `-fdebug-dump-symbols` output using scope-detection regex:

```python
_SCOPE_PAT  = re.compile(r'^(\w[\w\s]*):\s*$')
_SYMBOL_PAT = re.compile(r'^\s{2,}(\w+)\s*:\s*([\w\s*()]+?)(?:\s*,\s*(.*))?$')
```

Each symbol is classified as VARIABLE, ARRAY, DERIVED, or PARAMETER based on type string patterns.

## SSA Def-Use Chain Tracking

The `FIRStructuralAnalyzer` and `SSATracker` build def-use maps for FIR and LLVM respectively:

```python
# FIR SSA graph
self.ssa_def_map: Dict[str, IROperation]   # %val → defining op
self.ssa_use_map: Dict[str, List[IROperation]]  # %val → using ops
```

This enables limited SSA chain tracing for the HLFIR-anchored correlation engine.

## Correlation Statistics

After correlation, the engine computes:

- **Total constructs**: Number of source constructs identified
- **Fully correlated**: Constructs with both FIR and LLVM operations matched
- **Correlation rate**: `fully_correlated / total * 100`
- **Avg FIR ops/construct**: Total matched FIR ops / total constructs
