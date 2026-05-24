"""
Stage-specific semantic parsers for Flang compiler dumps.

Each parser reads the raw text output from a compilation stage and returns
structured data (constructs, symbols, IR ops) with source location info.

Source location strategy
------------------------
* Parse tree: source text extracted via ``t = '...'`` terminal nodes,
  then matched back to a line in the original .f90 source.
* HLFIR / FIR: ``loc("file":line:col)`` MLIR location attribute, present
  when compiled with ``-g``.
* LLVM IR: ``!dbg !N`` references resolved against
  ``!N = !DILocation(line: L, column: C, ...)`` metadata.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ParseTreeConstruct:
    """A parsed Fortran construct from the parse-tree dump."""
    kind: str
    line_range: Tuple[int, int]
    text: str
    children: List['ParseTreeConstruct'] = field(default_factory=list)
    source_range: Optional[str] = None

    def to_dict(self):
        return {
            'construct_kind': self.kind,
            'line_range': self.line_range,
            'text': self.text,
            'source_range': self.source_range,
            'num_children': len(self.children),
        }


@dataclass
class SemanticSymbol:
    """A symbol entry from the semantics / symbol-table dump."""
    name: str
    kind: str
    type_spec: str
    scope: str
    line_number: Optional[int] = None
    attributes: Dict[str, str] = field(default_factory=dict)

    def to_dict(self):
        return {
            'symbol_name': self.name,
            'symbol_kind': self.kind,
            'type': self.type_spec,
            'scope': self.scope,
            'attributes': self.attributes,
        }


@dataclass
class IROperation:
    """An IR operation with optional source provenance."""
    op_name: str
    operands: List[str]
    results: List[str]
    source_range: Optional[str] = None   # "file:line:col"
    src_line: Optional[int] = None       # extracted integer line number
    construct_id: Optional[str] = None
    parent_block: Optional[str] = None
    debug_loc: Optional[str] = None      # "line:col"
    raw: str = ""                        # original text line

    def to_dict(self):
        return {
            'op_name': self.op_name,
            'operands': self.operands,
            'results': self.results,
            'source_range': self.source_range,
            'src_line': self.src_line,
            'debug_loc': self.debug_loc,
            'raw': self.raw,
        }


# ---------------------------------------------------------------------------
# Parse-tree parser
# ---------------------------------------------------------------------------

class ParseTreeParser:
    """
    Extracts Fortran constructs from a Flang ``-fdebug-dump-parse-tree`` dump.

    Flang's parse-tree dump is an indented textual walk of the AST.
    Terminal nodes carrying source text appear as::

        Name = 'foo'
        t = 'a(:) = b(:) + c(:)'

    We scan every line for a known construct-type keyword and then collect
    the nearest ``t = '...'`` value as the source text.  We then resolve
    that text back to a line number in the original Fortran source.
    """

    # All Flang construct-type names we want to surface.  The value is a
    # normalised kind string returned in ParseTreeConstruct.kind.
    CONSTRUCT_MARKERS: Dict[str, str] = {
        'AssignmentStmt':         'AssignmentStmt',
        'WhereConstruct':         'WhereConstruct',
        'WhereConstructStmt':     'WhereConstruct',
        'WhereStmt':              'WhereStmt',
        'MaskedElsewhereStmt':    'WhereConstruct',
        'ElsewhereStmt':          'WhereConstruct',
        'ForallConstruct':        'ForallConstruct',
        'ForallConstructStmt':    'ForallConstruct',
        'ForallStmt':             'ForallStmt',
        'DoConstruct':            'DoConstruct',
        'NonLabelDoStmt':         'DoConstruct',
        'DoConcurrentStmt':       'DoConcurrentStmt',
        'LoopControl':            'DoConstruct',
        'IfConstruct':            'IfConstruct',
        'IfThenStmt':             'IfConstruct',
        'IfStmt':                 'IfStmt',
        'ElseIfStmt':             'IfConstruct',
        'SelectCaseConstruct':    'SelectCaseConstruct',
        'CaseConstruct':          'SelectCaseConstruct',
        'PrintStmt':              'PrintStmt',
        'WriteStmt':              'WriteStmt',
        'ReadStmt':               'ReadStmt',
        'CallStmt':               'CallStmt',
        'AllocateStmt':           'AllocateStmt',
        'DeallocateStmt':         'DeallocateStmt',
        'ReturnStmt':             'ReturnStmt',
        'StopStmt':               'StopStmt',
        'OpenMPConstruct':        'OpenMPConstruct',
        'OpenACCConstruct':       'OpenACCConstruct',
    }

    # Flang emits source text in two forms:
    #   t = 'a = b + c'        (leaf terminal)
    #   AssignmentStmt = 'a = b + c'  (full statement on construct line)
    _T_PAT = re.compile(r"^\s*t\s*=\s*'([^']*(?:''[^']*)*)'")
    _STMT_PAT = re.compile(
        r"(?:AssignmentStmt|PrintStmt|WriteStmt|ReadStmt|CallStmt|"
        r"WhereStmt|ForallStmt|DoStmt|IfStmt|AllocateStmt|DeallocateStmt|"
        r"ReturnStmt|StopStmt|OpenStmt|CloseStmt|InquireStmt|RewindStmt|"
        r"BackspaceStmt|EndfileStmt|WaitStmt|FlushStmt|"
        r"WhereConstructStmt|ForallConstructStmt|DoConcurrentStmt|"
        r"IfThenStmt|ElseIfStmt|ElseStmt|SelectCaseStmt|CaseStmt|"
        r"TypeDeclarationStmt|ParameterStmt|ImplicitStmt|"
        r"UseStmt|ModuleStmt|ProgramStmt|SubroutineStmt|FunctionStmt)"
        r"\s*=\s*'([^']*(?:''[^']*)*)'"
    )
    # MLIR loc() attribute (appears if -g was used and parse tree has it)
    _LOC_PAT = re.compile(r'loc\(["\'].*?["\']\s*:(\d+)\s*:\s*(\d+)\)')

    def __init__(self, parse_tree_dump: str, source_text: str = ""):
        self.dump = parse_tree_dump
        self.lines = parse_tree_dump.splitlines()
        self.source_text = source_text or ""
        self.source_lines = self.source_text.splitlines()
        self.constructs: List[ParseTreeConstruct] = []
        # Track which source lines we already assigned to avoid duplicates
        self._used_lines: set = set()

    def parse(self) -> List[ParseTreeConstruct]:
        self.constructs = []
        self._used_lines = set()
        self._extract_all_constructs()
        return self.constructs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_all_constructs(self):
        i = 0
        while i < len(self.lines):
            line = self.lines[i]
            matched_kind = self._match_construct_marker(line)
            if matched_kind:
                construct = self._parse_construct(i, matched_kind)
                if construct:
                    self.constructs.append(construct)
            i += 1

    def _match_construct_marker(self, line: str) -> Optional[str]:
        """Return the normalised kind if this line contains a construct marker."""
        stripped = line.strip()
        # Avoid matching substrings – require the keyword to be a whole word
        for marker, kind in self.CONSTRUCT_MARKERS.items():
            if re.search(r'\b' + re.escape(marker) + r'\b', stripped):
                return kind
        return None

    def _parse_construct(self, line_idx: int, kind: str) -> Optional[ParseTreeConstruct]:
        """Extract a construct starting at line_idx."""
        # Look ahead up to 10 lines for a t = '...' or Name = '...' terminal
        text = self._find_source_text(line_idx, lookahead=10)
        if not text:
            # Try to synthesise text from the source if we find a line match
            text = self._guess_text_for_kind(kind)

        if not text:
            return None

        # Check for a loc() attribute on the same or nearby lines
        src_line = self._find_loc_in_range(line_idx, lookahead=5)

        # Resolve source position via text matching if loc() wasn't found
        line_range, source_range = self._resolve_source_range(text, hint_line=src_line)

        # Filter: if we couldn't locate the construct at all, skip it
        if line_range == (0, 0):
            return None

        return ParseTreeConstruct(
            kind=kind,
            line_range=line_range,
            text=text,
            source_range=source_range,
        )

    def _find_source_text(self, start: int, lookahead: int = 10) -> str:
        """Scan forward looking for a source-text terminal value."""
        end = min(start + lookahead, len(self.lines))
        for j in range(start, end):
            line = self.lines[j]
            # 1. Direct construct statement: AssignmentStmt = '...'
            m = self._STMT_PAT.search(line)
            if m:
                return m.group(1).replace("''", "'")
            # 2. Leaf terminal: t = '...'
            m = self._T_PAT.match(line)
            if m:
                return m.group(1).replace("''", "'")
        return ""

    def _find_loc_in_range(self, start: int, lookahead: int = 5) -> Optional[int]:
        """Return the source line number from a loc() attribute, if present."""
        end = min(start + lookahead, len(self.lines))
        for j in range(start, end):
            m = self._LOC_PAT.search(self.lines[j])
            if m:
                return int(m.group(1))
        return None

    def _guess_text_for_kind(self, kind: str) -> str:
        """Last-resort: return the kind name so the construct isn't silently dropped."""
        return f"[{kind}]"

    def _resolve_source_range(
        self, text: str, hint_line: Optional[int] = None
    ) -> Tuple[Tuple[int, int], Optional[str]]:
        """
        Map construct text back to a line number in the original source.

        Priority:
        1. hint_line from loc() attribute
        2. Exact normalised substring match
        3. Token-based best match
        4. (0, 0) — caller will skip this construct
        """
        if not self.source_lines:
            if hint_line:
                return (hint_line, hint_line), f"source.f90:{hint_line}:1"
            return (0, 0), None

        # If we have a loc() hint, validate it quickly then accept
        if hint_line and 1 <= hint_line <= len(self.source_lines):
            line_len = len(self.source_lines[hint_line - 1])
            return (hint_line, hint_line), f"source.f90:{hint_line}:1-{hint_line}:{line_len}"

        # Normalise text for comparison
        norm_text = self._normalise(text).replace(' ', '')
        if not norm_text or norm_text.startswith('['):
            return (0, 0), None

        best_line = None
        best_score = 0
        tokens = self._tokens(text)

        for idx, src_line in enumerate(self.source_lines, start=1):
            # Skip comments and blanks
            stripped = src_line.strip()
            if not stripped or stripped.startswith('!'):
                continue
            norm_src = self._normalise(src_line).replace(' ', '')

            # Exact containment
            if norm_text and norm_text in norm_src:
                line_len = len(src_line)
                return (idx, idx), f"source.f90:{idx}:1-{idx}:{line_len}"

            # Token overlap score
            if tokens:
                score = sum(1 for t in tokens if t in norm_src) / len(tokens)
                if score > best_score:
                    best_score = score
                    best_line = idx

        if best_line and best_score >= 0.5:
            line_len = len(self.source_lines[best_line - 1])
            return (best_line, best_line), f"source.f90:{best_line}:1-{best_line}:{line_len}"

        return (0, 0), None

    @staticmethod
    def _normalise(text: str) -> str:
        t = text.lower().strip()
        t = re.sub(r'\[\w+\([0-9]+\)::', '[', t)
        t = re.sub(r'::\d+_\d+', '::', t)
        t = re.sub(r':(\d+)_\d+', r':\1', t)
        t = re.sub(r'(\d)_\d+', r'\1', t)
        t = t.replace('::', ':')
        t = re.sub(r'[^a-z0-9+\-*/=()[\]:,\s]', ' ', t)
        t = re.sub(r'\s+', ' ', t)
        return t.strip()

    @staticmethod
    def _tokens(text: str) -> List[str]:
        words = re.findall(r'[a-z_][a-z0-9_]*', text.lower())
        # Drop very short / common tokens
        return [w for w in words if len(w) > 1 and w not in ('to', 'in', 'of')]


