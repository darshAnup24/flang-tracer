"""
HLFIR-anchored correlation engine.

This module implements the semantic anchoring strategy:
- Use HLFIR operations as semantic anchors for constructs
- Map FIR subgraphs to HLFIR anchors
- Track SSA dependencies through FIR → LLVM
- Score correlation confidence
"""

import re
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .stage_parsers import IROperation
from .construct_id import ConstructID, ConstructKind

logger = logging.getLogger(__name__)


@dataclass
class FIRSubgraph:
    """A connected subgraph of FIR operations."""
    root_op: IROperation
    operations: List[IROperation] = field(default_factory=list)
    variables: Set[str] = field(default_factory=set)
    operand_chain: List[str] = field(default_factory=list)  # SSA value chain
    
    def add_op(self, op: IROperation):
        self.operations.append(op)
        # Extract variables from operands and results
        for operand in op.operands:
            if operand.startswith('%'):
                self.operand_chain.append(operand)
    
    def to_dict(self):
        return {
            'root': self.root_op.op_name,
            'num_ops': len(self.operations),
            'variables': list(self.variables),
            'operand_chain': self.operand_chain[:5]  # First 5 SSA values
        }


@dataclass
class CorrelationScore:
    """Confidence score for a correlation."""
    hlfir_match: float = 0.0  # How well HLFIR ops match construct
    fir_structure: float = 0.0  # How complete is FIR subgraph
    ssa_lineage: float = 0.0  # How clear is SSA dependency chain
    variable_overlap: float = 0.0  # Variable name matches
    overall: float = 0.0
    
    def compute_overall(self):
        self.overall = (
            self.hlfir_match * 0.4 +
            self.variable_overlap * 0.3 +
            self.fir_structure * 0.2 +
            self.ssa_lineage * 0.1
        )
        return self.overall


class HLFIRAnchor:
    """Represents a semantic anchor from HLFIR."""
    
    def __init__(self, ops: List[IROperation], construct: ConstructID):
        self.ops = ops
        self.construct = construct
        self.fir_subgraph: Optional[FIRSubgraph] = None
        self.llvm_chain: List[Dict] = []
        self.confidence: CorrelationScore = CorrelationScore()
    
    def extract_variables_from_ops(self) -> Set[str]:
        """Extract all variables referenced in HLFIR operations."""
        variables = set()
        for op in self.ops:
            # Extract variable names from operands
            for operand in op.operands:
                # Filter SSA values
                if not operand.startswith('%'):
                    variables.add(operand.lower())
        return variables


class FIRStructuralAnalyzer:
    """Analyzes FIR operations to build subgraphs for constructs."""
    
    def __init__(self, all_fir_ops: List[IROperation]):
        self.all_ops = all_fir_ops
        self.ssa_def_map: Dict[str, IROperation] = {}  # %val -> defining op
        self.ssa_use_map: Dict[str, List[IROperation]] = defaultdict(list)  # %val -> using ops
        self._build_ssa_graph()
    
    def _build_ssa_graph(self):
        """Build SSA value def-use chains."""
        for op in self.all_ops:
            # Map results
            for result in op.results:
                if result.startswith('%'):
                    self.ssa_def_map[result] = op
            
            # Map operands
            for operand in op.operands:
                if operand.startswith('%'):
                    self.ssa_use_map[operand].append(op)
    
    def extract_subgraph_for_root(self, root_op: IROperation, 
                                   max_depth: int = 1) -> FIRSubgraph:
        """Extract a connected subgraph starting from a root operation.
        
        We keep max_depth very shallow to avoid pulling in unrelated operations.
        """
        subgraph = FIRSubgraph(root_op=root_op)
        visited = set()
        queue = [(root_op, 0)]
        
        while queue:
            op, depth = queue.pop(0)
            
            if depth > max_depth or id(op) in visited:
                continue
            
            visited.add(id(op))
            subgraph.add_op(op)
            
            # Only follow very limited chains
            if depth == 0:
                # At root level, only follow first direct use
                for result in op.results:
                    if result in self.ssa_use_map and self.ssa_use_map[result]:
                        using_op = self.ssa_use_map[result][0]
                        if id(using_op) not in visited:
                            queue.append((using_op, depth + 1))
                
                # And first direct dependency
                if op.operands:
                    operand = op.operands[0]
                    if operand in self.ssa_def_map:
                        def_op = self.ssa_def_map[operand]
                        if id(def_op) not in visited:
                            queue.append((def_op, depth + 1))
        
        return subgraph
    
    def extract_subgraphs_for_hlfir_ops(self, hlfir_ops: List[IROperation]) -> List[FIRSubgraph]:
        """Extract FIR subgraphs that correspond to HLFIR operations."""
        if not hlfir_ops:
            return []
        
        # Find ONLY the root FIR operations for the main HLFIR operations
        subgraphs = []
        seen_roots = set()
        
        # Focus on the primary assignment/store operations in FIR
        primary_fir_ops = [op for op in self.all_ops if op.op_name in {'fir.store', 'hlfir.assign', 'arith.addi', 'arith.addf'}]
        
        for fir_op in primary_fir_ops[:3]:  # Only first 3 relevant FIR ops
            if id(fir_op) not in seen_roots:
                subgraph = self.extract_subgraph_for_root(fir_op, max_depth=1)
                if subgraph.operations:
                    subgraphs.append(subgraph)
                    seen_roots.add(id(fir_op))
        
        return subgraphs


