"""
Compiler interface: runs flang with the right flags and captures stage dumps.
"""

import subprocess
import os
import logging
import tempfile
from typing import Dict

logger = logging.getLogger(__name__)


class FlangNotFoundError(Exception):
    pass


class CompilerInterface:

    # Flang candidates ordered by preference (newest first).
    # The Fedora package installs plain 'flang' (LLVM 21).
    _CANDIDATES = [
        'flang',
        'flang-new',
        '/usr/bin/flang',
        '/usr/bin/flang-new',
        '/usr/lib/llvm-18/bin/flang-new',
        '/usr/lib/llvm-17/bin/flang-new',
    ]

    def __init__(self):
        self.flang_path = self._find_flang()
        self.temp_dir = tempfile.mkdtemp(prefix='ftrace_')
        logger.info(f"Using Flang: {self.flang_path}")

    @classmethod
    def _find_flang(cls) -> str:
        for c in cls._CANDIDATES:
            try:
                r = subprocess.run([c, '--version'], capture_output=True, timeout=5)
                if r.returncode == 0:
                    logger.info(f"Found flang at: {c}")
                    return c
            except Exception:
                continue
        raise FlangNotFoundError(
            "No flang compiler found. Install with: sudo dnf install -y flang"
        )

    def compile_to_stages(self, code: str) -> Dict[str, str]:
        src = os.path.join(self.temp_dir, 'input.f90')
        with open(src, 'w') as f:
            f.write(code)

        stages = {}
        stages['parse_tree'] = self._extract_parse_tree(src)
        stages['semantics'] = self._extract_semantics(src)
        stages['hlfir'] = self._extract_hlfir(src)
        stages['fir'] = self._extract_fir(src)
        stages['llvm_ir'] = self._extract_llvm_ir(src)
        return stages

    def _run(self, args, merge_stderr=True):
        """Run a command and return its output. Returns empty string on error."""
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=30)
            out = r.stdout
            if merge_stderr:
                out = out + r.stderr
            if r.returncode != 0:
                logger.warning(f"Compiler returned {r.returncode}: {' '.join(args)}")
                logger.debug(f"stderr: {r.stderr[:500]}")
            return out
        except subprocess.TimeoutExpired:
            logger.error(f"Compiler timed out: {' '.join(args)}")
            return ""
        except Exception as e:
            logger.error(f"Compiler error: {e}")
            return ""

    def _extract_parse_tree(self, src: str) -> str:
        """Dump the Flang parse tree.  Output goes to stdout/stderr."""
        return self._run([
            self.flang_path, '-fc1',
            '-fdebug-dump-parse-tree',
            src
        ])

    def _extract_semantics(self, src: str) -> str:
        """Dump the Flang symbol table after semantic analysis."""
        return self._run([
            self.flang_path, '-fc1',
            '-fdebug-dump-symbols',
            src
        ])

    def _extract_hlfir(self, src: str) -> str:
        """Emit HLFIR (High-Level FIR)."""
        out = os.path.join(self.temp_dir, 'out.hlfir')
        self._run([
            self.flang_path, '-fc1', '-O0',
            '-emit-hlfir',
            src, '-o', out
        ])
        if os.path.exists(out):
            return open(out).read()
        # Some flang builds write to stdout
        return self._run([self.flang_path, '-fc1', '-O0',
                          '-emit-hlfir', src])

    def _extract_fir(self, src: str) -> str:
        """Emit FIR (lowered MLIR)."""
        out = os.path.join(self.temp_dir, 'out.fir')
        self._run([
            self.flang_path, '-fc1', '-O0',
            '-emit-fir',
            src, '-o', out
        ])
        if os.path.exists(out):
            return open(out).read()
        return self._run([self.flang_path, '-fc1', '-O0',
                          '-emit-fir', src])

    def _extract_llvm_ir(self, src: str) -> str:
        """Emit LLVM IR."""
        out = os.path.join(self.temp_dir, 'out.ll')
        self._run([
            self.flang_path, '-fc1', '-O0',
            '-emit-llvm',
            src, '-o', out
        ])
        if os.path.exists(out):
            return open(out).read()
        return self._run([self.flang_path, '-fc1', '-O0',
                          '-emit-llvm', src])


# ---------------------------------------------------------------------------
# Legacy shims kept for backward compatibility
# ---------------------------------------------------------------------------

class IRParser:
    @staticmethod
    def parse_fortran_construct(line: str):
        l = line.strip().lower()
        if ' = ' in l and not any(x in l for x in ['if', 'do', 'where']):
            return 'SCALAR_ASSIGN'
        return None


class SourceLocationCorrelator:
    def __init__(self, code: str):
        self.lines = code.split('\n')

    def extract(self):
        res = []
        for i, line in enumerate(self.lines, 1):
            kind = IRParser.parse_fortran_construct(line)
            if kind:
                res.append({"kind": kind, "line": i, "text": line.strip()})
        return res

    def correlate(self, stages):
        return []