# ---------------------------------------------------------------------------
# Semantics / symbol-table parser
# ---------------------------------------------------------------------------

class SemanticsParser:
    """Parses Flang ``-fdebug-dump-symbols`` output."""

    # Symbol table entry patterns
    _SCOPE_PAT  = re.compile(r'^(\w[\w\s]*):\s*$')
    _SYMBOL_PAT = re.compile(
        r'^\s{2,}(\w+)\s*:.*?(\w+(?:\s+\w+)*(?:\([^)]*\))?)\s*(?:,\s*(.*))?$'
    )
    _TYPE_PAT   = re.compile(
        r'(\w+(?:\s+\w+)*(?:\([^)]*\))?)\s*(?:,\s*(.+))?'
    )

    def __init__(self, semantics_dump: str):
        self.dump = semantics_dump
        self.lines = semantics_dump.splitlines()

    def parse(self) -> Dict[str, SemanticSymbol]:
        symbols: Dict[str, SemanticSymbol] = {}
        current_scope = 'global'

        for line in self.lines:
            # Detect scope header
            m = self._SCOPE_PAT.match(line)
            if m:
                current_scope = m.group(1).strip()
                continue

            # Try to extract symbol entry
            sym = self._parse_symbol_line(line, current_scope)
            if sym:
                symbols[sym.name.lower()] = sym

        return symbols

    def _parse_symbol_line(self, line: str, scope: str) -> Optional[SemanticSymbol]:
        if not line.strip() or line.strip().startswith('!'):
            return None

        # Pattern: "  name: type [attrs]"
        m = re.match(
            r'^\s{2,}(\w+)\s*:\s*([\w\s*()]+?)(?:\s*,\s*(.*))?$', line
        )
        if not m:
            return None

        name = m.group(1).strip()
        type_spec = m.group(2).strip()
        attrs_raw = m.group(3) or ''

        kind = 'VARIABLE'
        if 'array' in type_spec.lower() or '(' in type_spec:
            kind = 'ARRAY'
        elif 'type' in type_spec.lower():
            kind = 'DERIVED'
        elif attrs_raw and 'parameter' in attrs_raw.lower():
            kind = 'PARAMETER'

        return SemanticSymbol(
            name=name,
            kind=kind,
            type_spec=type_spec,
            scope=scope,
            attributes={'attrs': attrs_raw} if attrs_raw else {},
        )


