#ftrace/engine.py
import json
import logging
from typing import Dict, List, Optional

from .compiler_interface import CompilerInterface, FlangNotFoundError
from .provenance import ProvenanceCorrelationEngine

logger = logging.getLogger(__name__)


class TraceBundle:
    """Container for trace results with metadata."""
    
    def __init__(self):
        self.nodes = []
        self.metadata = {}

    def add_node(self, node: Dict):
        """Add a correlated construct to the bundle."""
        if self._validate_node(node):
            self.nodes.append(node)
            return True
        return False

    def _validate_node(self, node: Dict) -> bool:
        """Validate node structure."""
        required_fields = ['construct', 'source', 'metadata']
        return isinstance(node, dict) and all(field in node for field in required_fields)

    def set_metadata(self, key: str, value):
        """Set bundle-level metadata."""
        self.metadata[key] = value

    def to_dict(self):
        """Export to dictionary."""
        return {
            "metadata": self.metadata,
            "nodes": self.nodes
        }


class SemanticCorrelationEngine:
    """
    Semantic correlation engine using provenance-based tracing.
    
    This engine replaces the old generic correlation with semantic-aware
    extraction at each stage:
    - Parse Tree: AST constructs (AssignmentStmt, Variable, Expr, etc.)
    - Semantics: Symbol table and type information
    - HLFIR: High-level Fortran IR with semantic structure
    - FIR: Lowered SSA IR with one-to-many operation mapping
    - LLVM IR: Machine code with debug metadata
    """

    def __init__(self):
        self.bundle = TraceBundle()
        self.provenance_engine: Optional[ProvenanceCorrelationEngine] = None
        self.correlation_stats: Dict = {}

    def trace_with_real_compiler(self, fortran_code: str) -> TraceBundle:
        """Trace Fortran code through all compilation stages using provenance.
        
        This is the main entry point for semantic correlation.
        """
        try:
            logger.info("Starting semantic correlation with provenance engine")
            
            # Compile to all stages
            compiler = CompilerInterface()
            stages = compiler.compile_to_stages(fortran_code)

            # Create provenance engine with all stage dumps
            self.provenance_engine = ProvenanceCorrelationEngine(
                fortran_code=fortran_code,
                parse_tree=stages['parse_tree'],
                semantics=stages['semantics'],
                hlfir=stages['hlfir'],
                fir=stages['fir'],
                llvm_ir=stages['llvm_ir']
            )

            # Perform semantic correlation
            correlations = self.provenance_engine.correlate()

            # Build trace bundle
            self.bundle = TraceBundle()

            for correlation in correlations:
                node = correlation.to_dict()
                self.bundle.add_node(node)

            # Gather statistics
            self.correlation_stats = self.provenance_engine.get_correlation_stats()
            self.bundle.set_metadata('correlation_stats', self.correlation_stats)
            self.bundle.set_metadata('num_constructs', len(correlations))

            logger.info(f"Tracing complete: {len(correlations)} constructs correlated")
            logger.info(f"Correlation rate: {self.correlation_stats['correlation_rate']:.1f}%")

            return self.bundle

        except FlangNotFoundError as e:
            logger.error(f"Flang compiler not found: {e}")
            raise
        except Exception as e:
            logger.error(f"Tracing failed: {e}", exc_info=True)
            raise

    def get_stats(self) -> Dict:
        """Get correlation statistics."""
        if not self.provenance_engine:
            return {}
        return self.provenance_engine.get_correlation_stats()


# Legacy API for backward compatibility
class CorrelationEngine:
    """Legacy correlation engine. Use SemanticCorrelationEngine instead."""
    
    def __init__(self):
        self.semantic_engine = SemanticCorrelationEngine()
        self.bundle = TraceBundle()

    def trace_with_real_compiler(self, fortran_code: str) -> TraceBundle:
        """Delegate to semantic engine for backward compatibility."""
        return self.semantic_engine.trace_with_real_compiler(fortran_code)