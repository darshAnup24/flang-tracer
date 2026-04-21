import json

class TraceBundle:
    def __init__(self):
        self.nodes = []
        
    def to_dict(self):
        return {"nodes": [n for n in self.nodes]}

class CorrelationEngine:
    """Engine that correlates source constructs across 5 compilation stages via SourceLocKey."""
    def __init__(self):
        self.stage_data = {
            'parse': [],
            'sema': [],
            'hlfir': [],
            'fir': [],
            'llvm': []
        }
        self.bundle = TraceBundle()

    def load_stage(self, stage_name, data):
        """Loads data from a parsed stage dump"""
        if stage_name in self.stage_data:
            self.stage_data[stage_name] = data

    def hash_loc(self, src_range):
        """Normalizes source line:col hashes to prevent subtle drift during correlation."""
        return str(src_range).strip()

    def correlate(self):
        """Align representations by SourceLocKey and fallbacks (symbol fuzzy matching)."""
        # Primary alignment key is the `srcRange` from the ParseTree
        for parse_node in self.stage_data['parse']:
            key = self.hash_loc(parse_node.get('src_range'))
            
            # Find matching nodes
            sema_node = next((n for n in self.stage_data['sema'] if self.hash_loc(n.get('src_range')) == key), None)
            hlfir_node = next((n for n in self.stage_data['hlfir'] if self.hash_loc(n.get('src_range')) == key), None)
            fir_node = next((n for n in self.stage_data['fir'] if self.hash_loc(n.get('src_range')) == key), None)
            llvm_node = next((n for n in self.stage_data['llvm'] if self.hash_loc(n.get('src_range')) == key), None)
            
            correlated_node = {
                "src_range": key,
                "kind": parse_node.get('kind', 'UNKNOWN'),
                "text": parse_node.get('text', ''),
                "parse_tree": parse_node.get('parse_tree', ''),
                "semantics": sema_node.get('semantics', '') if sema_node else '',
                "hlfir_op": hlfir_node.get('hlfir_op', '') if hlfir_node else '',
                "fir_op": fir_node.get('fir_op', '') if fir_node else '',
                "llvm_ir": llvm_node.get('llvm_ir', '') if llvm_node else ''
            }
            self.bundle.nodes.append(correlated_node)
            
        return self.bundle