# ---------------------------------------------------------------------------
# HLFIR parser
# ---------------------------------------------------------------------------

class HLFIRParser:
    """Parses Flang HLFIR (``-emit-hlfir``) MLIR text."""

    _LOC_PAT = re.compile(r'loc\(["\'].*?["\']?\s*:(\d+)\s*:\s*(\d+)\)')
    _RESULT_PAT = re.compile(r'(%[\w.]+(?:,\s*%[\w.]+)*)\s*=')
    _OP_PAT = re.compile(r'(hlfir\.\w+|fir\.\w+|arith\.\w+|func\.\w+|cf\.\w+)\b')

    def __init__(self, hlfir_dump: str):
        self.dump = hlfir_dump
        self.lines = hlfir_dump.splitlines()

    def parse(self) -> List[IROperation]:
        ops: List[IROperation] = []
        for line in self.lines:
            op = self._parse_op_line(line)
            if op:
                ops.append(op)
        return ops

    def _parse_op_line(self, line: str) -> Optional[IROperation]:
        stripped = line.strip()
        if not stripped or stripped.startswith('//') or stripped.startswith('#'):
            return None

        m_op = self._OP_PAT.search(stripped)
        if not m_op:
            return None

        op_name = m_op.group(1)
        results = self._RESULT_PAT.findall(stripped)
        results = [r.strip() for r in (results[0].split(',') if results else [])]
        operands = re.findall(r'%[\w.]+', stripped[m_op.end():])

        # Extract loc() attribute
        src_line, src_col, src_range, debug_loc = None, None, None, None
        m_loc = self._LOC_PAT.search(stripped)
        if m_loc:
            src_line = int(m_loc.group(1))
            src_col = int(m_loc.group(2))
            src_range = f"source.f90:{src_line}:{src_col}"
            debug_loc = f"{src_line}:{src_col}"

        return IROperation(
            op_name=op_name,
            operands=operands,
            results=results,
            source_range=src_range,
            src_line=src_line,
            debug_loc=debug_loc,
            raw=stripped,
        )


