"""
Stage-specific semantic parsers for Flang compiler dumps.

This module provides semantic-aware extraction of constructs at each stage:
- Parse Tree: AST nodes (AssignmentStmt, Variable, Expr, etc.)
- Semantics: Symbol table entries and type bindings
- HLFIR: High-level Fortran IR with semantic structure
- FIR: Lowered SSA-style operations with source ranges
- LLVM IR: Machine code with debug metadata
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ParseTreeConstruct:
    """Represents a parsed Fortran construct from the parse tree."""
    kind: str  # 'AssignmentStmt', 'Expr', 'Variable', etc.
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
            'num_children': len(self.children)
        }


@dataclass
class SemanticSymbol:
    """Represents a symbol with type information from semantics stage."""
    name: str
    kind: str  # 'VARIABLE', 'PARAMETER', 'ARRAY', 'DERIVED', etc.
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
            'attributes': self.attributes
        }


@dataclass
class IROperation:
    """Represents an IR operation with provenance."""
    op_name: str
    operands: List[str]
    results: List[str]
    source_range: Optional[str] = None
    construct_id: Optional[str] = None
    parent_block: Optional[str] = None
    debug_loc: Optional[str] = None

    def to_dict(self):
        return {
            'op_name': self.op_name,
            'operands': self.operands,
            'results': self.results,
            'source_range': self.source_range,
            'construct_id': self.construct_id,
            'debug_loc': self.debug_loc
        }


class ParseTreeParser:
    """Extracts AST constructs from Flang parse tree dumps."""

    def __init__(self, parse_tree_dump: str, source_text: str = ""):
        self.dump = parse_tree_dump
        self.lines = parse_tree_dump.splitlines()
        self.source_text = source_text or ""
        self.source_lines = self.source_text.splitlines()
        self.constructs: List[ParseTreeConstruct] = []

    def parse(self) -> List[ParseTreeConstruct]:
        """Extract all constructs from parse tree dump."""
        self.constructs = []
        self._extract_all_assignments()
        return self.constructs

    def _extract_all_assignments(self):
        """Extract all assignment statements and structured constructs from parse tree."""
        for i, line in enumerate(self.lines):
            # Look for AssignmentStm entries which show "t = '...'"
            if 'AssignmentStm' in line:
                construct = self._parse_assignment_stmt(i)
                if construct:
                    self.constructs.append(construct)
            # Look for other statement types
            elif any(stmt in line for stmt in ['PrintStmt', 'WriteStmt', 'ReadStmt']):
                construct = self._parse_io_stmt(i)
                if construct:
                    self.constructs.append(construct)
            elif 'CallStmt' in line:
                construct = self._parse_call_stmt(i)
                if construct:
                    self.constructs.append(construct)

    def _parse_assignment_stmt(self, line_idx: int) -> Optional[ParseTreeConstruct]:
        """Parse an assignment statement from parse tree."""
        # Look for the "t = '...'" pattern which gives us the source text
        for j in range(line_idx, min(line_idx + 5, len(self.lines))):
            match = re.search(r"t\s*=\s*'([^']+)'", self.lines[j])
            if match:
                text = match.group(1)
                line_range, source_range = self._resolve_source_range(text)
                construct = ParseTreeConstruct(
                    kind='AssignmentStmt',
                    line_range=line_range,
                    text=text,
                    source_range=source_range
                )
                return construct
        return None

    def _parse_io_stmt(self, line_idx: int) -> Optional[ParseTreeConstruct]:
        """Parse an I/O statement from parse tree."""
        line = self.lines[line_idx]
        if 'PrintStmt' in line:
            kind = 'PrintStmt'
        elif 'WriteStmt' in line:
            kind = 'WriteStmt'
        elif 'ReadStmt' in line:
            kind = 'ReadStmt'
        else:
            return None
        
        # Try to extract the statement text
        for j in range(line_idx, min(line_idx + 3, len(self.lines))):
            match = re.search(r"t\s*=\s*'([^']+)'", self.lines[j])
            if match:
                text = match.group(1)
                line_range, source_range = self._resolve_source_range(text)
                construct = ParseTreeConstruct(
                    kind=kind,
                    line_range=line_range,
                    text=text,
                    source_range=source_range
                )
                return construct
        return None

    def _parse_call_stmt(self, line_idx: int) -> Optional[ParseTreeConstruct]:
        """Parse a call statement from parse tree."""
        for j in range(line_idx, min(line_idx + 3, len(self.lines))):
            match = re.search(r"t\s*=\s*'([^']+)'", self.lines[j])
            if match:
                text = match.group(1)
                line_range, source_range = self._resolve_source_range(text)
                construct = ParseTreeConstruct(
                    kind='CallStmt',
                    line_range=line_range,
                    text=text,
                    source_range=source_range
                )
                return construct
        return None

    def _resolve_source_range(self, text: str) -> Tuple[Tuple[int, int], Optional[str]]:
        """Resolve source line numbers and range information using the original source."""
        if not text or not self.source_lines:
            return (0, 0), None

        normalized_target = self._normalize_source_text(text).replace(' ', '')
        if not normalized_target:
            return (0, 0), None

        best_match = None
        for idx, line in enumerate(self.source_lines, start=1):
            normalized_line = self._normalize_source_text(line).replace(' ', '')
            if normalized_target in normalized_line:
                return (idx, idx), f"source.f90:{idx}:1-{idx}:{len(line)}"
            if all(token in normalized_line for token in self._extract_search_tokens(text)):
                best_match = idx

        if best_match is not None:
            line = self.source_lines[best_match - 1]
            return (best_match, best_match), f"source.f90:{best_match}:1-{best_match}:{len(line)}"

        return (0, 0), None

    def _normalize_source_text(self, text: str) -> str:
        """Normalize text for source matching."""
        text = text.lower().strip()
        # Normalize array constructor type spec [INTEGER(4):: -> [
        text = re.sub(r'\[\w+\([0-9]+\)::', '[', text)
        # Remove Fortran kind suffixes like _4, _8 AFTER the number (e.g., 1_4 -> 1, ::1_8 -> ::)
        text = re.sub(r'::\d+_\d+', '::', text)
        text = re.sub(r':(\d+)_\d+', r':\1', text)
        text = re.sub(r'(\d)_\d+', r'\1', text)
        # Normalize array specs: :: becomes :
        text = text.replace('::', ':')
        text = text.replace('(', ' ( ').replace(')', ' ) ').replace('[', ' [ ').replace(']', ' ] ')
        text = text.replace('=', ' = ').replace('+', ' + ').replace('-', ' - ').replace('*', ' * ').replace('/', ' / ')
        text = re.sub(r'[^a-z0-9\+\-\*\/=\(\)\[\]\:\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_search_tokens(self, text: str) -> List[str]:
        """Extract tokens for heuristic source matching."""
        return [tok for tok in re.findall(r'[a-zA-Z_]\w*|\+|\-|\*|\/|==|/=|<=|>=|<|>', text) if tok]


class SemanticsParser:
    """Extracts symbol table and type information from Fortran semantics dumps."""

    SYMBOL_PATTERNS = {
        'variable': r'^(\s*)(?P<name>\w+).*?(?P<type>REAL|INTEGER|LOGICAL|CHARACTER|COMPLEX)',
        'parameter': r'PARAMETER.*?=.*?(?P<value>[\d\w\.\-]+)',
        'array': r'DIMENSION.*?\[(?P<shape>[\d\*:, ]+)\]',
        'derived': r'TYPE.*?::',
    }

    def __init__(self, semantics_dump: str):
        self.dump = semantics_dump
        self.lines = semantics_dump.split('\n')
        self.symbols: Dict[str, SemanticSymbol] = {}

    def parse(self) -> Dict[str, SemanticSymbol]:
        """Extract all symbols from semantics dump."""
        self.symbols = {}
        self._extract_symbols()
        return self.symbols

    def _extract_symbols(self):
        """Walk semantics dump and extract symbol definitions."""
        current_scope = 'GLOBAL'

        for i, line in enumerate(self.lines):
            # Scope change detection
            if 'PROGRAM' in line or 'SUBROUTINE' in line or 'FUNCTION' in line:
                match = re.search(r'(PROGRAM|SUBROUTINE|FUNCTION)\s+(\w+)', line)
                if match:
                    current_scope = match.group(2)

            # Symbol extraction
            symbol = self._extract_symbol(line, current_scope)
            if symbol:
                self.symbols[symbol.name] = symbol

    def _extract_symbol(self, line: str, scope: str) -> Optional[SemanticSymbol]:
        """Extract a single symbol from a semantics line."""
        if not line.strip():
            return None

        # Type detection
        type_spec = None
        for type_name in ['REAL', 'INTEGER', 'LOGICAL', 'CHARACTER', 'COMPLEX']:
            if type_name in line:
                type_spec = type_name
                break

        if not type_spec:
            return None

        # Name extraction
        match = re.search(r'(\w+)\s+', line)
        if not match:
            return None

        name = match.group(1)

        # Kind detection
        kind = 'VARIABLE'
        if 'PARAMETER' in line:
            kind = 'PARAMETER'
        elif 'DIMENSION' in line or '[' in line:
            kind = 'ARRAY'
        elif 'ALLOCATABLE' in line:
            kind = 'ALLOCATABLE'
        elif 'POINTER' in line:
            kind = 'POINTER'

        # Attributes extraction
        attributes = {}
        if 'INTENT' in line:
            match_intent = re.search(r'INTENT\s*\(\s*(\w+)\s*\)', line)
            if match_intent:
                attributes['intent'] = match_intent.group(1)

        if 'VALUE' in line:
            attributes['value'] = True

        return SemanticSymbol(
            name=name,
            kind=kind,
            type_spec=type_spec,
            scope=scope,
            attributes=attributes
        )


class HLFIRParser:
    """Extracts high-level Fortran IR operations with semantic structure preserved."""

    def __init__(self, hlfir_dump: str):
        self.dump = hlfir_dump
        self.lines = hlfir_dump.splitlines()
        self.operations: List[IROperation] = []

    def parse(self) -> List[IROperation]:
        """Extract operations from HLFIR dump."""
        self.operations = []
        self._extract_operations()
        return self.operations

    def _extract_operations(self):
        """Extract HLFIR operations, preserving high-level semantics."""
        for line in self.lines:
            op = self._parse_operation_line(line)
            if op:
                self.operations.append(op)

    def _parse_operation_line(self, line: str) -> Optional[IROperation]:
        """Parse a single HLFIR operation line."""
        stripped = line.strip()
        if not stripped or stripped.startswith('//'):
            return None

        match = re.match(r'(?:(%[\w#\.]+)\s*=\s*)?(hlfir\.\w+)\s*(.*)$', stripped)
        if not match:
            return None

        result = match.group(1)
        op_name = match.group(2)
        rest = match.group(3)
        operands = self._parse_operands(rest)
        source_range = self._extract_source_range(line)

        return IROperation(
            op_name=op_name,
            operands=operands,
            results=[result] if result else [],
            source_range=source_range
        )

    def _parse_operands(self, rest: str) -> List[str]:
        """Extract operands from an HLFIR operation string."""
        if not rest:
            return []

        operand_part = rest.split(':', 1)[0]
        operand_part = operand_part.split('{', 1)[0]
        operand_part = operand_part.replace(' to ', ', ')
        operand_part = operand_part.replace(' unordered', '')

        tokens = [tok.strip() for tok in re.split(r'[(),\s]+', operand_part) if tok.strip()]
        return [tok for tok in tokens if tok not in {'to', 'unordered', 'shape', 'fastmath', 'contract'}]

    def _extract_source_range(self, line: str) -> Optional[str]:
        """Extract source location from MLIR loc() attribute."""
        match = re.search(r'loc\("([^"]+)"\)', line)
        if match:
            return match.group(1)
        return None


class FIRParser:
    """Extracts lowered SSA operations from FIR with provenance tracking."""

    def __init__(self, fir_dump: str):
        self.dump = fir_dump
        self.lines = fir_dump.splitlines()
        self.operations: List[IROperation] = []
        self.construct_map: Dict[str, List[IROperation]] = {}

    def parse(self) -> List[IROperation]:
        """Extract operations from FIR dump."""
        self.operations = []
        self._extract_operations()
        self._group_by_provenance()
        return self.operations

    def _extract_operations(self):
        """Extract FIR operations with source provenance."""
        block_stack = []
        for line in self.lines:
            stripped = line.strip()
            if stripped.startswith('fir.do_loop') and '{' in stripped:
                block_stack.append('fir.do_loop')

            op = self._parse_operation_line(line)
            if op:
                op.parent_block = block_stack[-1] if block_stack else None
                self.operations.append(op)

            if stripped == '}' and block_stack:
                block_stack.pop()

    def _parse_operation_line(self, line: str) -> Optional[IROperation]:
        """Parse a FIR operation line."""
        stripped = line.strip()
        if not stripped or stripped.startswith('//'):
            return None

        match = re.match(
            r'(?:(%[\w#\.]+)\s*=\s*)?(fir\.\w+|arith\.\w+)\s*(.*)$',
            stripped
        )
        if not match:
            return None

        result = match.group(1)
        op_name = match.group(2)
        rest = match.group(3)

        operand_section = rest.split(':', 1)[0]
        operand_section = operand_section.split('{', 1)[0]
        operands = [tok.strip() for tok in re.split(r'[(),\s]+', operand_section) if tok.strip()]
        operands = [tok for tok in operands if tok not in {'to', 'step', 'unordered', 'shape', 'fastmath', 'contract', 'tuple', 'none'}]

        debug_loc = None
        debug_match = re.search(r'!dbg\s*!([0-9]+)', line)
        if debug_match:
            debug_loc = f"metadata_id_{debug_match.group(1)}"

        source_range = self._extract_source_range(line)

        return IROperation(
            op_name=op_name,
            operands=operands,
            results=[result] if result else [],
            source_range=source_range,
            debug_loc=debug_loc
        )

    def _extract_source_range(self, line: str) -> Optional[str]:
        """Extract source location from FIR operation."""
        match = re.search(r'loc\("([^"]+)"\)', line)
        if match:
            return match.group(1)
        return None

    def _group_by_provenance(self):
        """Group operations by their source provenance."""
        self.construct_map.clear()

        for op in self.operations:
            if op.source_range:
                if op.source_range not in self.construct_map:
                    self.construct_map[op.source_range] = []
                self.construct_map[op.source_range].append(op)

    def get_ops_for_source_range(self, source_range: str) -> List[IROperation]:
        """Get all FIR operations for a source range (one-to-many mapping)."""
        return self.construct_map.get(source_range, [])


class LLVMParser:
    """Extracts LLVM IR instructions with debug metadata correlation."""

    def __init__(self, llvm_ir: str):
        self.dump = llvm_ir
        self.lines = llvm_ir.split('\n')
        self.instructions: List[Dict] = []
        self.debug_metadata: Dict[int, Dict] = {}

    def parse(self) -> List[Dict]:
        """Extract instructions from LLVM IR."""
        self.instructions = []
        self._extract_debug_metadata()
        self._extract_instructions()
        return self.instructions

    def _extract_debug_metadata(self):
        """Extract debug metadata mappings."""
        for i, line in enumerate(self.lines):
            if '!dbg' in line:
                match = re.search(r'!(\d+)', line)
                if match:
                    metadata_id = int(match.group(1))
                    # Store line number for this metadata ID
                    if metadata_id not in self.debug_metadata:
                        self.debug_metadata[metadata_id] = {}
                    self.debug_metadata[metadata_id]['line'] = i

    def _extract_instructions(self):
        """Extract LLVM instructions relevant to Fortran semantics."""
        for i, line in enumerate(self.lines):
            if not line.strip() or line.startswith(';'):
                continue

            op_types = [
                'fadd', 'fsub', 'fmul', 'fdiv',
                'add', 'sub', 'mul', 'sdiv', 'udiv',
                'icmp', 'fcmp', 'load', 'store', 'call'
            ]

            for op_type in op_types:
                if re.search(rf'\b{re.escape(op_type)}\b', line):
                    instr = self._parse_instruction(line, op_type)
                    if instr:
                        self.instructions.append(instr)
                    break

    def _parse_instruction(self, line: str, op_type: str) -> Optional[Dict]:
        """Parse a single LLVM instruction."""
        debug_loc = None
        match_dbg = re.search(r'!dbg !([0-9]+)', line)
        if match_dbg:
            debug_loc = f"metadata_id_{match_dbg.group(1)}"

        return {
            'op': op_type,
            'line': line.strip(),
            'debug_loc': debug_loc
        }


class StageExtractor:
    """Unified interface for stage-aware extraction."""

    def __init__(self, fortran_code: str, parse_tree: str, semantics: str,
                 hlfir: str, fir: str, llvm_ir: str):
        self.source = fortran_code
        self.parse_tree_parser = ParseTreeParser(parse_tree, fortran_code)
        self.semantics_parser = SemanticsParser(semantics)
        self.hlfir_parser = HLFIRParser(hlfir)
        self.fir_parser = FIRParser(fir)
        self.llvm_parser = LLVMParser(llvm_ir)

    def extract_all(self) -> Dict:
        """Extract semantic information from all stages."""
        return {
            'parse_tree': [c.to_dict() for c in self.parse_tree_parser.parse()],
            'semantics': {k: v.to_dict() for k, v in self.semantics_parser.parse().items()},
            'hlfir': [op.to_dict() for op in self.hlfir_parser.parse()],
            'fir': [op.to_dict() for op in self.fir_parser.parse()],
            'llvm': self.llvm_parser.parse(),
        }

    def get_construct_by_source_range(self, source_range: str) -> Dict:
        """Get all related constructs/operations for a source range."""
        return {
            'fir_ops': [op.to_dict() for op in self.fir_parser.get_ops_for_source_range(source_range)]
        }
