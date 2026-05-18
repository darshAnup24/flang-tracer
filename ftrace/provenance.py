"""
Provenance-based correlation engine for semantic compilation tracing.

This module integrates construct identification, stage-specific parsing, and
one-to-many operation mapping using HLFIR as semantic anchors.
"""

import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass

from .stage_parsers import (
    ParseTreeParser, SemanticsParser, HLFIRParser, FIRParser, LLVMParser,
    ParseTreeConstruct, SemanticSymbol, IROperation
)
from .construct_id import (
    ConstructIdentifier, ProvenanceTracker, ConstructID, ConstructKind
)
from .hlfir_anchoring import HLFIRAnchoredCorrelationEngine, HLFIRAnchor

logger = logging.getLogger(__name__)


@dataclass
class CorrelatedConstruct:
    """Represents a construct with full pipeline correlation."""
    construct_id: ConstructID
    source_text: str
    parse_tree: List[ParseTreeConstruct]
    semantics: List[SemanticSymbol]
    hlfir_ops: List[IROperation]
    fir_ops: List[IROperation]  # One-to-many mapping
    llvm_instrs: List[Dict]

    def to_dict(self):
        return {
            'construct': self.construct_id.to_dict(),
            'source': self.source_text,
            'parse_tree': [c.to_dict() for c in self.parse_tree],
            'semantics': [s.to_dict() for s in self.semantics],
            'hlfir_ops': [op.to_dict() for op in self.hlfir_ops],
            'fir_ops': [op.to_dict() for op in self.fir_ops],
            'llvm_instrs': self.llvm_instrs,
            'metadata': {
                'num_hlfir_ops': len(self.hlfir_ops),
                'num_fir_ops': len(self.fir_ops),
                'num_llvm_instrs': len(self.llvm_instrs),
                'fully_correlated': bool(self.fir_ops and self.llvm_instrs),
            }
        }