class SSATracker:
    """Tracks SSA value chains through LLVM IR."""
    
    def __init__(self, llvm_instrs: List[Dict]):
        self.instrs = llvm_instrs
        self.ssa_def_map: Dict[str, Dict] = {}  # %val -> defining instr
        self.ssa_use_map: Dict[str, List[Dict]] = defaultdict(list)  # %val -> using instrs
        self._build_ssa_graph()
    
    def _build_ssa_graph(self):
        """Build SSA value def-use chains for LLVM."""
        for instr in self.instrs:
            line = instr.get('line', '')
            
            # Extract assignment: %val = ...
            match = re.search(r'(%[\w\.]+)\s*=', line)
            if match:
                result = match.group(1)
                self.ssa_def_map[result] = instr
            
            # Extract operands: any %val references
            for operand in re.findall(r'%[\w\.]+', line):
                if operand not in self.ssa_def_map:
                    self.ssa_use_map[operand].append(instr)
    
    def trace_value_chain(self, start_val: str, max_depth: int = 2) -> List[Dict]:
        """Trace an SSA value through its definition and uses."""
        chain = []
        visited = set()
        queue = [(start_val, 0)]
        
        while queue:
            val, depth = queue.pop(0)
            
            if depth > max_depth or val in visited:
                continue
            
            visited.add(val)
            
            # Add defining instruction
            if val in self.ssa_def_map:
                instr = self.ssa_def_map[val]
                chain.append(instr)
                
                if depth < max_depth:
                    # Follow input operands conservatively
                    for operand in re.findall(r'%[\w\.]+', instr.get('line', ''))[:2]:
                        if operand not in visited:
                            queue.append((operand, depth + 1))
            
            # Add using instructions (only first 2)
            if val in self.ssa_use_map:
                for instr in self.ssa_use_map[val][:2]:
                    if instr not in chain:
                        chain.append(instr)
        
        return chain


