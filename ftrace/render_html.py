"""
Stage-aware semantic HTML renderer for Flang tracer results.

This module provides semantic interpretation of each stage:
- Parse Tree: AST node visualization with proper syntax tree structure
- Semantics: Symbol table with type and attribute information
- HLFIR: High-level Fortran IR with semantic structure preserved
- FIR: Lowered SSA IR with one-to-many operation visualization
- LLVM IR: Machine code with relevance filtering
"""

import html as html_module
from typing import Dict, List, Optional


def escape_html(text):
    """Safely escape HTML special characters."""
    if not text:
        return ""
    return html_module.escape(str(text))


class StageFormatter:
    """Formats output for each compilation stage."""

    @staticmethod
    def format_parse_tree(constructs: List) -> str:
        """Format parse tree constructs as semantic AST nodes."""
        if not constructs:
            return '<div class="stage-content"><p>[No parse tree constructs found]</p></div>'

        html = '<div class="stage-content parse-tree">'

        for construct in constructs:
            if isinstance(construct, dict):
                kind = construct.get('construct_kind', 'Unknown')
                line_range = construct.get('line_range', (0, 0))
                html += f'''
                <div class="ast-node">
                    <span class="node-kind">{escape_html(kind)}</span>
                    <span class="node-range">:{line_range[0]}-{line_range[1]}</span>
                </div>
                '''

        html += '</div>'
        return html

    @staticmethod
    def format_semantics(symbols: List) -> str:
        """Format semantic symbols as a type-annotated table."""
        if not symbols:
            return '<div class="stage-content"><p>[No symbols found]</p></div>'

        html = '''
        <div class="stage-content semantics">
            <table class="symbol-table">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Kind</th>
                        <th>Type</th>
                        <th>Attributes</th>
                    </tr>
                </thead>
                <tbody>
        '''

        for sym in symbols:
            if isinstance(sym, dict):
                name = escape_html(sym.get('symbol_name', '?'))
                kind = escape_html(sym.get('symbol_kind', ''))
                type_spec = escape_html(sym.get('type', ''))
                attrs = sym.get('attributes', {})
                attrs_str = ', '.join(f"{k}={v}" for k, v in attrs.items())

                html += f'''
                    <tr>
                        <td class="sym-name">{name}</td>
                        <td class="sym-kind">{kind}</td>
                        <td class="sym-type">{type_spec}</td>
                        <td class="sym-attrs">{escape_html(attrs_str)}</td>
                    </tr>
                '''

        html += '''
                </tbody>
            </table>
        </div>
        '''

        return html

    @staticmethod
    def format_hlfir(ops: List) -> str:
        """Format HLFIR operations with semantic structure."""
        if not ops:
            return '<div class="stage-content"><p>[No HLFIR operations]</p></div>'

        html = '<div class="stage-content hlfir">'

        for op in ops:
            if isinstance(op, dict):
                op_name = escape_html(op.get('op_name', '?'))
                results = op.get('results', [])
                operands = op.get('operands', [])

                html += f'<div class="ir-op hlfir-op">'
                html += f'<span class="op-result">{", ".join(escape_html(str(r)) for r in results)}</span>'
                html += f' <span class="op-name">=</span> '
                html += f'<span class="op-name hlfir-name">{op_name}</span>'
                html += f'<span class="op-args">({", ".join(escape_html(str(a)) for a in operands)})</span>'

                if op.get('source_range'):
                    html += f'<span class="op-loc"> @ {escape_html(op.get("source_range"))}</span>'

                html += '</div>'

        html += '</div>'
        return html

    @staticmethod
    def format_fir(ops: List) -> str:
        """Format FIR operations with one-to-many visualization."""
        if not ops:
            return '<div class="stage-content"><p>[No FIR operations]</p></div>'

        html = '<div class="stage-content fir">'

        # Group by construct for one-to-many visualization
        construct_groups: Dict[str, List] = {}
        for op in ops:
            if isinstance(op, dict):
                construct_id = op.get('construct_id', 'unknown')
                if construct_id not in construct_groups:
                    construct_groups[construct_id] = []
                construct_groups[construct_id].append(op)

        # Render grouped operations
        for construct_id, ops_in_group in construct_groups.items():
            html += f'<div class="fir-construct" data-construct="{escape_html(construct_id)}">'

            if len(ops_in_group) > 1:
                html += f'<div class="op-count">{len(ops_in_group)} FIR operations</div>'

            for op in ops_in_group:
                op_name = escape_html(op.get('op_name', '?'))
                results = op.get('results', [])
                operands = op.get('operands', [])

                html += f'<div class="ir-op fir-op">'
                html += f'<span class="op-result">{", ".join(escape_html(str(r)) for r in results)}</span>'
                html += f' <span class="op-name">=</span> '
                html += f'<span class="op-name fir-name">{op_name}</span>'
                html += f'<span class="op-args">({", ".join(escape_html(str(a)) for a in operands)})</span>'

                if op.get('debug_loc'):
                    html += f' <span class="debug-loc">[{escape_html(op.get("debug_loc"))}]</span>'

                html += '</div>'

            html += '</div>'

        html += '</div>'
        return html

    @staticmethod
    def format_llvm(instrs: List) -> str:
        """Format LLVM instructions with debug metadata."""
        if not instrs:
            return '<div class="stage-content"><p>[No LLVM instructions]</p></div>'

        html = '<div class="stage-content llvm">'

        for instr in instrs:
            if isinstance(instr, dict):
                op = escape_html(instr.get('op', '?'))
                line = escape_html(instr.get('line', ''))
                debug_loc = instr.get('debug_loc', '')

                html += f'<div class="llvm-instr">'
                html += f'<span class="llvm-op">{op}</span> '
                html += f'<code class="llvm-line">{line}</code>'

                if debug_loc:
                    html += f' <span class="debug-loc">{escape_html(debug_loc)}</span>'

                html += '</div>'

        html += '</div>'
        return html


