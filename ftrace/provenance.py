"""
Provenance-based correlation engine.

Core strategy
-------------
* Parse all five stage dumps.
* Identify source constructs (from parse tree + source text fallback) with
  stable line ranges.
* For every construct, collect IR ops whose ``loc()`` attribute (HLFIR/FIR)
  or resolved ``!dbg`` line (LLVM IR) falls within the construct's line range.
  This is the *only* correct one-to-many mapping — no type-bucket heuristics.
* Fall back to type-based heuristics only when ``-g`` was not used and loc
  attributes are absent.
"""

import re
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

from .stage_parsers import (
    ParseTreeParser, SemanticsParser, HLFIRParser, FIRParser, LLVMParser,
    ParseTreeConstruct, SemanticSymbol, IROperation,
)
from .construct_id import (
    ConstructIdentifier, ProvenanceTracker, ConstructID, ConstructKind,
)
from .hlfir_anchoring import HLFIRAnchoredCorrelationEngine, HLFIRAnchor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class CorrelatedConstruct:
    """A source construct correlated across all compilation stages."""
    construct_id: ConstructID
    source_text: str
    parse_tree: List[ParseTreeConstruct]
    semantics: List[SemanticSymbol]
    hlfir_ops: List[IROperation]
    fir_ops: List[IROperation]
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
            },
        }


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class ProvenanceCorrelationEngine:
    """Provenance-based correlation across all Flang compilation stages."""

    def __init__(self, fortran_code: str, parse_tree: str, semantics: str,
                 hlfir: str, fir: str, llvm_ir: str):
        self.source = fortran_code
        self.source_lines = fortran_code.split('\n')

        self.construct_id_gen = ConstructIdentifier(fortran_code)
        self.constructs: Dict[str, ConstructID] = {}

        self.parse_tree_parser = ParseTreeParser(parse_tree, fortran_code)
        self.semantics_parser  = SemanticsParser(semantics)
        self.hlfir_parser      = HLFIRParser(hlfir)
        self.fir_parser        = FIRParser(fir)
        self.llvm_parser       = LLVMParser(llvm_ir)

        self.provenance = ProvenanceTracker()

        self.parse_tree_constructs: List[ParseTreeConstruct] = []
        self.semantics_symbols: Dict[str, SemanticSymbol] = {}
        self.hlfir_ops: List[IROperation] = []
        self.fir_ops:  List[IROperation] = []
        self.llvm_instrs: List[Dict] = []

        self.hlfir_anchors: Dict[str, HLFIRAnchor] = {}
        self.correlations: Dict[str, CorrelatedConstruct] = {}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def correlate(self) -> List[CorrelatedConstruct]:
        logger.info("Starting provenance correlation")

        self._parse_all_stages()
        self._identify_constructs()
        self._build_correlations()

        # Compute stats
        n_fir_with_loc = sum(1 for op in self.fir_ops if op.src_line)
        n_llvm_with_loc = sum(1 for i in self.llvm_instrs if i.get('src_line'))
        logger.info(
            f"Stage sizes — parse_tree: {len(self.parse_tree_constructs)}, "
            f"hlfir: {len(self.hlfir_ops)}, fir: {len(self.fir_ops)} "
            f"({n_fir_with_loc} with loc), "
            f"llvm: {len(self.llvm_instrs)} ({n_llvm_with_loc} with loc)"
        )
        logger.info(f"Correlation complete: {len(self.correlations)} constructs")
        return list(self.correlations.values())

    # ------------------------------------------------------------------
    # Step 1 – parse all stage dumps
    # ------------------------------------------------------------------

    def _parse_all_stages(self):
        self.parse_tree_constructs = self.parse_tree_parser.parse()
        self.semantics_symbols     = self.semantics_parser.parse()
        self.hlfir_ops             = self.hlfir_parser.parse()
        self.fir_ops               = self.fir_parser.parse()
        self.llvm_instrs           = self.llvm_parser.parse()
        logger.debug(
            f"Parsed stages: pt={len(self.parse_tree_constructs)} "
            f"sym={len(self.semantics_symbols)} "
            f"hlfir={len(self.hlfir_ops)} fir={len(self.fir_ops)} "
            f"llvm={len(self.llvm_instrs)}"
        )

    # ------------------------------------------------------------------
    # Step 2 – identify constructs
    # ------------------------------------------------------------------

    def _identify_constructs(self):
        """Build self.constructs from parse tree (primary) + source text (fallback)."""
        # Primary: parse tree gives us actual AST nodes with kinds
        pt_ids = self.construct_id_gen.identify_from_parse_tree(
            [c.to_dict() for c in self.parse_tree_constructs]
        )
        self.constructs.update(pt_ids)

        # Fallback: scan source text for any constructs missed by the parse tree
        src_ids = self.construct_id_gen.identify_from_source_text()
        for hid, c in src_ids.items():
            if hid in self.constructs:
                continue
            # Don't add if line range overlaps an existing construct
            if any(
                c.line_range[0] <= ex.line_range[1] and ex.line_range[0] <= c.line_range[1]
                for ex in self.constructs.values()
            ):
                continue
            self.constructs[hid] = c

        # Remove constructs we failed to locate in source
        before = len(self.constructs)
        self.constructs = {
            hid: c for hid, c in self.constructs.items()
            if c.line_range != (0, 0)
        }
        dropped = before - len(self.constructs)
        if dropped:
            logger.info(f"Dropped {dropped} unlocated constructs")

    # ------------------------------------------------------------------
    # Step 3 – build correlations
    # ------------------------------------------------------------------

    def _build_correlations(self):
        for hid, construct in self.constructs.items():
            src_text = self._get_source_text(construct)
            pt_nodes = self._find_parse_tree_constructs(construct)
            symbols  = self._find_semantics(construct)
            hlfir    = self._find_hlfir(construct)
            fir      = self._find_fir(construct)
            llvm     = self._find_llvm(construct)

            self.correlations[hid] = CorrelatedConstruct(
                construct_id=construct,
                source_text=src_text,
                parse_tree=pt_nodes,
                semantics=symbols,
                hlfir_ops=hlfir,
                fir_ops=fir,
                llvm_instrs=llvm,
            )

    # ------------------------------------------------------------------
    # Source text
    # ------------------------------------------------------------------

    def _get_source_text(self, construct: ConstructID) -> str:
        start, end = construct.line_range
        if start == 0:
            return ""
        lines = self.source_lines[start - 1: end]
        return '\n'.join(lines).strip()

    # ------------------------------------------------------------------
    # Per-construct stage lookups
    # ------------------------------------------------------------------

    def _find_parse_tree_constructs(self, c: ConstructID) -> List[ParseTreeConstruct]:
        results = []
        for pt in self.parse_tree_constructs:
            if self._line_ranges_overlap(c.line_range, pt.line_range):
                results.append(pt)
        return results

    def _find_semantics(self, c: ConstructID) -> List[SemanticSymbol]:
        return [
            sym for name, sym in self.semantics_symbols.items()
            if name in (v.lower() for v in c.variables)
        ]

    def _find_hlfir(self, c: ConstructID) -> List[IROperation]:
        """Find HLFIR ops whose loc() line falls within the construct's range."""
        start, end = c.line_range
        by_loc = [op for op in self.hlfir_ops
                  if op.src_line and start <= op.src_line <= end]
        if by_loc:
            return by_loc
        # Fallback: variable-name overlap
        return self._find_ir_by_vars(self.hlfir_ops, c)

    def _find_fir(self, c: ConstructID) -> List[IROperation]:
        """
        Find FIR ops whose loc() line falls within the construct's source range.

        This is the correct one-to-many mapping: every FIR operation that the
        compiler lowered from construct lines [start, end] is included.
        """
        start, end = c.line_range
        by_loc = [op for op in self.fir_ops
                  if op.src_line and start <= op.src_line <= end]
        if by_loc:
            return by_loc
        # Fallback: kind-based heuristic (used when -g is absent)
        return self._find_fir_by_kind_heuristic(c)

    def _find_llvm(self, c: ConstructID) -> List[Dict]:
        """Find LLVM instructions whose !dbg line falls within the construct's range."""
        start, end = c.line_range
        by_loc = [instr for instr in self.llvm_instrs
                  if instr.get('src_line') and start <= instr['src_line'] <= end]
        if by_loc:
            return by_loc
        # Fallback: variable-name text search
        return self._find_llvm_by_vars(c)

    # ------------------------------------------------------------------
    # Fallback heuristics (used only when loc() data is absent)
    # ------------------------------------------------------------------

    def _find_ir_by_vars(self, ops: List[IROperation], c: ConstructID) -> List[IROperation]:
        """Return ops that mention at least one variable from this construct."""
        if not c.variables:
            return []
        results = []
        for op in ops:
            text = op.raw.lower()
            if any(v.lower() in text for v in c.variables):
                results.append(op)
        return results

    def _find_fir_by_kind_heuristic(self, c: ConstructID) -> List[IROperation]:
        """
        Last-resort FIR matching by construct kind.

        Unlike the old implementation, we restrict to ops that mention at least
        one of the construct's variables to avoid the "same FIR for all" bug.
        """
        kind_op_map = {
            ConstructKind.ARRAY_ASSIGN:  {'fir.store', 'fir.load', 'fir.array_coor',
                                          'fir.array_update', 'hlfir.assign'},
            ConstructKind.SCALAR_ASSIGN: {'fir.store', 'fir.load', 'hlfir.assign'},
            ConstructKind.WHERE:         {'fir.where', 'hlfir.where', 'fir.array_coor'},
            ConstructKind.WHERE_MASKED:  {'fir.where', 'hlfir.where'},
            ConstructKind.FORALL:        {'fir.do_loop', 'hlfir.forall', 'fir.array_coor'},
            ConstructKind.DO:            {'fir.do_loop', 'fir.load', 'fir.store'},
            ConstructKind.DO_CONCURRENT: {'fir.do_loop', 'fir.array_coor'},
            ConstructKind.IF:            {'cf.cond_br', 'fir.if', 'cf.br'},
        }
        target_ops = kind_op_map.get(c.kind, {'fir.store', 'fir.load'})
        variables_lower = {v.lower() for v in c.variables}

        candidates = []
        for op in self.fir_ops:
            if op.op_name not in target_ops:
                continue
            # Must mention at least one variable (prevents shared-bucket problem)
            if variables_lower and not any(v in op.raw.lower() for v in variables_lower):
                continue
            candidates.append(op)

        return candidates

    def _find_llvm_by_vars(self, c: ConstructID) -> List[Dict]:
        if not c.variables:
            return []
        results = []
        for instr in self.llvm_instrs:
            text = instr.get('line', '').lower()
            if any(v.lower() in text for v in c.variables):
                results.append(instr)
        return results

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_correlation_stats(self) -> Dict:
        """Return statistics about the correlation results."""
        if not self.correlations:
            return {
                'total_constructs': 0,
                'correlated_constructs': 0,
                'correlation_rate': 0.0,
                'avg_fir_ops_per_construct': 0.0,
            }

        total = len(self.correlations)
        correlated = sum(
            1 for c in self.correlations.values()
            if c.fir_ops and c.llvm_instrs
        )
        total_fir = sum(len(c.fir_ops) for c in self.correlations.values())

        return {
            'total_constructs': total,
            'correlated_constructs': correlated,
            'correlation_rate': (correlated / total * 100) if total else 0.0,
            'avg_fir_ops_per_construct': total_fir / total if total else 0.0,
        }

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _line_ranges_overlap(r1: Tuple[int, int], r2: Tuple[int, int]) -> bool:
        return not (r1[1] < r2[0] or r2[1] < r1[0])