class HLFIRAnchoredCorrelationEngine:
    """
    Main correlation engine using HLFIR as semantic anchors.
    
    Architecture:
    Source Construct → HLFIR Anchor → FIR Subgraph → LLVM SSA Chain → Confidence Score
    """
    
    def __init__(self, constructs: Dict[str, ConstructID], 
                 hlfir_ops: List[IROperation],
                 fir_ops: List[IROperation],
                 llvm_instrs: List[Dict]):
        self.constructs = constructs
        self.hlfir_ops = hlfir_ops
        self.fir_ops = fir_ops
        self.llvm_instrs = llvm_instrs
        
        self.fir_analyzer = FIRStructuralAnalyzer(fir_ops)
        self.ssa_tracker = SSATracker(llvm_instrs)
        
        self.anchors: Dict[str, HLFIRAnchor] = {}
    
    def correlate(self) -> Dict[str, HLFIRAnchor]:
        """Perform HLFIR-anchored correlation."""
        self.anchors = {}
        
        for construct_hash, construct in self.constructs.items():
            logger.debug(f"Correlating construct: {construct}")
            
            # Step 1: Find HLFIR anchor
            hlfir_ops = self._find_hlfir_anchor(construct)
            if not hlfir_ops:
                logger.debug(f"No HLFIR anchor found for {construct}")
                continue
            
            # Step 2: Create anchor
            anchor = HLFIRAnchor(hlfir_ops, construct)
            
            # Step 3: Extract FIR subgraph
            anchor.fir_subgraph = self._extract_fir_subgraph(anchor)
            
            # Step 4: Trace LLVM chain
            anchor.llvm_chain = self._trace_llvm_chain(anchor)
            
            # Step 5: Score confidence
            anchor.confidence = self._score_confidence(anchor)
            
            self.anchors[construct_hash] = anchor
        
        return self.anchors
    
    def _find_hlfir_anchor(self, construct: ConstructID) -> List[IROperation]:
        """Find HLFIR operations matching the construct kind and variables."""
        candidates = []
        construct_vars = set(v.lower() for v in construct.variables)
        
        for op in self.hlfir_ops:
            # Match by operation type
            matched = False
            if construct.kind == ConstructKind.ARRAY_ASSIGN:
                if op.op_name in {'hlfir.assign', 'hlfir.elemental', 'hlfir.designate'}:
                    matched = True
            elif construct.kind == ConstructKind.SCALAR_ASSIGN:
                if op.op_name == 'hlfir.assign':
                    matched = True
            elif construct.kind in {ConstructKind.IO_STATEMENT, ConstructKind.PRINT_STATEMENT}:
                if 'hlfir' not in op.op_name:
                    matched = True  # I/O might not have HLFIR
            
            if matched:
                candidates.append(op)
        
        # Limit to 3 most relevant ops
        return candidates[:3]
    
    def _extract_fir_subgraph(self, anchor: HLFIRAnchor) -> FIRSubgraph:
        """Extract FIR subgraph corresponding to HLFIR anchor, filtered by construct variables."""
        if not anchor.ops:
            return FIRSubgraph(root_op=None)
        
        # Get construct variables for filtering
        construct_vars = set(v.lower() for v in anchor.construct.variables)
        
        # Use first HLFIR op to find corresponding FIR subgraph
        subgraphs = self.fir_analyzer.extract_subgraphs_for_hlfir_ops(anchor.ops)
        
        if subgraphs:
            # Merge and filter subgraphs by variable references
            merged_ops = []
            seen_ids = set()
            
            for subgraph in subgraphs:
                for op in subgraph.operations:
                    op_id = id(op)
                    if op_id not in seen_ids:
                        # Check if op references any construct variables
                        op_text = str(op.operands + op.results).lower()
                        # Keep ops that reference construct vars, or keep first few anyway
                        if any(var in op_text for var in construct_vars) or len(merged_ops) < 3:
                            merged_ops.append(op)
                            seen_ids.add(op_id)
            
            if merged_ops:
                return FIRSubgraph(root_op=merged_ops[0], operations=merged_ops, variables={}, operand_chain=[])
        
        return FIRSubgraph(root_op=None)
    
    def _trace_llvm_chain(self, anchor: HLFIRAnchor) -> List[Dict]:
        """Trace LLVM SSA chain from FIR subgraph."""
        if not anchor.fir_subgraph or not anchor.fir_subgraph.operand_chain:
            return []
        
        # Start from first 2 SSA values only (most relevant)
        chains = []
        for ssa_val in anchor.fir_subgraph.operand_chain[:2]:
            chain = self.ssa_tracker.trace_value_chain(ssa_val, max_depth=2)
            chains.extend(chain)
        
        # Limit total LLVM instructions
        return chains[:10]
    
    def _score_confidence(self, anchor: HLFIRAnchor) -> CorrelationScore:
        """Score the confidence of a correlation."""
        score = CorrelationScore()
        
        # HLFIR match: how many ops found
        score.hlfir_match = min(1.0, len(anchor.ops) / 3.0)
        
        # Variable overlap
        construct_vars = set(anchor.construct.variables)
        if construct_vars:
            # Extract variables from HLFIR operands (approximate)
            hlfir_vars = set()
            for op in anchor.ops:
                for operand in op.operands:
                    if not operand.startswith('%'):
                        hlfir_vars.add(operand.lower())
            
            overlap = len(construct_vars & hlfir_vars) / len(construct_vars) if construct_vars else 0
            score.variable_overlap = min(1.0, overlap)
        
        # FIR structure: how complete is the subgraph
        if anchor.fir_subgraph and anchor.fir_subgraph.operations:
            score.fir_structure = min(1.0, len(anchor.fir_subgraph.operations) / 8.0)
        
        # SSA lineage: how clear is LLVM chain
        if anchor.llvm_chain:
            score.ssa_lineage = min(1.0, len(anchor.llvm_chain) / 5.0)
        
        score.compute_overall()
        return score