class ProvenanceCorrelationEngine:
    """Main engine for provenance-based semantic correlation."""

    def __init__(self, fortran_code: str, parse_tree: str, semantics: str,
                 hlfir: str, fir: str, llvm_ir: str):
        """Initialize with all compilation stage dumps."""
        self.source = fortran_code
        self.source_lines = fortran_code.split('\n')

        # Initialize construct identification
        self.construct_id = ConstructIdentifier(fortran_code)
        # Start with empty constructs - will be populated from parse tree
        self.constructs = {}

        # Initialize stage parsers
        self.parse_tree_parser = ParseTreeParser(parse_tree, fortran_code)
        self.semantics_parser = SemanticsParser(semantics)
        self.hlfir_parser = HLFIRParser(hlfir)
        self.fir_parser = FIRParser(fir)
        self.llvm_parser = LLVMParser(llvm_ir)

        # Initialize provenance tracking
        self.provenance = ProvenanceTracker()

        # Parsed data
        self.parse_tree_constructs: List[ParseTreeConstruct] = []
        self.semantics_symbols: Dict[str, SemanticSymbol] = {}
        self.hlfir_ops: List[IROperation] = []
        self.fir_ops: List[IROperation] = []
        self.llvm_instrs: List[Dict] = []

        # HLFIR anchors for correlation
        self.hlfir_anchors: Dict[str, HLFIRAnchor] = {}

        # Correlation results
        self.correlations: Dict[str, CorrelatedConstruct] = {}

    def correlate(self) -> List[CorrelatedConstruct]:
        """Perform HLFIR-anchored semantic correlation across all stages."""
        logger.info("Starting HLFIR-anchored correlation")

        # Step 1: Parse all stages
        self._parse_all_stages()

        # Step 2: Identify and enhance constructs
        self._enhance_constructs_from_parse_tree()
        
        # Step 2a: Filter out invalid constructs
        self._filter_invalid_constructs()

        # Step 3: Use HLFIR-anchored correlation engine
        self._correlate_with_hlfir_anchoring()

        # Step 4: Build final results
        self._build_correlations()

        logger.info(f"Correlation complete: {len(self.correlations)} constructs")
        return list(self.correlations.values())

    def _parse_all_stages(self):
        """Parse all compilation stages."""
        logger.debug("Parsing all stages")
        self.parse_tree_constructs = self.parse_tree_parser.parse()
        self.semantics_symbols = self.semantics_parser.parse()
        self.hlfir_ops = self.hlfir_parser.parse()
        self.fir_ops = self.fir_parser.parse()
        self.llvm_instrs = self.llvm_parser.parse()

    def _enhance_constructs_from_parse_tree(self):
        """Identify constructs from parse tree and enhance with source-based identification."""
        # Get constructs from parse tree (primary source)
        pt_ids = self.construct_id.identify_from_parse_tree(
            [c.to_dict() for c in self.parse_tree_constructs]
        )
        
        # Merge parse tree constructs
        self.constructs.update(pt_ids)
        
        # Fallback: identify any missing constructs from source text
        source_ids = self.construct_id.identify_from_source_text()
        
        # Only add source-based constructs that don't conflict with parse tree ones
        for hash_id, construct in source_ids.items():
            if hash_id not in self.constructs:
                # Check if this source construct overlaps with any existing parse tree construct
                overlaps = False
                for existing in self.constructs.values():
                    if (construct.line_range[0] <= existing.line_range[1] and 
                        existing.line_range[0] <= construct.line_range[1]):
                        overlaps = True
                        break
                if not overlaps:
                    self.constructs[hash_id] = construct

    def _filter_invalid_constructs(self):
        """Filter out constructs with invalid line ranges."""
        # Remove constructs that couldn't be located in source (line range 0,0)
        valid_constructs = {}
        for hash_id, construct in self.constructs.items():
            if construct.line_range != (0, 0):
                valid_constructs[hash_id] = construct
        
        removed = len(self.constructs) - len(valid_constructs)
        if removed > 0:
            logger.info(f"Filtered out {removed} constructs with invalid line ranges")
        
        self.constructs = valid_constructs

    def _build_construct_pipelines(self):
        """Build the complete pipeline for each construct."""
        for construct_id, construct in self.constructs.items():
            logger.debug(f"Building pipeline for {construct}")

            # Get source range
            source_range = construct.source_range

            # Find matching parse tree constructs
            parse_tree = self._find_parse_tree_constructs(construct)
            self.provenance.map_construct_at_stage(construct_id, 'parse_tree', parse_tree)

            # Find matching semantics
            semantics = self._find_semantics_for_construct(construct)
            self.provenance.map_construct_at_stage(construct_id, 'semantics', semantics)

            # Find matching HLFIR operations
            hlfir = self._find_hlfir_for_construct(construct)
            self.provenance.map_construct_at_stage(construct_id, 'hlfir', hlfir)

            # Find matching FIR operations (one-to-many)
            fir = self._find_fir_for_construct(construct)
            self.provenance.map_construct_at_stage(construct_id, 'fir', fir)

            # Find matching LLVM instructions
            llvm = self._find_llvm_for_construct(construct)
            self.provenance.map_construct_at_stage(construct_id, 'llvm', llvm)

    def _find_parse_tree_constructs(self, construct: ConstructID) -> List[ParseTreeConstruct]:
        """Find parse tree constructs matching a construct ID."""
        results = []

        for pt_construct in self.parse_tree_constructs:
            # Match by construct kind and line range
            pt_kind = self._map_pt_kind_to_construct_kind(pt_construct.kind)

            if (pt_kind == construct.kind and
                self._line_ranges_overlap(construct.line_range, pt_construct.line_range)):
                results.append(pt_construct)

        return results

    def _find_semantics_for_construct(self, construct: ConstructID) -> List[SemanticSymbol]:
        """Find semantic symbols referenced in a construct."""
        results = []

        # Look for variables mentioned in the construct
        for var_name in construct.variables:
            if var_name in self.semantics_symbols:
                results.append(self.semantics_symbols[var_name])

        return results

    def _find_hlfir_for_construct(self, construct: ConstructID) -> List[IROperation]:
        """Find HLFIR operations for a construct using source range and heuristics."""
        results = []

        for op in self.hlfir_ops:
            if op.source_range and self._source_ranges_match(construct.source_range, op.source_range):
                results.append(op)

        if not results:
            results = self._find_hlfir_by_kind(construct)

        return results

    def _find_fir_for_construct(self, construct: ConstructID) -> List[IROperation]:
        """Find all FIR operations for a construct (one-to-many mapping)."""
        results = []

        for op in self.fir_ops:
            if op.source_range and self._source_ranges_match(construct.source_range, op.source_range):
                results.append(op)

        if not results and construct.source_range:
            norm_range = construct.source_range.replace(' ', '').lower()
            for sr, ops in self.fir_parser.construct_map.items():
                if sr.replace(' ', '').lower() == norm_range:
                    results.extend(ops)
                    break

        if not results:
            results = self._find_fir_by_kind(construct)

        if not results and len(construct.operators) > 0:
            results = self._find_fir_by_operators(construct.operators)

        return results

    def _find_llvm_for_construct(self, construct: ConstructID) -> List[Dict]:
        """Find LLVM instructions for a construct."""
        results = []

        # First try: match by debug location if available
        for instr in self.llvm_instrs:
            if instr.get('debug_loc'):
                results.append(instr)

        # If we found some, use them
        if results:
            return results

        # Second try: use only MOST SPECIFIC heuristics
        # Don't just grab ALL instructions mentioning the variable
        # Only match if this is the most likely candidate
        
        # For arithmetic operations related to the assignment
        if construct.kind in {ConstructKind.SCALAR_ASSIGN, ConstructKind.ARRAY_ASSIGN}:
            for instr in self.llvm_instrs:
                line = instr.get('line', '').lower()
                # Only include arithmetic operations
                if instr['op'] in {'add', 'sub', 'mul', 'sdiv', 'udiv', 'fadd', 'fsub', 'fmul', 'fdiv'}:
                    # Check if this operation involves our variables
                    if any(var.lower() in line for var in construct.variables):
                        results.append(instr)
                        if len(results) >= 10:  # Limit to 10 operations
                            break
        
        # For I/O statements
        elif construct.kind in {ConstructKind.IO_STATEMENT, ConstructKind.PRINT_STATEMENT}:
            for instr in self.llvm_instrs:
                if 'call' in instr['op']:
                    if any(x in instr.get('line', '').lower() for x in ['beginexternallist', 'outputdescriptor', 'iostatement', 'fortran']):
                        results.append(instr)
                        if len(results) >= 5:  # Limit to 5 operations
                            break

        return results

    def _find_hlfir_by_kind(self, construct: ConstructID) -> List[IROperation]:
        """Find HLFIR operations by construct kind with improved attribution."""
        candidates = []
        
        # Filter operations by construct kind
        for op in self.hlfir_ops:
            if construct.kind == ConstructKind.ARRAY_ASSIGN:
                # Array assignments typically involve elemental operations and designates
                if op.op_name in {'hlfir.assign', 'hlfir.elemental', 'hlfir.designate', 'hlfir.destroy'}:
                    candidates.append(op)
            elif construct.kind == ConstructKind.SCALAR_ASSIGN:
                # Scalar assignments are simpler
                if op.op_name in {'hlfir.assign', 'hlfir.designate'}:
                    candidates.append(op)
            elif construct.kind == ConstructKind.WHERE and 'hlfir.where' in op.op_name:
                candidates.append(op)
            elif construct.kind == ConstructKind.FORALL and 'hlfir' in op.op_name:
                candidates.append(op)
            elif construct.kind in {ConstructKind.DO, ConstructKind.DO_CONCURRENT} and 'hlfir' in op.op_name:
                candidates.append(op)
        
        # Instead of distributing across all constructs of same kind,
        # limit to a reasonable number per construct to avoid over-attribution
        max_ops_per_construct = min(5, len(candidates))
        return candidates[:max_ops_per_construct]

    def _find_fir_by_kind(self, construct: ConstructID) -> List[IROperation]:
        """Find FIR operations by construct kind with improved attribution."""
        candidates = []
        
        # For assignment constructs, match specific operation patterns
        if construct.kind in {ConstructKind.ARRAY_ASSIGN, ConstructKind.SCALAR_ASSIGN}:
            # Operations typically involved in assignments
            assignment_ops = {'fir.store', 'fir.load', 'fir.array_coor', 'arith.addi', 'arith.addf', 
                             'arith.subi', 'arith.subf', 'arith.muli', 'arith.mulf'}
            for op in self.fir_ops:
                if op.op_name in assignment_ops:
                    candidates.append(op)
        
        # For I/O operations
        elif construct.kind in {ConstructKind.IO_STATEMENT, ConstructKind.PRINT_STATEMENT}:
            for op in self.fir_ops:
                if 'call' in op.op_name or 'fir.call' in op.op_name:
                    candidates.append(op)
        
        # For loop constructs
        elif construct.kind in {ConstructKind.DO, ConstructKind.DO_CONCURRENT, ConstructKind.FORALL}:
            for op in self.fir_ops:
                if op.op_name == 'fir.do_loop':
                    candidates.append(op)
                    break  # Only one do_loop per construct
        
        # For WHERE constructs
        elif construct.kind == ConstructKind.WHERE:
            for op in self.fir_ops:
                if 'where' in op.op_name.lower():
                    candidates.append(op)
        
        # Limit operations per construct to avoid over-attribution
        max_ops_per_construct = 8 if construct.kind in {ConstructKind.ARRAY_ASSIGN, ConstructKind.SCALAR_ASSIGN} else 5
        return candidates[:max_ops_per_construct]

    def _find_llvm_by_variables(self, variables: List[str]) -> List[Dict]:
        """Find LLVM instructions that mention construct variables."""
        results = []
        for instr in self.llvm_instrs:
            line = instr.get('line', '').lower()
            for var in variables:
                if var.lower() in line:
                    results.append(instr)
                    break
        return results

    def _map_pt_kind_to_construct_kind(self, pt_kind: str) -> ConstructKind:
        """Map parse tree kind string to ConstructKind."""
        kind_lower = pt_kind.lower()
        if 'assignment' in kind_lower:
            return ConstructKind.SCALAR_ASSIGN
        elif 'where' in kind_lower:
            return ConstructKind.WHERE
        elif 'forall' in kind_lower:
            return ConstructKind.FORALL
        elif 'do' in kind_lower:
            if 'concurrent' in kind_lower:
                return ConstructKind.DO_CONCURRENT
            return ConstructKind.DO
        else:
            return ConstructKind.UNKNOWN

    def _line_ranges_overlap(self, range1: Tuple[int, int], range2: Tuple[int, int]) -> bool:
        """Check if two line ranges overlap."""
        return not (range1[1] < range2[0] or range2[1] < range1[0])

    def _source_ranges_match(self, sr1: str, sr2: str) -> bool:
        """Check if two source ranges match (with tolerance for minor differences).
        
        Handles:
        - Exact matches: "file.f90:10:1-10:20" == "file.f90:10:1-10:20"
        - Line overlaps: operations on same source line
        - Multi-line constructs: operations within construct range
        """
        if not sr1 or not sr2:
            return False

        # Normalize both ranges
        sr1_norm = sr1.replace(' ', '').lower()
        sr2_norm = sr2.replace(' ', '').lower()

        # Exact match
        if sr1_norm == sr2_norm:
            return True

        # Extract line numbers and compare
        import re
        def extract_lines(sr):
            """Extract all line numbers from a source range."""
            # Format: "file.f90:10:1-10:20" or "file.f90:10:1-15:20"
            matches = re.findall(r':(\d+):', sr)
            return set(int(m) for m in matches) if matches else set()

        def extract_line_range(sr):
            """Extract start and end line numbers."""
            # Format: "file.f90:10:1-10:20" means lines 10-10
            # Format: "file.f90:10:1-15:20" means lines 10-15
            match = re.search(r':(\d+):\d+-(\d+):\d+', sr)
            if match:
                start_line = int(match.group(1))
                end_line = int(match.group(2))
                return start_line, end_line
            return None

        # Check if line ranges overlap
        range1 = extract_line_range(sr1)
        range2 = extract_line_range(sr2)

        if range1 and range2:
            start1, end1 = range1
            start2, end2 = range2
            # Ranges overlap if one doesn't end before the other starts
            return not (end1 < start2 or end2 < start1)

        # Fallback: check if same line numbers appear
        lines1 = extract_lines(sr1)
        lines2 = extract_lines(sr2)

        # Same line numbers suggest related operations
        return bool(lines1 & lines2)

    def _find_fir_by_operators(self, operators: List[str]) -> List[IROperation]:
        """Heuristic FIR search by operators (integer and floating point)."""
        results = []

        # Map Fortran operators to FIR operations
        op_map = {
            '+': ['arith.addi', 'arith.addf', 'fir.load', 'fir.store'],
            '-': ['arith.subi', 'arith.subf', 'fir.load', 'fir.store'],
            '*': ['arith.muli', 'arith.mulf', 'fir.load', 'fir.store'],
            '/': ['arith.divsi', 'arith.divui', 'arith.divf', 'fir.load', 'fir.store'],
            '**': ['math.powi', 'math.powf'],
            '==': ['arith.cmpi', 'arith.cmpf'],
            '/=': ['arith.cmpi', 'arith.cmpf'],
            '<': ['arith.cmpi', 'arith.cmpf'],
            '>': ['arith.cmpi', 'arith.cmpf'],
            '<=': ['arith.cmpi', 'arith.cmpf'],
            '>=': ['arith.cmpi', 'arith.cmpf'],
        }

        for op in operators:
            fir_ops_to_match = op_map.get(op, [])
            for fir in self.fir_ops:
                for fir_op_pattern in fir_ops_to_match:
                    if fir_op_pattern in fir.op_name:
                        results.append(fir)
                        break

        return results

    def _find_llvm_by_operators(self, operators: List[str]) -> List[Dict]:
        """Heuristic LLVM search by operators (integer and floating point)."""
        results = []

        # Map Fortran operators to LLVM instructions
        op_map = {
            '+': ['add', 'fadd', 'load', 'store'],
            '-': ['sub', 'fsub', 'load', 'store'],
            '*': ['mul', 'fmul', 'load', 'store'],
            '/': ['sdiv', 'udiv', 'fdiv', 'load', 'store'],
            '**': ['llvm.powi', 'llvm.pow'],
            '==': ['icmp', 'fcmp'],
            '/=': ['icmp', 'fcmp'],
            '<': ['icmp', 'fcmp'],
            '>': ['icmp', 'fcmp'],
            '<=': ['icmp', 'fcmp'],
            '>=': ['icmp', 'fcmp'],
        }

        for op in operators:
            llvm_ops_to_match = op_map.get(op, [])
            for instr in self.llvm_instrs:
                for llvm_op_pattern in llvm_ops_to_match:
                    if llvm_op_pattern in instr.get('op', ''):
                        results.append(instr)
                        break

        return results

    def _correlate_operations(self):
        """Perform fine-grained operation correlation within constructs."""
        # This step is replaced by HLFIR anchoring
        pass

    def _correlate_with_hlfir_anchoring(self):
        """Use HLFIR as semantic anchors for correlation."""
        logger.info("Correlating constructs using HLFIR semantic anchors")
        
        # Create HLFIR-anchored correlation engine
        engine = HLFIRAnchoredCorrelationEngine(
            constructs=self.constructs,
            hlfir_ops=self.hlfir_ops,
            fir_ops=self.fir_ops,
            llvm_instrs=self.llvm_instrs
        )
        
        # Perform HLFIR-anchored correlation
        self.hlfir_anchors = engine.correlate()
        
        logger.info(f"Found {len(self.hlfir_anchors)} anchored correlations")

    def _build_correlations(self):
        """Build final correlation results from HLFIR anchors."""
        self.correlations = {}

        for construct_hash, anchor in self.hlfir_anchors.items():
            construct_id = anchor.construct
            
            # Get source text for this construct
            line_start, line_end = construct_id.line_range
            source_text = '\n'.join(self.source_lines[line_start - 1:line_end])
            
            # Get semantics for variables
            semantics = []
            for var in construct_id.variables:
                if var in self.semantics_symbols:
                    semantics.append(self.semantics_symbols[var])
            
            # Build correlated construct using HLFIR anchor data
            correlation = CorrelatedConstruct(
                construct_id=construct_id,
                source_text=source_text,
                parse_tree=[],  # Parse tree is secondary to HLFIR
                semantics=semantics,
                hlfir_ops=anchor.ops,
                fir_ops=anchor.fir_subgraph.operations if anchor.fir_subgraph else [],
                llvm_instrs=anchor.llvm_chain
            )
            
            self.correlations[construct_hash] = correlation

    def get_correlation_stats(self) -> Dict:
        """Get correlation statistics."""
        total = len(self.correlations)
        fully_correlated = sum(
            1 for c in self.correlations.values()
            if c.fir_ops and c.llvm_instrs
        )

        return {
            'total_constructs': total,
            'fully_correlated': fully_correlated,
            'correlation_rate': (fully_correlated / total * 100) if total > 0 else 0,
            'avg_fir_ops_per_construct': sum(
                len(c.fir_ops) for c in self.correlations.values()
            ) / total if total > 0 else 0,
        }
