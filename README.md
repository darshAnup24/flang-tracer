# Flang Multi-Stage Compilation Pipeline Tracer (FTrace)

## What is it?
FTrace is a tool that allows you to trace a single piece of Fortran source code completely across the Flang compiler's complex internal stages. It shows you what your source code looks like at the five different stages of compilation: Parse Tree, Semantics, HLFIR, FIR, and LLVM IR.

## Why is it used?
When engineers build the Flang compiler or developers debug performance issues with their Fortran code, they often need to know exactly how Fortran is translated into low-level machine instructions. Flang's compilation process is very complex, with 5 separate intermediate stages. Before this tool, developers had to manually dump out massive files for each stage and visually guess which line of code corresponded to which machine instruction.

**FTrace automates this matching process.** It guarantees that you can select a specific construct (like an Array Assignment) and instantly see bidirectional, line-by-line, correlated translations of that construct across all five stages of the compiler!

## How to use it?

### Command Line Interface
Run the fundamental trace directly from your terminal:
```bash
ftrace trace my_code.f90
```

To see only a specific stage calculation (e.g. only FIR):
```bash
ftrace show --stage fir
```

Want to generate an interactive HTML report to view in your browser?
```bash
ftrace export --format html
```

Need to see how an optimization change impacted the compilation of a specific piece of code? Diff it:
```bash
ftrace diff old_code.f90 new_code.f90 --construct C05
```

### Getting Started Example
1. Navigate to the examples tab: `cd examples/`
2. We have 10 standard testing cases. Run: `ftrace trace C01_array_assign.f90`
3. Observe how the arrays translate into LLVM execution blocks in the terminal!
