# Design

## Approach

FTrace uses a **provenance-based semantic correlation** architecture to trace Fortran source constructs through Flang's six compilation stages:

```
Source → Parse Tree → Semantics → HLFIR → FIR → LLVM IR
```

### Core Strategy

1. **Stage-Specific Parsers** — Each stage's raw text dump is parsed into structured data:
   - `ParseTreeParser` — Extracts AST node types (`AssignmentStmt`, `DoConstruct`, etc.) and their source text from `-fdebug-dump-parse-tree` output.
   - `SemanticsParser` — Extracts symbol table entries (name, type, kind, scope) from `-fdebug-dump-symbols`.
   - `HLFIRParser` / `FIRParser` — Extract MLIR operations with `loc()` line/column attributes.
   - `LLVMParser` — Extracts LLVM instructions and resolves `!dbg !N` references against `!DILocation` metadata.

2. **Construct Identity System** — Each source construct receives a stable SHA-256 hash derived from its kind, line range, variables, and operators. This ID propagates through all stages for reliable correlation.

3. **Provenance-Based Correlation** — The `ProvenanceCorrelationEngine` maps each construct to its corresponding operations at every stage using:
   - **Primary**: MLIR `loc()` attributes and LLVM `!dbg` metadata matching the construct's source line range. This is the only correct one-to-many mapping — every FIR/LLVM operation lowered from a construct's source lines is included.
   - **Fallback**: Variable-name overlap heuristics when `-g` debug info is absent.

4. **HLFIR Anchoring** — An optional `HLFIRAnchoredCorrelationEngine` uses HLFIR operations as semantic anchors, extracts FIR subgraphs via SSA def-use chains, and traces LLVM value chains for confidence scoring.

### Pipeline Flow

```
Fortran Source
     │
     ▼
┌─────────────┐     ┌──────────────────┐
│  Compiler   │────▶│  Stage Parsers   │
│  Interface  │     │  (5 parsers)     │
└─────────────┘     └──────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Construct   │
                    │  Identifier  │
                    └──────────────┘
                           │
                           ▼
                    ┌──────────────────┐
                    │  Provenance      │
                    │  Correlation     │
                    └──────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │   Renderer   │
                    │ (HTML/JSON/  │
                    │   Text)      │
                    └──────────────┘
```

## Alternatives Considered

### 1. Simple Text-Based Correlation (Rejected)
- **Approach**: Grep for identical source text across stage dumps.
- **Why rejected**: Misses constructs that expand to multiple operations (one-to-many). Cannot distinguish between different constructs with similar text. No semantic awareness.

### 2. Line-Number-Only Correlation (Rejected)
- **Approach**: Match constructs to IR ops by source line number alone.
- **Why rejected**: Fails when the compiler doesn't emit debug location metadata (`-g` required). Multiple constructs can share the same line range. Cannot correlate constructs spanning multiple lines.

### 3. Type-Bucket Heuristics (Used as fallback)
- **Approach**: Map construct kinds to expected FIR operation types (e.g., `ARRAY_ASSIGN` → `fir.store`, `fir.load`, `fir.array_coor`).
- **Why used**: As a fallback when `-g` is absent, but refined to filter by variable name overlap to avoid the "same FIR for all" bug.

### 4. HLFIR-Anchored Correlation (Current)
- **Approach**: Use HLFIR operations as semantic anchors that preserve high-level construct structure, then extract FIR subgraphs and LLVM SSA chains.
- **Why chosen**: HLFIR preserves more semantic information than FIR. FIR includes one-to-many expansion which is the primary correlation challenge. This approach provides the most accurate correlation with confidence scoring.

### 5. MLIR Debug Info Metadata (Current)
- **Approach**: Parse MLIR `loc()` attributes and LLVM `!DILocation` metadata for exact line-column provenance.
- **Why chosen**: When `-g` is available, this provides pixel-perfect line-level correlation without heuristics.
