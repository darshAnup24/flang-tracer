# Flang Multi-Stage Compilation Pipeline Tracer (FTrace)

## What is it?
FTrace is a tool that allows you to trace a single piece of Fortran source code completely across the Flang compiler's complex internal stages. It shows you what your source code looks like at the five different stages of compilation: Parse Tree, Semantics, HLFIR, FIR, and LLVM IR.

📝 **Compiler Design Theory:** For a full academic breakdown explaining how concepts like ASTs, Symbol Tables, Intermediate Representations, and Lowering work under the hood here, please refer to our [Compiler Design Concepts Guide](docs/compiler_design_concepts.md).

## Why is it used?
When engineers build the Flang compiler or developers debug performance issues with their Fortran code, they often need to know exactly how Fortran is translated into low-level machine instructions. Flang's compilation process is very complex, with 5 separate intermediate stages. Before this tool, developers had to manually dump out massive files for each stage and visually guess which line of code corresponded to which machine instruction.

**FTrace automates this matching process.** It guarantees that you can select a specific construct (like an Array Assignment) and instantly see bidirectional, line-by-line, correlated translations of that construct across all five stages of the compiler!

## How to use it?

### Interactive Web Application (New!)
FTrace now comes with a beautiful, fully-interactive Web Interface. It provides a frosted-glass Dark Mode dashboard allowing you to paste Fortran code and visually experience pipeline mappings!
To launch the Web Dashboard locally:
```bash
# Starting from the flang-tracer/ folder
source venv/bin/activate
python3 web/app.py
```
*Next, open the provided `http://127.0.0.1:8080/` link in your browser.*

### Command Line Interface (CLI)
You can also run the fundamental trace natively from your terminal setup:

```bash
# Make sure to run inside the virtual environment!
./venv/bin/ftrace trace my_code.f90
```

To see only a specific stage calculation (e.g. only FIR):
```bash
./venv/bin/ftrace show --stage fir
```

Want to generate an interactive HTML report locally instead of launching the web-app?
```bash
./venv/bin/ftrace export --format html
```

Need to see how an optimization change impacted the compilation of a specific piece of code? Diff it:
```bash
./venv/bin/ftrace diff old_code.f90 new_code.f90 --construct C05
```

### Getting Started Fast
1. Navigate to your project folder: `cd flang-tracer/`
2. We have 10 standard testing models locally at `examples/`
3. Hit the Web App: `python3 web/app.py`
4. Copy the code directly from `examples/C01_array_assign.f90` and run the Trace Engine!
