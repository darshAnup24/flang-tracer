#/ftrace/compiler_interface.py

import subprocess
import os
import logging
import tempfile
from typing import Dict

logger = logging.getLogger(__name__)


class FlangNotFoundError(Exception):
    pass


class CompilerInterface:

    def __init__(self):
        self.flang_path = self._find_flang()
        self.temp_dir = tempfile.mkdtemp(prefix='ftrace_')
        logger.info(f"Using Flang: {self.flang_path}")

    @staticmethod
    def _find_flang() -> str:
        candidates = [
            'flang-new',
            '/usr/bin/flang-new',
            '/usr/lib/llvm-18/bin/flang-new'
        ]

        for c in candidates:
            try:
                r = subprocess.run([c, '--version'], capture_output=True, timeout=5)
                if r.returncode == 0:
                    return c
            except:
                continue

        raise FlangNotFoundError("flang-new not found")

    def compile_to_stages(self, code: str) -> Dict[str, str]:

        src = os.path.join(self.temp_dir, 'input.f90')
        with open(src, 'w') as f:
            f.write(code)

        return {
            "parse_tree": self._extract_parse_tree(src),
            "semantics": self._extract_semantics(src),
            "hlfir": self._extract_hlfir(src),
            "fir": self._extract_fir(src),
            "llvm_ir": self._extract_llvm_ir(src),
        }

    def _run(self, args):
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=30)
            return r.stdout + r.stderr
        except Exception as e:
            return f"[Error: {e}]"

    def _extract_parse_tree(self, src):
        return self._run([self.flang_path, '-fc1', '-fdebug-dump-parse-tree', src])

    def _extract_semantics(self, src):
        return self._run([self.flang_path, '-fc1', '-fdebug-dump-symbols', src])

    def _extract_hlfir(self, src):
        out = os.path.join(self.temp_dir, 'out.hlfir')

        self._run([
            self.flang_path,
            '-fc1',
            '-O0',
            '-emit-hlfir',
            src,
            '-o', out
        ])

        return open(out).read() if os.path.exists(out) else "[No HLFIR]"

    def _extract_fir(self, src):
        out = os.path.join(self.temp_dir, 'out.fir')

        self._run([
            self.flang_path,
            '-fc1',
            '-O0',
            '-emit-fir',
            src,
            '-o', out
        ])

        return open(out).read() if os.path.exists(out) else "[No FIR]"

    def _extract_llvm_ir(self, src):
        out = os.path.join(self.temp_dir, 'out.ll')

        self._run([
            self.flang_path,
            '-fc1',
            '-O0',
            '-emit-llvm',
            src,
            '-o', out
        ])

        return open(out).read() if os.path.exists(out) else "[No LLVM IR]"


# -------------------------
# SIMPLE PARSER
# -------------------------

class IRParser:

    @staticmethod
    def parse_fortran_construct(line: str):
        l = line.strip().lower()

        if ' = ' in l and not any(x in l for x in ['if', 'do', 'where']):
            return 'SCALAR_ASSIGN'

        return None


# -------------------------
# CORRELATOR
# -------------------------

class SourceLocationCorrelator:

    def __init__(self, code: str):
        self.lines = code.split('\n')

    def extract(self):
        res = []
        for i, line in enumerate(self.lines, 1):
            kind = IRParser.parse_fortran_construct(line)
            if kind:
                res.append({
                    "kind": kind,
                    "line": i,
                    "text": line.strip()
                })
        return res

    def correlate(self, stages):
        src_nodes = self.extract()
        out = []

        for n in src_nodes:
            out.append({
                "text": n["text"],
                "kind": n["kind"],
                "parse_tree": "[Not captured]",
                "semantics": "[Not captured]",

                #  FIX: ignore noisy HLFIR
                "hlfir_op": "[Skipped noisy HLFIR]",

                #  PRIMARY SIGNAL
                "fir_op": self._extract_stage_info(stages["fir"], n["text"]),

                "llvm_ir": self._extract_stage_info(stages["llvm_ir"], n["text"]),
            })

        return out

    @staticmethod
    def _extract_stage_info(stage_dump: str, source_text: str) -> str:

        lines = stage_dump.split('\n')
        result = []

        if '+' in source_text:
            ops = ['arith.addf', 'fadd']
        elif '-' in source_text:
            ops = ['arith.subf', 'fsub']
        elif '*' in source_text:
            ops = ['arith.mulf', 'fmul']
        elif '/' in source_text:
            ops = ['arith.divf', 'fdiv']
        else:
            ops = []

        for line in lines:

            if 'hlfir.declare' in line or 'fir.alloca' in line:
                continue

            if '_FortranAio' in line:
                continue

            if any(op in line for op in ops):
                result.append(line)

            elif 'fir.load' in line or 'fir.store' in line:
                result.append(line)

            if len(result) >= 6:
                break

        if result:
            return '\n'.join(result)

        return "[No relevant IR]"