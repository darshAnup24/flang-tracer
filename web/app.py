from flask import Flask, request, jsonify, render_template
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


def normalize_nodes(nodes):
    """Convert semantic bundle nodes to API format."""
    out = []
    for n in nodes:
        if not isinstance(n, dict):
            continue

        construct = n.get('construct', {})
        metadata = n.get('metadata', {})

        out.append({
            "text": n.get('source', ''),
            "kind": construct.get('kind', 'UNKNOWN'),
            "construct_id": construct.get('id', ''),
            "parse_tree": str(n.get('parse_tree', [])),
            "semantics": str(n.get('semantics', [])),
            "hlfir_op": str(n.get('hlfir_ops', [])),
            "fir_op": str(n.get('fir_ops', [])),
            "llvm_ir": str(n.get('llvm_instrs', [])),
            "num_hlfir": metadata.get('num_hlfir_ops', 0),
            "num_fir": metadata.get('num_fir_ops', 0),
            "num_llvm": metadata.get('num_llvm_instrs', 0),
            "correlated": metadata.get('fully_correlated', False)
        })
    return out


@app.route('/')
def index():
    return render_template('index.html')


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
            return jsonify({"nodes": []}), 400

        if COMPILER_AVAILABLE:
            try:
                logger.info("Using semantic correlation engine")
                engine = SemanticCorrelationEngine()
                bundle = engine.trace_with_real_compiler(code)
                
                # Convert bundle to dict if needed
                if hasattr(bundle, 'to_dict'):
                    bundle_dict = bundle.to_dict()
                else:
                    bundle_dict = bundle if isinstance(bundle, dict) else {}
                
                nodes = bundle_dict.get('nodes', [])
                return jsonify({
                    "nodes": normalize_nodes(nodes),
                    "stats": bundle_dict.get('metadata', {}).get('correlation_stats', {})
                })

            except Exception as e:
                logger.warning(f"Real compiler failed: {e}", exc_info=True)

        construct = extract_construct_type(code)
        bundle = get_mock_bundle_for_construct(construct)
        nodes = bundle.get('nodes', [])

        if nodes:
            lines = [
                l.strip() for l in code.split('\n')
                if l.strip() and not l.strip().startswith('!')
            ]
            snippet = '\n'.join(lines[:3])
            nodes[0]['text'] = snippet

        return jsonify({"nodes": normalize_nodes(nodes)})

    except Exception as e:
        logger.error(f"Trace error: {e}", exc_info=True)
        return jsonify({"nodes": []}), 500


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