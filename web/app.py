from flask import Flask, request, jsonify, render_template, send_from_directory
import sys
import os
import re
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ftrace.engine import SemanticCorrelationEngine
from ftrace.compiler_interface import FlangNotFoundError
from ftrace.render_html import generate_html
from tests.mocks import get_mock_bundle_for_construct

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates')

MAX_CODE_SIZE = 50 * 1024
FORTRAN_KEYWORDS = {'program', 'subroutine', 'function', 'module', 'interface', 'type'}
EXAMPLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'examples'))
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'output'))

COMPILER_AVAILABLE = False
try:
    from ftrace.compiler_interface import CompilerInterface
    CompilerInterface()
    COMPILER_AVAILABLE = True
except FlangNotFoundError:
    COMPILER_AVAILABLE = False


def validate_fortran_code(code):
    if not code or not isinstance(code, str):
        return False, "Invalid input"

    code = code.strip()
    if not code:
        return False, "Empty code"

    if len(code) > MAX_CODE_SIZE:
        return False, "Code too large"

    has_keyword = any(
        line.strip().lower().startswith(tuple(FORTRAN_KEYWORDS))
        for line in code.split('\n')
        if line.strip() and not line.strip().startswith('!')
    )

    if not has_keyword:
        return False, "Missing Fortran keyword"

    if 'end' not in code.lower():
        return False, "Missing end statement"

    return True, None


def list_example_files():
    try:
        return sorted([
            name for name in os.listdir(EXAMPLES_DIR)
            if name.endswith('.f90')
        ])
    except OSError:
        return []


def read_example_file(name):
    if not name or '/' in name or '\\' in name:
        return None
    path = os.path.join(EXAMPLES_DIR, name)
    try:
        if os.path.commonpath([EXAMPLES_DIR, path]) != EXAMPLES_DIR:
            return None
    except ValueError:
        return None

    try:
        with open(path, 'r') as f:
            return f.read()
    except IOError:
        return None


def extract_construct_type(code):
    code = code.lower()

    if 'do concurrent' in code:
        return 'C05'
    elif 'forall' in code:
        return 'C04'
    elif re.search(r'type\s+::\s+\w+', code):
        return 'C06'
    elif 'where' in code:
        return 'C03'
    else:
        return 'C01'


def _fmt(value) -> str:
    """Render a stage field as a human-readable string."""
    if not value:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(item.get('raw') or item.get('line') or str(item))
            else:
                parts.append(str(item))
        return '\n'.join(parts)
    return str(value)


def normalize_nodes(nodes):
    """
    Convert bundle nodes to the API response format.

    Handles two node shapes:
    * Real bundle  – nested ``construct`` / ``metadata`` sub-dicts
    * Mock data    – flat keys (``kind``, ``text``, ``parse_tree``, …)
    """
    out = []
    for n in nodes:
        if not isinstance(n, dict):
            continue

        # -- identity fields --------------------------------------------------
        construct = n.get('construct') or {}
        metadata  = n.get('metadata')  or {}

        kind         = construct.get('kind') or n.get('kind', 'UNKNOWN')
        construct_id = construct.get('id')   or n.get('src_range', '')
        src_range    = construct.get('source_range') or n.get('src_range', '')
        text         = n.get('source') or n.get('text', '')

        # -- stage content fields --------------------------------------------
        # Real bundle uses plural keys (hlfir_ops, fir_ops, llvm_instrs)
        # Mock data uses singular keys (hlfir_op, fir_op, llvm_ir)
        parse_tree_raw = n.get('parse_tree', [])
        semantics_raw  = n.get('semantics',  [])
        hlfir_raw      = n.get('hlfir_ops')  or n.get('hlfir_op', '')
        fir_raw        = n.get('fir_ops')    or n.get('fir_op',   '')
        llvm_raw       = n.get('llvm_instrs') or n.get('llvm_ir',  '')

        # -- counts -----------------------------------------------------------
        num_hlfir = metadata.get('num_hlfir_ops') or (len(hlfir_raw) if isinstance(hlfir_raw, list) else 0)
        num_fir   = metadata.get('num_fir_ops')   or (len(fir_raw)   if isinstance(fir_raw,   list) else 0)
        num_llvm  = metadata.get('num_llvm_instrs') or (len(llvm_raw) if isinstance(llvm_raw,  list) else 0)

        out.append({
            "text":         text,
            "kind":         kind,
            "construct_id": construct_id,
            "src_range":    src_range,
            "parse_tree":   _fmt(parse_tree_raw),
            "semantics":    _fmt(semantics_raw),
            "hlfir_op":     _fmt(hlfir_raw),
            "fir_op":       _fmt(fir_raw),
            "llvm_ir":      _fmt(llvm_raw),
            "num_hlfir":    num_hlfir,
            "num_fir":      num_fir,
            "num_llvm":     num_llvm,
            "correlated":   metadata.get('fully_correlated', bool(fir_raw)),
        })
    return out


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/output/<path:filename>')
def serve_output(filename):
    """Serve pre-generated HTML/JSON/TXT files from the output directory."""
    return send_from_directory(OUTPUT_DIR, filename)


