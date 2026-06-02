import html as html_module
from typing import Dict, List, Optional


def escape_html(text):
    if not text:
        return ""
    return html_module.escape(str(text))


class StageFormatter:

    @staticmethod
    def format_parse_tree(constructs: List) -> str:
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
        if not ops:
            return '<div class="stage-content"><p>[No FIR operations]</p></div>'

        html = '<div class="stage-content fir">'

        construct_groups: Dict[str, List] = {}
        for op in ops:
            if isinstance(op, dict):
                construct_id = op.get('construct_id', 'unknown')
                if construct_id not in construct_groups:
                    construct_groups[construct_id] = []
                construct_groups[construct_id].append(op)

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

            construct = node.get('construct', {})
            construct_kind = construct.get('kind', 'UNKNOWN')
            construct_id = construct.get('id', 'N/A')

            source_text = escape_html(node.get('source', '[No source]'))

            parse_tree_html = StageFormatter.format_parse_tree(node.get('parse_tree', []))
            semantics_html = StageFormatter.format_semantics(node.get('semantics', []))
            hlfir_html = StageFormatter.format_hlfir(node.get('hlfir_ops', []))
            fir_html = StageFormatter.format_fir(node.get('fir_ops', []))
            llvm_html = StageFormatter.format_llvm(node.get('llvm_instrs', []))

            construct_meta = node.get('metadata', {})
            is_correlated = construct_meta.get('fully_correlated', False)
            correlation_status = "✓ Fully correlated" if is_correlated else "⚠ Partial"

            rows_html += f'''
            <div class="trace-row" id="construct-{idx}">
                <div class="construct-header">
                    <span class="construct-kind">{escape_html(construct_kind)}</span>
                    <span class="construct-id">{escape_html(construct_id)}</span>
                    <span class="correlation-status {'correlated' if is_correlated else 'partial'}">
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

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flang Multi-Stage Semantic Tracer</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">

    <style>
        :root {{
            --bg-base:    #0d0f14;
            --bg-surface: #13161e;
            --bg-raised:  #1a1e28;
            --bg-hover:   #212536;
            --border:     #2a2f3d;
            --border-lit: #3d4560;
            --accent:     #5b8fff;
            --accent2:    #40d9b5;
            --accent3:    #f06f3f;
            --text-1:     #e8ecf4;
            --text-2:     #9ba5be;
            --text-3:     #5a6278;
            --tag-blue:   #1e3a6e;
            --tag-green:  #0f3329;
            --radius:     8px;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background: var(--bg-base);
            color: var(--text-1);
            font-family: 'Inter', sans-serif;
            font-size: 13px;
            line-height: 1.5;
            padding: 20px;
        }}

        h1 {{
            color: var(--accent);
            margin-bottom: 20px;
            font-size: 22px;
            font-weight: 600;
            letter-spacing: -0.01em;
        }}

        .header {{
            margin-bottom: 24px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 16px;
        }}

        .stats {{
            display: flex;
            gap: 28px;
            margin: 16px 0 4px;
            flex-wrap: wrap;
        }}

        .stat-item {{
            display: flex;
            flex-direction: column;
            gap: 2px;
        }}

        .stat-label {{
            color: var(--text-3);
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }}

        .stat-value {{
            color: var(--accent);
            font-size: 20px;
            font-weight: 700;
            line-height: 1;
        }}

        .trace-container {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}

        .trace-row {{
            background: var(--bg-surface);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            overflow: hidden;
            box-shadow: 0 2px 12px rgba(0,0,0,0.25);
        }}

        .construct-header {{
            background: var(--bg-raised);
            padding: 12px 16px;
            display: flex;
            gap: 12px;
            align-items: center;
            border-bottom: 1px solid var(--border);
            flex-wrap: wrap;
        }}

        .construct-kind {{
            background: var(--tag-blue);
            color: var(--accent);
            padding: 3px 10px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 11px;
            font-family: 'JetBrains Mono', monospace;
        }}

        .construct-id {{
            color: var(--text-3);
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
        }}

        .correlation-status {{
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.02em;
        }}

        .correlation-status.correlated {{
            background: var(--tag-green);
            color: var(--accent2);
        }}

        .correlation-status.partial {{
            background: #3d2a10;
            color: #e8b84b;
        }}

        .op-counts {{
            color: var(--text-3);
            font-size: 10px;
            font-family: 'JetBrains Mono', monospace;
            margin-left: auto;
        }}

        .stages-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 0;
        }}

        .stage {{
            border-right: 1px solid var(--border);
            border-bottom: 1px solid var(--border);
            padding: 14px;
            background: var(--bg-base);
            min-height: 160px;
            overflow-y: auto;
            max-height: 360px;
        }}

        .stage:last-child {{
            border-right: none;
        }}

        .stage-label {{
            color: var(--text-2);
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 700;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border);
        }}

        .stage-content {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            color: var(--text-2);
            line-height: 1.6;
        }}

        .source {{
            grid-column: 1 / -1;
        }}

        .source .stage-content {{
            background: var(--bg-surface);
            padding: 10px 12px;
            border-radius: 5px;
            border-left: 3px solid var(--accent);
            color: var(--text-1);
            font-size: 12px;
        }}

        .ast-node {{
            display: flex;
            gap: 10px;
            padding: 5px 8px;
            background: var(--bg-raised);
            margin-bottom: 3px;
            border-radius: 4px;
            border-left: 2px solid var(--accent);
        }}

        .node-kind {{
            color: var(--accent);
            font-weight: 600;
        }}

        .node-range {{
            color: var(--text-3);
            font-size: 10px;
        }}

        .symbol-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 10.5px;
        }}

        .symbol-table thead {{
            background: var(--bg-raised);
            border-bottom: 1px solid var(--accent);
        }}

        .symbol-table th {{
            padding: 6px 8px;
            text-align: left;
            color: var(--text-1);
            font-weight: 600;
        }}

        .symbol-table td {{
            padding: 5px 8px;
            border-bottom: 1px solid var(--border);
        }}

        .sym-name {{
            color: #d4a0ff;
            font-weight: 600;
        }}

        .sym-kind {{
            color: var(--accent);
            font-size: 10px;
        }}

        .sym-type {{
            color: var(--accent2);
        }}

        .sym-attrs {{
            color: var(--text-3);
            font-size: 10px;
        }}

        .ir-op {{
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            padding: 5px 8px;
            background: var(--bg-raised);
            margin-bottom: 3px;
            border-radius: 4px;
            border-left: 2px solid var(--border-lit);
            font-size: 10.5px;
        }}

        .hlfir-op {{
            border-left-color: #ffcb6b;
        }}

        .fir-op {{
            border-left-color: #f78c6c;
        }}

        .llvm-instr {{
            display: flex;
            gap: 8px;
            padding: 3px 8px;
            margin-bottom: 3px;
            border-left: 2px solid var(--border-lit);
            font-size: 10.5px;
        }}

        .op-result {{
            color: #d4a0ff;
        }}

        .op-name {{
            color: var(--accent);
            font-weight: 600;
        }}

        .hlfir-name {{
            color: #ffcb6b;
        }}

        .fir-name {{
            color: #f78c6c;
        }}

        .op-args {{
            color: var(--text-2);
        }}

        .op-loc, .debug-loc {{
            color: var(--text-3);
            font-size: 9.5px;
        }}

        .llvm-op {{
            color: #d4a0ff;
            font-weight: 600;
        }}

        .llvm-line {{
            color: var(--text-2);
            padding: 1px 5px;
            background: var(--bg-raised);
            border-radius: 3px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 10.5px;
        }}

        .fir-construct {{
            margin-bottom: 6px;
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 6px 8px;
            background: var(--bg-raised);
        }}

        .op-count {{
            color: var(--text-2);
            font-size: 9.5px;
            margin-bottom: 5px;
            padding-bottom: 4px;
            border-bottom: 1px solid var(--border);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        ::-webkit-scrollbar {{ width: 4px; height: 4px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{ background: var(--border-lit); border-radius: 2px; }}

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
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Error — FTrace</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-base:    #0d0f14;
            --bg-surface: #13161e;
            --bg-raised:  #1a1e28;
            --border:     #2a2f3d;
            --accent3:    #f06f3f;
            --text-1:     #e8ecf4;
            --text-2:     #9ba5be;
        }}
        body {{
            background: var(--bg-base);
            color: var(--text-1);
            font-family: 'Inter', sans-serif;
            padding: 40px;
        }}
        .error-container {{
            max-width: 600px;
            margin: 0 auto;
            background: var(--bg-surface);
            padding: 30px;
            border-radius: 8px;
            border-left: 4px solid var(--accent3);
            border: 1px solid var(--border);
        }}
        h2 {{
            color: var(--accent3);
            margin-bottom: 15px;
            font-weight: 600;
        }}
        p {{
            color: var(--text-2);
            word-break: break-word;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="error-container">
        <h2>Tracing Error</h2>
        <p>{escape_html(msg)}</p>
    </div>
</body>
</html>"""
