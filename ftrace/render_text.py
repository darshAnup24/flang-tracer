from rich.console import Console
from rich.panel import Panel

console = Console()

def render_trace_to_terminal(trace_bundle):
    """Render the correlated trace bundle to text output."""
    for node in trace_bundle.get('nodes', []):
        console.print(Panel(f"Construct: {node.get('kind')} @ {node.get('src_range')}", title="Source Mapping"))
        # Render each stage representation side-by-side or stacked
        if 'parse_tree' in node:
            console.print(Panel(node['parse_tree'], title="Stage 0: Parse Tree", style="blue"))
        if 'llvm_ir' in node:
            console.print(Panel(node['llvm_ir'], title="Stage 4: LLVM IR", style="red"))