# ---------------------------------------------------------------------------
# FIR parser
# ---------------------------------------------------------------------------

class FIRParser:
    """Parses Flang FIR (``-emit-fir``) MLIR text."""

    _LOC_PAT = re.compile(r'loc\(["\'].*?["\']?\s*:(\d+)\s*:\s*(\d+)\)')
    _RESULT_PAT = re.compile(r'((?:%[\w.]+)(?:\s*,\s*%[\w.]+)*)\s*=')
    _OP_PAT = re.compile(
        r'(fir\.\w+|hlfir\.\w+|arith\.\w+|func\.\w+|omp\.\w+|cf\.\w+|llvm\.\w+)\b'
    )

    def __init__(self, fir_dump: str):
        self.dump = fir_dump
        self.lines = fir_dump.splitlines()

    def parse(self) -> List[IROperation]:
        ops: List[IROperation] = []
        for line in self.lines:
            op = self._parse_op_line(line)
            if op:
                ops.append(op)
        return ops

    def _parse_op_line(self, line: str) -> Optional[IROperation]:
        stripped = line.strip()
        if not stripped or stripped.startswith('//') or stripped.startswith('#'):
            return None

        m_op = self._OP_PAT.search(stripped)
        if not m_op:
            return None

        op_name = m_op.group(1)
        results = self._RESULT_PAT.findall(stripped)
        results = [r.strip() for r in (results[0].split(',') if results else [])]
        operands = re.findall(r'%[\w.]+', stripped[m_op.end():])

        src_line, src_col, src_range, debug_loc = None, None, None, None
        m_loc = self._LOC_PAT.search(stripped)
        if m_loc:
            src_line = int(m_loc.group(1))
            src_col = int(m_loc.group(2))
            src_range = f"source.f90:{src_line}:{src_col}"
            debug_loc = f"{src_line}:{src_col}"

        return IROperation(
            op_name=op_name,
            operands=operands,
            results=results,
            source_range=src_range,
            src_line=src_line,
            debug_loc=debug_loc,
            raw=stripped,
        )


