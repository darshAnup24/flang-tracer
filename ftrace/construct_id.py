"""
Construct identity system for stable correlation through compilation stages.

This module manages stable construct IDs that persist from Parse Tree through LLVM,
enabling one-to-many mapping and reliable correlation across all stages.
"""

import hashlib
import re
from typing import Dict, Optional, List, Tuple
from enum import Enum


class ConstructKind(Enum):
    """Classification of Fortran language constructs."""
    SCALAR_ASSIGN = "scalar_assignment"
    ARRAY_ASSIGN = "array_assignment"
    WHERE = "where_construct"
    WHERE_MASKED = "where_masked"
    FORALL = "forall_construct"
    DO = "do_construct"
    DO_CONCURRENT = "do_concurrent"
    IF = "if_construct"
    SELECT_CASE = "select_case"
    INTRINSIC_CALL = "intrinsic_call"
    USER_CALL = "user_call"
    POLYMORPH_CALL = "polymorphic_call"
    COARRAY_OP = "coarray_operation"
    IO_STATEMENT = "io_statement"
    PRINT_STATEMENT = "print_statement"
    EXPR = "expression"
    UNKNOWN = "unknown"


@staticmethod
def normalize_source_range(src_range: str) -> str:
    """Normalize source range for reliable matching.
    
    Converts 'file.f90:10:1-10:20' format to normalized key.
    """
    if not src_range:
        return ""
    # Keep only line:col-line:col part, normalize whitespace
    return re.sub(r'\s+', '', src_range)


class ConstructID:
    """Stable identifier for a Fortran construct across all stages."""

    def __init__(self, kind: ConstructKind, line_range: Tuple[int, int],
                 source_range: str, variables: List[str], operators: List[str]):
        """
        Initialize a construct ID.
        
        Args:
            kind: Classification of the construct
            line_range: (start_line, end_line) in source file
            source_range: Fortran standard source location "file:line:col-line:col"
            variables: List of variable names involved
            operators: List of operators used ('+', '-', etc.)
        """
        self.kind = kind
        self.line_range = line_range
        self.source_range = normalize_source_range(source_range)
        self.variables = sorted(variables)  # Sorted for deterministic hashing
        self.operators = sorted(operators)

    @property
    def hash(self) -> str:
        """Generate a stable hash for this construct."""
        components = [
            self.kind.value,
            f"{self.line_range[0]}:{self.line_range[1]}",
            self.source_range,
            ",".join(self.variables),
            ",".join(self.operators),
        ]
        content = "|".join(components)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def __eq__(self, other):
        if not isinstance(other, ConstructID):
            return False
        return (self.kind == other.kind and
                self.line_range == other.line_range and
                self.source_range == other.source_range)

    def __hash__(self):
        return hash((self.kind, self.line_range, self.source_range))

    def __str__(self):
        return f"[{self.kind.value}:{self.hash}@{self.line_range}]"

    def to_dict(self):
        return {
            'kind': self.kind.value,
            'id': self.hash,
            'line_range': self.line_range,
            'source_range': self.source_range,
            'variables': self.variables,
            'operators': self.operators,
        }


