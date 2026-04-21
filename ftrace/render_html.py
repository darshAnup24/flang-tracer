import json

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Flang Pipeline Trace</title>
    <style>
        body {{ font-family: monospace; background: #1e1e1e; color: #d4d4d4; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr; gap: 10px; }}
        .pane {{ border: 1px solid #333; padding: 10px; overflow-x: auto; }}
        h3 {{ color: #569cd6; font-size: 14px; text-align: center; }}
        .node {{ padding: 5px; margin-bottom: 10px; border-left: 2px solid #c586c0; background: #252526; cursor: pointer; }}
        .node:hover {{ background: #333333; }}
        .active {{ background: #2a2d2e; border-left: 2px solid #4af626; }}
    </style>
</head>
<body>
    <h2 style="text-align:center; color:#9cdcfe;">FTrace: Multi-Stage Compilation Viewer</h2>
    <div class="grid">
        <div class="pane" id="p-src"><h3>Source Code</h3>{src_html}</div>
        <div class="pane" id="p-pt"><h3>Parse Tree</h3>{pt_html}</div>
        <div class="pane" id="p-sema"><h3>Semantics</h3>{sema_html}</div>
        <div class="pane" id="p-fir"><h3>HLFIR / FIR</h3>{fir_html}</div>
        <div class="pane" id="p-llvm"><h3>LLVM IR</h3>{llvm_html}</div>
    </div>
    <script>
        function highlight(id) {{
            document.querySelectorAll('.node').forEach(n => n.classList.remove('active'));
            document.querySelectorAll('.id-' + id).forEach(n => n.classList.add('active'));
        }}
    </script>
</body>
</html>
"""

def generate_html(trace_bundle):
    """Generates the 5-pane interactive HTML view for a given TraceBundle."""
    src, pt, sema, fir, llvm = "", "", "", "", ""
    
    for i, node in enumerate(trace_bundle.get('nodes', [])):
        nid = f"n{i}"
        div_str = f'<div class="node id-{nid}" onclick="highlight(\'{nid}\')">'
        
        src += f"{div_str}<strong>{node.get('src_range')}</strong><br/>{node.get('text')}</div>"
        pt += f"{div_str}{node.get('parse_tree')}</div>"
        sema += f"{div_str}{node.get('semantics')}</div>"
        
        fir_combined = f"<b>HLFIR:</b><br>{node.get('hlfir_op')}<br/><br/><b>FIR:</b><br>{node.get('fir_op')}"
        fir += f"{div_str}{fir_combined}</div>"
        
        llvm += f"{div_str}{node.get('llvm_ir')}</div>"

    return HTML_TEMPLATE.format(src_html=src, pt_html=pt, sema_html=sema, fir_html=fir, llvm_html=llvm)