# ---------------------------------------------------------------------------
# LLVM IR parser
# ---------------------------------------------------------------------------

class LLVMParser:
    """
    Parses Flang LLVM IR (``-emit-llvm``) with debug info.

    Resolves ``!dbg !N`` references against
    ``!N = !DILocation(line: L, column: C, scope: !M)`` metadata.
    """

    _DILOCN_PAT = re.compile(
        r'^!(\d+)\s*=\s*!DILocation\(line:\s*(\d+),\s*column:\s*(\d+)'
    )
    _DBG_REF_PAT = re.compile(r'!dbg\s*!(\d+)')
    _INSTR_PAT = re.compile(
        r'(%[\w.]+\s*=\s*|store\s|load\s|br\s|ret\s|call\s|icmp\s|fcmp\s'
        r'|add\s|sub\s|mul\s|div\s|getelementptr\s)'
    )

    def __init__(self, llvm_dump: str):
        self.dump = llvm_dump
        self.lines = llvm_dump.splitlines()
        self._dilocn: Dict[str, Dict] = {}
        self._build_dilocation_map()

    def _build_dilocation_map(self):
        """First pass: collect all !DILocation metadata entries."""
        for line in self.lines:
            m = self._DILOCN_PAT.match(line.strip())
            if m:
                self._dilocn[m.group(1)] = {
                    'line': int(m.group(2)),
                    'column': int(m.group(3)),
                }

    def parse(self) -> List[Dict]:
        """Return list of instruction dicts with resolved source lines."""
        instrs = []
        for line in self.lines:
            stripped = line.strip()
            if not stripped or stripped.startswith(';') or stripped.startswith('!'):
                continue
            if not self._INSTR_PAT.search(stripped):
                continue

            src_line = None
            src_col = None
            m_dbg = self._DBG_REF_PAT.search(stripped)
            if m_dbg:
                ref = m_dbg.group(1)
                if ref in self._dilocn:
                    src_line = self._dilocn[ref]['line']
                    src_col = self._dilocn[ref]['column']

            instrs.append({
                'line': stripped,
                'src_line': src_line,
                'src_col': src_col,
                'debug_loc': f"{src_line}:{src_col}" if src_line else None,
            })
        return instrs
