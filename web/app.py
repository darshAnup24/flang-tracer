from flask import Flask, request, jsonify, render_template
import sys
import os
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests.mocks import get_c01_mock_bundle

app = Flask(__name__, template_folder='templates')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/trace', methods=['POST'])
def trace():
    code = request.form.get('code', '')
    
    # Simulate processing time for compiler stages
    time.sleep(1.5)
    
    # In a full build environment, this would call flang-new and read the trace bundle.
    # For demonstration, we'll fetch the core mock and inject the source segment if valid.
    bundle = get_c01_mock_bundle()
    
    if code and len(code.strip()) > 0:
        lines = code.strip().split('\n')
        extract = lines[-1] if len(lines) > 0 else code
        # Update the mock simply to reflect an interactive injection:
        bundle['nodes'][0]['text'] = extract
        
        # Super simple dynamic parsing for wow factor in LLVM mapping
        bundle['nodes'][0]['hlfir_op'] = f"hlfir.assign %sum to %Uploaded_Src"
        bundle['nodes'][0]['llvm_ir'] = f"br label %loop.body\n; Translated dynamically from upload"
    
    return jsonify(bundle)

if __name__ == '__main__':
    app.run(debug=True, port=8080)
