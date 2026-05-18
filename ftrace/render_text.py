from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

console = Console()


def render_trace_to_terminal(trace_bundle):

    if not trace_bundle or not isinstance(trace_bundle, dict):
        console.print("[red]Error:[/red] Invalid trace bundle format")
        return

    nodes = trace_bundle.get('nodes', [])
    if not nodes:
        console.print("[yellow]No trace nodes found[/yellow]")
        return

    console.print()
    console.print("[bold cyan]Flang Multi-Stage Compilation Trace[/bold cyan]")
    console.print("=" * 80)
    console.print()

    for idx, node in enumerate(nodes, 1):

        if not isinstance(node, dict):
            continue

        src_range = node.get('src_range', f'Node {idx}')
        kind = node.get('kind', 'UNKNOWN')
        text = node.get('text', '').strip()

        console.print(f"[bold]Construct #{idx}: {kind} @ {src_range}[/bold]")
        console.print()

        # Source
        if text:
            console.print("[yellow]Source Code:[/yellow]")
            console.print(Syntax(text, "fortran", theme="monokai"))
            console.print()

        # Parse Tree
        parse_tree = (node.get('parse_tree') or '').strip()
        if parse_tree:
            console.print(Panel(parse_tree, title="Parse Tree (AST)", expand=False))
            console.print()

        # Semantics
        semantics = (node.get('semantics') or '').strip()
        if semantics:
            console.print(Panel(semantics, title="Semantics", expand=False))
            console.print()

        # HLFIR
        hlfir = (node.get('hlfir_op') or '').strip()
        if hlfir:
            console.print(Panel(hlfir, title="HLFIR", expand=False))
            console.print()

        # FIR
        fir = (node.get('fir_op') or '').strip()
        if fir:
            console.print(Panel(fir, title="FIR", expand=False))
            console.print()

        # LLVM IR
        llvm = (node.get('llvm_ir') or '').strip()
        if llvm:
            console.print(Panel(llvm, title="LLVM IR", expand=False))
            console.print()

        if idx < len(nodes):
            console.print("-" * 80)
            console.print()

    console.print("=" * 80)
    console.print("Trace complete")
    console.print()


def print_stage_summary(bundle):

    if not bundle or not bundle.get('nodes'):
        return

    table = Table(title="Compilation Stages Summary")

    table.add_column("Construct")
    table.add_column("Source")
    table.add_column("Parse")
    table.add_column("Semantics")
    table.add_column("FIR")

    for node in bundle.get('nodes', []):
        if isinstance(node, dict):
            table.add_row(
                (node.get('kind') or '')[:15],
                (node.get('text') or '')[:15],
                (node.get('parse_tree') or '')[:15],
                (node.get('semantics') or '')[:15],
                (node.get('fir_op') or '')[:15]
            )

    console.print(table)