@app.route('/api/output-files', methods=['GET'])
def list_output_files():
    """List all HTML files in the output directory."""
    try:
        files = sorted([
            f for f in os.listdir(OUTPUT_DIR)
            if f.endswith('.html')
        ])
        return jsonify({'files': files})
    except OSError:
        return jsonify({'files': []})


@app.route('/api/trace', methods=['POST'])
def trace():
    try:
        # Handle both form and JSON payloads
        if request.is_json:
            code = request.json.get('code', '')
        else:
            code = request.form.get('code', '')

        valid, msg = validate_fortran_code(code)
        if not valid:
            return jsonify({"error": msg, "nodes": []}), 400

        if COMPILER_AVAILABLE:
            try:
                logger.info("Using real flang compiler")
                engine = SemanticCorrelationEngine()
                bundle = engine.trace_with_real_compiler(code)

                if hasattr(bundle, 'to_dict'):
                    bundle_dict = bundle.to_dict()
                else:
                    bundle_dict = bundle if isinstance(bundle, dict) else {}

                nodes = bundle_dict.get('nodes', [])
                stats = bundle_dict.get('metadata', {}).get('correlation_stats', {})
                return jsonify({
                    "nodes": normalize_nodes(nodes),
                    "stats": stats,
                    "mode": "real",
                })

            except Exception as e:
                logger.warning(f"Real compiler failed: {e}", exc_info=True)
                # Fall through to mock with a warning embedded in the response

        # ---- Mock mode (flang unavailable or compilation failed) ----
        construct = extract_construct_type(code)
        bundle = get_mock_bundle_for_construct(construct)
        nodes = bundle.get('nodes', [])

        if nodes:
            code_lines = [
                l.strip() for l in code.split('\n')
                if l.strip() and not l.strip().startswith('!')
            ]
            snippet = '\n'.join(code_lines[:3])
            nodes[0]['text'] = snippet

        return jsonify({
            "nodes": normalize_nodes(nodes),
            "mode": "mock",
            "mock_warning": (
                "flang compiler not found. Showing illustrative mock data. "
                "Install flang with: sudo dnf install -y flang"
            ),
        })

    except Exception as e:
        logger.error(f"Trace error: {e}", exc_info=True)
        return jsonify({"nodes": []}), 500


def trace_file(filepath):
    """Trace a single Fortran file and return normalized nodes."""
    code = read_example_file(filepath)
    if not code:
        return [], {}
    if COMPILER_AVAILABLE:
        try:
            engine = SemanticCorrelationEngine()
            bundle = engine.trace_with_real_compiler(code)
            bundle_dict = bundle.to_dict() if hasattr(bundle, 'to_dict') else (bundle if isinstance(bundle, dict) else {})
            return normalize_nodes(bundle_dict.get('nodes', [])), bundle_dict.get('metadata', {}).get('correlation_stats', {})
        except Exception:
            pass
    construct = extract_construct_type(code)
    bundle = get_mock_bundle_for_construct(construct)
    nodes = bundle.get('nodes', [])
    if nodes:
        code_lines = [l.strip() for l in code.split('\n') if l.strip() and not l.strip().startswith('!')]
        nodes[0]['text'] = '\n'.join(code_lines[:3])
    return normalize_nodes(nodes), {}


@app.route('/api/trace-all', methods=['GET'])
def trace_all():
    """Trace all example files and return results as one bundle."""
    files = list_example_files()
    all_results = []
    total_stats = {
        'total_constructs': 0,
        'total_files': len(files),
        'stages': ['parse_tree', 'semantics', 'hlfir', 'fir', 'llvm'],
    }
    for name in files:
        label = name.replace('.f90', '')
        nodes, stats = trace_file(name)
        all_results.append({
            'label': label,
            'file': name,
            'nodes': nodes,
            'stats': stats,
        })
        total_stats['total_constructs'] += len(nodes)
    return jsonify({
        'results': all_results,
        'stats': total_stats,
        'mode': 'real' if COMPILER_AVAILABLE else 'mock',
    })


@app.route('/api/examples', methods=['GET'])
def examples():
    return jsonify({
        'examples': list_example_files()
    })


@app.route('/api/examples/load', methods=['GET'])
def load_example():
    name = request.args.get('name', '')
    content = read_example_file(name)
    if content is None:
        return jsonify({'error': 'Invalid example file name'}), 400
    return jsonify({
        'name': name,
        'content': content
    })


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'compiler': 'real' if COMPILER_AVAILABLE else 'mock',
        'engine': 'semantic'
    })


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    logger.error(str(e))
    return jsonify({'error': 'Server error'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=8081, use_reloader=False)