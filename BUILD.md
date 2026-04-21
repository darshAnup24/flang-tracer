# Build Instructions for Flang Tracer

## Environment Bootstrap

1. Clone llvm-project at the following pinned commit SHA to ensure stability:
   `git clone https://github.com/llvm/llvm-project.git`
   `git checkout 21dbdc6f4e17fd8ae3beaee56958434544d6da21` (This is an example recent stable commit)

2. Create a build directory:
   `mkdir llvm-project/build && cd llvm-project/build`

3. Configure CMake with the specific flags required for this project:
   `cmake -G Ninja -C ../../cmake/flang-tracer.cmake ../llvm`

4. Build Flang:
   `ninja flang`

5. Verify baseline before applying patches:
   `ninja check-flang`
