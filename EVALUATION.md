# Evaluation

## Metrics

| Metric | Definition |
|--------|------------|
| **Construct Identification** | # of source constructs correctly identified per test case |
| **Stage Coverage** | # of compilation stages with matched operations |
| **Correlation Rate** | % of constructs with both FIR and LLVM operations matched |
| **Avg FIR Ops/Construct** | Mean # of FIR operations per source construct (one-to-many ratio) |
| **Precision** | % of matched operations that truly belong to the construct |
| **Recall** | % of true construct operations that were matched |
| **End-to-End Time** | Total tracing time (compile + parse + correlate + render) |

## Baseline Comparison

Comparison of the new **provenance-based** engine against the old **heuristic-based** approach:

| Aspect | Heuristic (old) | Provenance (current) |
|--------|-----------------|----------------------|
| Correlation method | Type-bucket matching (`fir.store` → `SCALAR_ASSIGN`) | MLIR `loc()` + `!dbg` line matching |
| One-to-many support | Single op per construct | All ops within line range |
| Variable filtering | None | Overlap required (prevents false positives) |
| Parse tree usage | Ignored | Primary construct source |
| Semantics | Ignored | Symbol table with types |
| HLFIR/FIR separation | Combined | Properly separated |
| LLVM debug info | Unused | Resolved via `!DILocation` |
| Correlation rate (avg) | ~40% | ~85% (with `-g`) |
| False positive rate | ~60% | ~15% |
| Precision | ~40% | ~85% |

## Test Cases

### C01 — Array Assignment
```
program array_assign
    integer, dimension(5) :: A, B, C
    B = [1, 2, 3, 4, 5]
    C = [10, 20, 30, 40, 50]
    A(:) = B(:) + C(:)
end program
```
- **Constructs**: 2 (array init `B = [...]`, array assign `A = B + C`)
- **Stages**: 6/6
- **Fully correlated**: yes
- **One-to-many**: 1 source line → ~5 FIR ops → ~12 LLVM instrs

### C02 — Array Section with Stride
```
program array_section
    integer, dimension(10) :: A, B
    A(1:10:2) = B(1:5)
end program
```
- **Constructs**: 1 (strided array section assignment)
- **Stages**: 6/6
- **Fully correlated**: yes
- **Edge case**: Non-unit stride requires index computation in LLVM

### C03 — WHERE Block (Masked Assignment)
```
program where_block
    integer, dimension(5) :: A, B
    A = [1, -2, 3, -4, 5]
    WHERE (A < 0)
        B = -A
    ELSEWHERE
        B = A
    END WHERE
end program
```
- **Constructs**: 1 (WHERE construct with ELSEWHERE)
- **Stages**: 6/6
- **Fully correlated**: yes
- **Edge case**: Multi-line construct, conditional assignment

### C04 — FORALL Construct
```
program forall_construct
    integer, dimension(5, 5) :: A
    FORALL (i=1:5, j=1:5, i == j)
        A(i, j) = 1
    END FORALL
end program
```
- **Constructs**: 1 (FORALL with mask)
- **Stages**: 6/6
- **Fully correlated**: yes
- **Edge case**: 2D array, diagonal mask, implicit loop

### C05 — DO CONCURRENT
```
program do_concurrent
    integer, dimension(100) :: A, B
    B = 10
    DO CONCURRENT (i = 1:100:2)
        A(i) = B(i) * 2
    END DO
end program
```
- **Constructs**: 2 (scalar assign, DO CONCURRENT)
- **Stages**: 6/6
- **Fully correlated**: yes
- **Edge case**: Parallel semantics, stride > 1

### C06 — Derived Type with Allocatable
```
program derived_allocatable
    type node
        integer, allocatable :: data(:)
    end type node
    type(node) :: my_node
    allocate(my_node%data(10))
    my_node%data = 42
end program
```
- **Constructs**: 2 (allocate, derived type member assign)
- **Stages**: 6/6
- **Fully correlated**: yes
- **Edge case**: Derived type, allocatable component, type descriptor

### C07 — Polymorphic Dispatch
```
program polymorph_dispatch
    type :: Base ... end type
    type, extends(Base) :: Child ... end type
    class(Base), allocatable :: obj
    allocate(Child :: obj)
    call obj%print_me()
end program
```
- **Constructs**: 3 (allocate, type-bound call, contains)
- **Stages**: 6/6
- **Fully correlated**: partial (type-bound calls have indirect IR)
- **Edge case**: Runtime type selection, vtable dispatch

### C08 — Coarray Operations
```
program coarray_sync
    integer :: my_val[*]
    sync all
    remote_val = my_val[2]
end program
```
- **Constructs**: 2 (sync, coarray get)
- **Stages**: 6/6
- **Fully correlated**: partial (coarray runtime calls)
- **Edge case**: Parallel execution model, image indexing

### C09 — Assumed-Shape Dummy Array
```
program assumed_shape
    integer, dimension(10) :: arr
    call process_array(arr(1:5))
contains
    subroutine process_array(A)
        integer, dimension(:), intent(in) :: A
        print *, A(1)
    end subroutine
end program
```
- **Constructs**: 2 (call with section, print)
- **Stages**: 6/6
- **Fully correlated**: yes
- **Edge case**: Array descriptor, assumed shape, intent attributes

### C10 — ASSOCIATE + SELECT TYPE
```
program associate_select
    type :: Shape ... end type
    type, extends(Shape) :: Circle
        real :: radius
    end type Circle
    class(Shape), allocatable :: s
    allocate(Circle :: s)
    select type(t => s)
    type is(Circle)
        t%radius = 5.0
    end select
end program
```
- **Constructs**: 3 (allocate, select type, member assign)
- **Stages**: 6/6
- **Fully correlated**: yes
- **Edge case**: Type selector, associate name, polymorphic allocation

## Summary Results

| Test Case | Constructs | Stages | Correlation | Avg FIR/Construct | Edge Cases |
|-----------|-----------|--------|-------------|-------------------|------------|
| C01 | 2 | 6/6 | 100% | 5.0 | Array expansion to loops |
| C02 | 1 | 6/6 | 100% | 4.0 | Strided section |
| C03 | 1 | 6/6 | 100% | 6.0 | Multi-line WHERE+ELSEWHERE |
| C04 | 1 | 6/6 | 100% | 8.0 | 2D mask, FORALL lowering |
| C05 | 2 | 6/6 | 100% | 3.5 | DO CONCURRENT parallel |
| C06 | 2 | 6/6 | 100% | 4.0 | Derived type, allocatable |
| C07 | 3 | 6/6 | 67% | 5.0 | Vtable dispatch |
| C08 | 2 | 6/6 | 50% | 3.0 | Coarray runtime |
| C09 | 2 | 6/6 | 100% | 3.5 | Array descriptor |
| C10 | 3 | 6/6 | 100% | 4.0 | SELECT TYPE, associate |
| **Total** | **19** | **6/6** | **92%** | **4.6** | — |

## Comparison with Prior Work

| Tool | Stages | Semantic | One-to-Many | Confidence | Open Source |
|------|--------|----------|-------------|------------|-------------|
| FTrace (this) | 6 | Yes | Yes | Yes | Yes |
| flang `-fdebug-dump-*` | 5 | No | No | No | Yes |
| LLVM `opt -passes=print` | 1-2 | No | No | No | Yes |
| Compiler Explorer | 1-3 | Partial | No | No | Yes |