def generate_html(trace_bundle):
    """Generate semantic HTML output from trace bundle."""
    if not trace_bundle or not isinstance(trace_bundle, dict):
        return generate_error_page("Invalid trace bundle format")

    nodes = trace_bundle.get('nodes', [])
    if not nodes:
        return generate_error_page("No trace nodes found")

    try:
        metadata = trace_bundle.get('metadata', {})
        stats = metadata.get('correlation_stats', {})

        rows_html = ""

        for idx, node in enumerate(nodes):
            if not isinstance(node, dict):
                continue

            # Extract construct and stage data
            construct = node.get('construct', {})
            construct_kind = construct.get('kind', 'UNKNOWN')
            construct_id = construct.get('id', 'N/A')

            source_text = escape_html(node.get('source', '[No source]'))

            # Stage-specific formatting
            parse_tree_html = StageFormatter.format_parse_tree(node.get('parse_tree', []))
            semantics_html = StageFormatter.format_semantics(node.get('semantics', []))
            hlfir_html = StageFormatter.format_hlfir(node.get('hlfir_ops', []))
            fir_html = StageFormatter.format_fir(node.get('fir_ops', []))
            llvm_html = StageFormatter.format_llvm(node.get('llvm_instrs', []))

            construct_meta = node.get('metadata', {})
            correlation_status = "✓ Fully correlated" if construct_meta.get('fully_correlated') else "⚠ Partial"

            rows_html += f'''
            <div class="trace-row" id="construct-{idx}">
                <div class="construct-header">
                    <span class="construct-kind">{escape_html(construct_kind)}</span>
                    <span class="construct-id">{escape_html(construct_id)}</span>
                    <span class="correlation-status {construct_meta.get('fully_correlated') and "correlated" or "partial"}">
                        {correlation_status}
                    </span>
                    <span class="op-counts">
                        HLFIR:{construct_meta.get('num_hlfir_ops', 0)} 
                        FIR:{construct_meta.get('num_fir_ops', 0)} 
                        LLVM:{construct_meta.get('num_llvm_instrs', 0)}
                    </span>
                </div>

                <div class="stages-grid">
                    <div class="stage source">
                        <div class="stage-label">Source Code</div>
                        <pre class="stage-content">{source_text}</pre>
                    </div>

                    <div class="stage parse-tree">
                        <div class="stage-label">Parse Tree (AST)</div>
                        {parse_tree_html}
                    </div>

                    <div class="stage semantics">
                        <div class="stage-label">Semantics (Symbols & Types)</div>
                        {semantics_html}
                    </div>

                    <div class="stage hlfir">
                        <div class="stage-label">HLFIR (High-Level IR)</div>
                        {hlfir_html}
                    </div>

                    <div class="stage fir">
                        <div class="stage-label">FIR (Lowered IR)</div>
                        {fir_html}
                    </div>

                    <div class="stage llvm">
                        <div class="stage-label">LLVM IR (Machine IR)</div>
                        {llvm_html}
                    </div>
                </div>
            </div>
            '''

        # Build overall page
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flang Multi-Stage Semantic Tracer</title>

    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background: #1e1e1e;
            color: #e0e0e0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 13px;
            line-height: 1.5;
            padding: 20px;
        }}

        h1 {{
            color: #4fc3f7;
            margin-bottom: 20px;
            font-size: 24px;
        }}

        .header {{
            margin-bottom: 30px;
            border-bottom: 2px solid #444;
            padding-bottom: 15px;
        }}

        .stats {{
            display: flex;
            gap: 30px;
            margin: 15px 0;
            flex-wrap: wrap;
        }}

        .stat-item {{
            display: flex;
            flex-direction: column;
        }}

        .stat-label {{
            color: #888;
            font-size: 11px;
            text-transform: uppercase;
        }}

        .stat-value {{
            color: #4fc3f7;
            font-size: 18px;
            font-weight: bold;
        }}

        .trace-container {{
            display: flex;
            flex-direction: column;
            gap: 30px;
        }}

        .trace-row {{
            background: #252526;
            border: 1px solid #3e3e42;
            border-radius: 6px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
        }}

        .construct-header {{
            background: #2d2d30;
            padding: 15px;
            display: flex;
            gap: 15px;
            align-items: center;
            border-bottom: 1px solid #3e3e42;
            flex-wrap: wrap;
        }}

        .construct-kind {{
            background: #0e639c;
            color: white;
            padding: 3px 8px;
            border-radius: 3px;
            font-weight: bold;
            font-size: 12px;
        }}

        .construct-id {{
            color: #ce9178;
            font-family: monospace;
            font-size: 11px;
        }}

        .correlation-status {{
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: bold;
        }}

        .correlation-status.correlated {{
            background: #2d7d2d;
            color: #6ba583;
        }}

        .correlation-status.partial {{
            background: #7d5d2d;
            color: #b5a683;
        }}

        .op-counts {{
            color: #888;
            font-size: 11px;
            margin-left: auto;
        }}

        .stages-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 0;
        }}

        .stage {{
            border-right: 1px solid #3e3e42;
            border-bottom: 1px solid #3e3e42;
            padding: 15px;
            background: #1e1e1e;
            min-height: 200px;
            overflow-y: auto;
            max-height: 400px;
        }}

        .stage:last-child {{
            border-right: none;
        }}

        .stage-label {{
            color: #9cdcfe;
            font-size: 11px;
            text-transform: uppercase;
            font-weight: bold;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid #3e3e42;
        }}

        .stage-content {{
            font-family: 'Consolas', 'Monaco', monospace;
            font-size: 12px;
            color: #d4d4d4;
        }}

        .source {{
            grid-column: 1 / -1;
        }}

        .source .stage-content {{
            background: #1e1e1e;
            padding: 10px;
            border-radius: 3px;
            border-left: 3px solid #0e639c;
        }}

        .ast-node {{
            display: flex;
            gap: 10px;
            padding: 6px;
            background: #2d2d30;
            margin-bottom: 4px;
            border-radius: 3px;
            border-left: 2px solid #4fc3f7;
        }}

        .node-kind {{
            color: #4fc3f7;
            font-weight: bold;
        }}

        .node-range {{
            color: #888;
            font-size: 11px;
        }}

        .symbol-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 11px;
        }}

        .symbol-table thead {{
            background: #2d2d30;
            border-bottom: 2px solid #0e639c;
        }}

        .symbol-table th {{
            padding: 8px;
            text-align: left;
            color: #9cdcfe;
            font-weight: bold;
        }}

        .symbol-table td {{
            padding: 6px 8px;
            border-bottom: 1px solid #3e3e42;
        }}

        .sym-name {{
            color: #ce9178;
            font-weight: bold;
        }}

        .sym-kind {{
            color: #4fc3f7;
            font-size: 10px;
        }}

        .sym-type {{
            color: #b5cea8;
        }}

        .sym-attrs {{
            color: #888;
            font-size: 10px;
        }}

        .ir-op {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            padding: 6px;
            background: #2d2d30;
            margin-bottom: 4px;
            border-radius: 2px;
            border-left: 2px solid #646695;
        }}

        .hlfir-op {{
            border-left-color: #b8860b;
        }}

        .fir-op {{
            border-left-color: #d16969;
        }}

        .llvm-instr {{
            display: flex;
            gap: 10px;
            padding: 4px;
            margin-bottom: 4px;
            border-left: 2px solid #999;
        }}

        .op-result {{
            color: #ce9178;
        }}

        .op-name {{
            color: #4fc3f7;
            font-weight: bold;
        }}

        .hlfir-name {{
            color: #b8860b;
        }}

        .fir-name {{
            color: #d16969;
        }}

        .op-args {{
            color: #d4d4d4;
        }}

        .op-loc, .debug-loc {{
            color: #888;
            font-size: 10px;
        }}

        .llvm-op {{
            color: #ce9178;
            font-weight: bold;
        }}

        .llvm-line {{
            color: #d4d4d4;
            padding: 2px 6px;
            background: #2d2d30;
            border-radius: 2px;
        }}

        .fir-construct {{
            margin-bottom: 8px;
            border: 1px solid #3e3e42;
            border-radius: 3px;
            padding: 6px;
            background: #2d2d30;
        }}

        .op-count {{
            color: #9cdcfe;
            font-size: 10px;
            margin-bottom: 6px;
            padding-bottom: 4px;
            border-bottom: 1px solid #3e3e42;
        }}

        @media (max-width: 1400px) {{
            .stages-grid {{
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            }}
        }}

        @media (max-width: 768px) {{
            .stages-grid {{
                grid-template-columns: 1fr;
            }}

            .construct-header {{
                flex-direction: column;
                align-items: flex-start;
            }}

            .op-counts {{
                margin-left: 0;
            }}
        }}
    </style>