class ConstructIdentifier:
    """Identifies and assigns stable IDs to Fortran constructs."""

    def __init__(self, fortran_code: str):
        """Initialize with Fortran source code."""
        self.source = fortran_code
        self.lines = fortran_code.split('\n')
        self.constructs: Dict[str, ConstructID] = {}
        self._id_counter = 0

    def identify_from_parse_tree(self, parse_tree_constructs: List) -> Dict[str, ConstructID]:
        """Identify constructs from parse tree information."""
        ids = {}

        for construct in parse_tree_constructs:
            kind_str = construct.get('construct_kind', '').lower()
            line_range = construct.get('line_range', (0, 0))
            source_range = construct.get('source_range', '')
            text = construct.get('text', '')

            kind = self._map_construct_kind(kind_str, text)
            variables = self._extract_variables(text)
            operators = self._extract_operators(text)

            if kind == ConstructKind.SCALAR_ASSIGN and self._looks_like_array_assignment(text):
                kind = ConstructKind.ARRAY_ASSIGN

            source_range = source_range or self._find_source_range(text, line_range)

            construct_id = ConstructID(kind, line_range, source_range, variables, operators)
            ids[construct_id.hash] = construct_id
            self.constructs[construct_id.hash] = construct_id

        return ids

    def _map_construct_kind(self, parse_tree_kind: str, text: str = "") -> ConstructKind:
        """Map parse tree construct kind to ConstructKind."""
        mapping = {
            'assignmentstmt': ConstructKind.SCALAR_ASSIGN,
            'arrayassignment': ConstructKind.ARRAY_ASSIGN,
            'whereconstruct': ConstructKind.WHERE,
            'wherestmt': ConstructKind.WHERE,
            'forallconstruct': ConstructKind.FORALL,
            'forallstmt': ConstructKind.FORALL,
            'doconstruct': ConstructKind.DO,
            'dococurrent': ConstructKind.DO_CONCURRENT,
            'ifconstruct': ConstructKind.IF,
            'selectcase': ConstructKind.SELECT_CASE,
            'intrinsic': ConstructKind.INTRINSIC_CALL,
        }
        kind = mapping.get(parse_tree_kind.lower(), ConstructKind.UNKNOWN)
        if kind == ConstructKind.SCALAR_ASSIGN and self._looks_like_array_assignment(text):
            return ConstructKind.ARRAY_ASSIGN
        return kind

    def _looks_like_array_assignment(self, text: str) -> bool:
        """Detect whether the construct text represents an array assignment."""
        if not text:
            return False
        lower = text.lower()
        # Check for various array syntax patterns
        array_indicators = [
            '(:', '%(', 'array', 'section',  # Array sections and operations
            '[', ']', '(/', '/)',           # Array constructors
            'reshape', 'spread', 'pack', 'unpack'  # Array functions
        ]
        return any(indicator in lower for indicator in array_indicators)

    def _find_source_range(self, text: str, fallback_range: Tuple[int, int]) -> str:
        """Find or approximate a source range for a construct."""
        if text:
            normalized_target = self._normalize_source_text(text).replace(' ', '')
            for i, line in enumerate(self.lines, start=1):
                normalized_line = self._normalize_source_text(line).replace(' ', '')
                if normalized_target and normalized_target in normalized_line:
                    return f"source.f90:{i}:1-{i}:{len(line)}"

        if fallback_range != (0, 0):
            start, end = fallback_range
            line_len = len(self.lines[start - 1]) if 0 < start <= len(self.lines) else 1
            return f"source.f90:{start}:1-{end}:{line_len}"

        return ""

    def _normalize_source_text(self, text: str) -> str:
        """Normalize source text for matching."""
        normalized = text.lower().strip()
        normalized = normalized.replace('::', ':')
        normalized = re.sub(r':\d+_\d+', ':', normalized)
        normalized = re.sub(r'\d+_\d+', '', normalized)
        normalized = re.sub(r'[^a-z0-9\+\-\*\/=\(\)\[\]\:\s]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized.strip()

    def identify_from_source_text(self) -> Dict[str, ConstructID]:
        """Identify constructs by analyzing source text directly."""
        ids = {}

        for i, line in enumerate(self.lines, 1):
            # Skip comments and empty lines
            if line.strip().startswith('!') or not line.strip():
                continue

            kind = self._classify_line(line)
            if kind == ConstructKind.UNKNOWN:
                continue

            # Extract variables and operators
            variables = self._extract_variables(line)
            operators = self._extract_operators(line)

            construct_id = ConstructID(
                kind=kind,
                line_range=(i, i),
                source_range=f"source.f90:{i}:1-{i}:{len(line)}",
                variables=variables,
                operators=operators
            )

            ids[construct_id.hash] = construct_id
            self.constructs[construct_id.hash] = construct_id

        return ids

    def _classify_line(self, line: str) -> ConstructKind:
        """Classify a source line into a construct kind."""
        line_lower = line.lower().strip()

        # Skip comments and empty lines
        if not line or line_lower.startswith('!'):
            return ConstructKind.UNKNOWN

        # READ/WRITE/PRINT statements
        if line_lower.startswith('read'):
            return ConstructKind.IO_STATEMENT
        
        if line_lower.startswith('write'):
            return ConstructKind.IO_STATEMENT
            
        if line_lower.startswith('print'):
            return ConstructKind.PRINT_STATEMENT

        # STOP statement
        if line_lower.startswith('stop'):
            return ConstructKind.UNKNOWN

        # WHERE construct
        if line_lower.startswith('where'):
            return ConstructKind.WHERE

        # FORALL construct
        if line_lower.startswith('forall'):
            return ConstructKind.FORALL

        # DO CONCURRENT
        if 'do concurrent' in line_lower:
            return ConstructKind.DO_CONCURRENT

        # Regular DO loop
        if line_lower.startswith('do ') and 'concurrent' not in line_lower:
            return ConstructKind.DO

        # IF construct
        if line_lower.startswith('if ') and ' then' in line_lower:
            return ConstructKind.IF

        # SELECT CASE
        if line_lower.startswith('select case'):
            return ConstructKind.SELECT_CASE

        # Assignment (but not in control structures)
        if '=' in line and not any(x in line_lower for x in ['if', 'do', 'where', 'select', 'end']):
            # Array assignment patterns
            array_patterns = [
                '[', ']', '(:,', '(:', ',:)', '%)',  # Array syntax
                '(/', '/)',  # Array constructors with (/ ... /)
                'reshape(', 'spread(', 'pack(', 'unpack(',  # Array functions
                'array(', 'section(',  # Array operations
            ]
            if any(pattern in line for pattern in array_patterns):
                return ConstructKind.ARRAY_ASSIGN
            else:
                return ConstructKind.SCALAR_ASSIGN

        # Intrinsic function call
        if 'call' in line_lower:
            intrinsics = ['sin', 'cos', 'sqrt', 'exp', 'log', 'abs', 'min', 'max', 'dot_product']
            if any(x in line_lower for x in intrinsics):
                return ConstructKind.INTRINSIC_CALL
            else:
                return ConstructKind.USER_CALL

        return ConstructKind.UNKNOWN

    def _extract_variables(self, text: str) -> List[str]:
        """Extract variable names from text."""
        # Match Fortran identifiers (alphanumeric + underscore, starting with letter)
        pattern = r'\b([a-zA-Z_]\w*)\b'
        matches = re.findall(pattern, text)

        # Filter out Fortran keywords
        keywords = {'do', 'end', 'if', 'then', 'else', 'where', 'forall', 'program',
                    'subroutine', 'function', 'real', 'integer', 'logical', 'character',
                    'call', 'return', 'continue', 'exit', 'cycle', 'select', 'case',
                    'allocate', 'deallocate', 'concurrent', 'value', 'intent', 'in', 'out',
                    'inout', 'implicit', 'none', 'contains', 'module', 'use', 'only'}

        variables = [m for m in matches if m.lower() not in keywords]
        return list(set(variables))  # Remove duplicates

    def _extract_operators(self, text: str) -> List[str]:
        """Extract operators from text."""
        operators = []

        for op in ['+', '-', '*', '/', '**', '//', '==', '/=', '<', '>', '<=', '>=', '.and.', '.or.', '.not.']:
            if op in text:
                operators.append(op)

        return operators

    def get_construct_id(self, line_number: int) -> Optional[ConstructID]:
        """Get the construct ID for a specific source line."""
        for cid in self.constructs.values():
            if cid.line_range[0] <= line_number <= cid.line_range[1]:
                return cid

        return None

    def match_source_range_to_id(self, source_range: str) -> Optional[ConstructID]:
        """Match an MLIR source range to a construct ID."""
        normalized = normalize_source_range(source_range)

        for cid in self.constructs.values():
            if cid.source_range == normalized:
                return cid

        return None


class ProvenanceTracker:
    """Tracks construct propagation through compilation stages."""

    def __init__(self):
        self.mappings: Dict[str, Dict[str, List]] = {
            'parse_tree': {},      # construct_id -> parse tree nodes
            'semantics': {},       # construct_id -> semantic symbols
            'hlfir': {},          # construct_id -> HLFIR operations
            'fir': {},            # construct_id -> FIR operations (one-to-many)
            'llvm': {},           # construct_id -> LLVM instructions
        }

    def map_construct_at_stage(self, construct_id: str, stage: str, data: List):
        """Map a construct to operations at a specific stage."""
        if stage not in self.mappings:
            self.mappings[stage] = {}

        if construct_id not in self.mappings[stage]:
            self.mappings[stage][construct_id] = []

        self.mappings[stage][construct_id].extend(data)

    def get_construct_pipeline(self, construct_id: str) -> Dict[str, List]:
        """Get the full pipeline representation of a construct."""
        return {stage: self.mappings[stage].get(construct_id, [])
                for stage in self.mappings.keys()}

    def get_fir_operations_for_construct(self, construct_id: str) -> List:
        """Get all FIR operations for a construct (one-to-many mapping)."""
        return self.mappings['fir'].get(construct_id, [])

    def get_correlations(self, construct_id: str) -> Dict:
        """Get all correlations for a construct across stages."""
        return {
            'construct_id': construct_id,
            'stages': {stage: len(ops) for stage, ops in self.mappings.items()},
            'pipeline': self.get_construct_pipeline(construct_id),
        }
