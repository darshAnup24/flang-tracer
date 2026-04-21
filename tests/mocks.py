import json

def get_c01_mock_bundle():
    """Returns a mock TraceBundle for C01 validation in tests without running full compiler builds."""
    return {
        "construct_id": "C01",
        "nodes": [
            {
                "src_range": "11:5-11:23",
                "kind": "ARRAY_ASSIGN",
                "parse_tree": "AssignmentStmt(Variable(Designator(A)), Expr(B + C))",
                "semantics": "Symbol A[Type: Array(Int32)]",
                "hlfir_op": "hlfir.assign %sum to %A : !fir.ref<!fir.array<5xi32>>",
                "fir_op": "fir.do_loop %arg0 = %c1 to %c5 step %c1",
                "llvm_ir": "br label %loop.body"
            }
        ]
    }
