# Compiler Design (CD) Concepts in Flang Tracer

The **Flang Multi-Stage Compilation Pipeline Tracer (FTrace)** acts as a powerful lens into the inner workings of a modern, multi-tier compiler. When running Fortran code (`.f90`) through the Flang compiler, it undergoes massive structural transformations before becoming executable machine code. 

FTrace isolates and correlates the compilation timeline. Below is an explanation of the core Compiler Design (CD) concepts demonstrated through this interactive tool.

---

## 1. Syntax Analysis & The Parse Tree (Stage 0)
**CD Concept: Abstract Syntax Trees (AST)**  
In Compiler Design, after Lexical Analysis (tokenization) finishes, the compiler performs Syntax Analysis mapping tokens to grammar rules. 

**How it's used in FTrace:**
The initial `Parse Tree` pane represents Flang's immediate structural interpretation of your Fortran code. It visually demonstrates how a single line chunk like an array assignment (`A = B + C`) is packaged into recursive parsing nodes like `AssignmentStmt(Variable, Expr)`. FTrace uses this stage to generate the universal `SourceLocKey` hash (capturing the line and column range), acting as the fundamental anchor point for tracking this instruction across all deeper compilation phases.

## 2. Semantic Analysis & Symbol Tables (Stage 1)
**CD Concept: Type Checking, Binding, and Symbol Environments**  
Syntax Analysis ensures code is grammatically correct, but Semantic Analysis checks if it makes logical sense (e.g., verifying you aren't adding an integer to a memory reference improperly).

**How it's used in FTrace:**
The **Semantics** pane exposes the compiler’s Symbol Table structure. Where Stage 0 just sees variable placeholder `A`, the decorated semantic extraction accurately binds variable types (e.g., `Type: Array(Int32)`). Compilers use this state to finalize memory footprint definitions and scoping rules before lowering code to IR formats.

## 3. High-Level Intermediate Representation (Stage 2: HLFIR)
**CD Concept: High-Level IR optimization mapping**  
Instead of jumping directly from Source Code to Machine Code, modern compilers process languages through an Intermediate Representation (IR). 

**How it's used in FTrace:**
FTrace isolates **HLFIR (High-Level Fortran IR)** representations. Traditional IRs destroy high-level semantics (like understanding what an `Array` is natively). HLFIR preserves Fortran operations explicitly so optimization passes can perform domain-specific performance boosts before the logic is fully decomposed into scalar bounds.

## 4. Low-Level Intermediate Representation (Stage 3 & 4: FIR & LLVM IR)
**CD Concept: Lowering and Code Generation (Code-Gen)**  
Lowering is the process of breaking down complex high-level structures into repetitive, simple low-level primitives (such as unrolling loops and defining rigid memory buffers).

**How it's used in FTrace:**
The progression from **FIR (Fortran IR)** to **LLVM IR** demonstrates pure Translation and Code Generation principles.
1. FTrace captures FIR actively scaling a single line of Fortran into expansive `fir.do_loop` control flows. 
2. FTrace then leverages our custom LLVM architectural patch to inject `!flang.srcrange` Metadata. This proves that you can track the exact mapping of an abstract loop mechanism directly downward into assembly-ready `br label %loop.body` constructs.

## 5. Reverse Pass Correlation Mapping
**CD Concept: Source-Level Debugging via Metadata**  
One of the hardest domains in CD is matching an optimized low-level machine instruction back to the user's high-level file to throw accurate errors or debugger flags. 

**How it's used in FTrace:**
This tool acts as a reverse metadata mapper. The Python Correlation Engine proves that despite 1 line of source code splitting into 50+ lines of optimized intermediate operations (referred to as a **1-to-N Expansion Ratio** architecture problem), keeping a constant `SourceLocKey` hash preserved explicitly over MLIR translation dialects enables 100% accurate backwards-correlation across five entirely different compiler dialect topologies.