</head>

<body>

    <div class="header">
        <h1>Flang Multi-Stage Semantic Tracer</h1>
        <div class="stats">
            <div class="stat-item">
                <div class="stat-label">Total Constructs</div>
                <div class="stat-value">{metadata.get('num_constructs', 0)}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Fully Correlated</div>
                <div class="stat-value">{stats.get('fully_correlated', 0)}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Correlation Rate</div>
                <div class="stat-value">{stats.get('correlation_rate', 0):.1f}%</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Avg FIR Ops/Construct</div>
                <div class="stat-value">{stats.get('avg_fir_ops_per_construct', 0):.1f}</div>
            </div>
        </div>
    </div>

    <div class="trace-container">
        {rows_html}
    </div>

</body>

</html>
'''

    except Exception as e:
        return generate_error_page(str(e))


def generate_error_page(msg: str) -> str:
    """Generate error page."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Error</title>
    <style>
        body {{
            background: #1e1e1e;
            color: #e0e0e0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            padding: 40px;
        }}
        .error-container {{
            max-width: 600px;
            margin: 0 auto;
            background: #252526;
            padding: 30px;
            border-radius: 6px;
            border-left: 4px solid #d16969;
        }}
        h2 {{
            color: #d16969;
            margin-bottom: 15px;
        }}
        p {{
            color: #d4d4d4;
            word-break: break-word;
        }}
    </style>
</head>
<body>
    <div class="error-container">
        <h2>Tracing Error</h2>
        <p>{escape_html(msg)}</p>
    </div>
</body>
</html>
"""