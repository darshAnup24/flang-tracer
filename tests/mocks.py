import json

def get_mock_bundle_for_construct(construct_id):
    """Returns mock trace bundles for different Fortran constructs."""
    
    bundles = {
        'C01': {
            'construct_id': 'C01',
            'name': 'Array Assignment',
            'nodes': [
                {
                    'src_range': '4:3-4:12',
                    'kind': 'ARRAY_ASSIGN',
                    'text': 'A = 10',
                    'parse_tree': 'AssignmentStmt(\n  Variable(Name("A")),\n  Expr(LiteralExpr(10))\n)',
                    'semantics': 'Symbol A [Type: Array(Int32, 5)] <- Int32 (implicit conversion)',
                    'hlfir_op': 'hlfir.assign %cst_10 to %A : !fir.ref<!fir.array<5xi32>>',
                    'fir_op': 'fir.do_loop %i0 = %c1 to %c5 step %c1 {\n  fir.array_update %A, %i0, %cst_10\n}',
                    'llvm_ir': 'br label %loop.body\nloop.body:\n  %idx = add i64 %i, 1\n  br i1 %cond, label %loop.body, label %loop.end'
                }
            ]
        },
        'C03': {
            'construct_id': 'C03',
            'name': 'WHERE Block',
            'nodes': [
                {
                    'src_range': '5:3-7:12',
                    'kind': 'WHERE_BLOCK',
                    'text': 'where (A > 0)\n  B = A / 2\nendwhere',
                    'parse_tree': 'WhereStmt(\n  Expr(BinaryOp(Var("A"), ">", Literal(0))),\n  AssignmentStmt(Var("B"), BinaryOp(Var("A"), "/", Literal(2)))\n)',
                    'semantics': 'WHERE mask: Array(Bool, 5) | Masked assignment: B[Type: Array(Real)]',
                    'hlfir_op': 'hlfir.where %mask {\n  hlfir.assign hlfir.binop div %A to %B\n}',
                    'fir_op': 'fir.where %mask : !fir.array<5xi1> {\n  fir.array_update %B, %i, fir.binop div %A_val\n}',
                    'llvm_ir': '%mask_ptr = getelementptr i1, i1* %mask_data, i64 %i\n%mask_val = load i1, i1* %mask_ptr\nbr i1 %mask_val, label %update, label %skip'
                }
            ]
        },
        'C04': {
            'construct_id': 'C04',
            'name': 'FORALL Construct',
            'nodes': [
                {
                    'src_range': '6:3-8:14',
                    'kind': 'FORALL_LOOP',
                    'text': 'forall (i = 1:n)\n  A(i) = B(i) + C(i)\nend forall',
                    'parse_tree': 'ForallStmt(\n  Index(Name("i"), Expr(1), Expr(n)),\n  AssignmentStmt(ArrayRef(Var("A"), Index(Var("i"))), BinaryOp(...))\n)',
                    'semantics': 'Index i [Type: Int32] range 1:n | Array subscript evaluation',
                    'hlfir_op': 'hlfir.forall {\n  %sum = hlfir.binop add %B[%i] to %C[%i]\n  hlfir.assign %sum to %A[%i]\n}',
                    'fir_op': 'fir.do_loop %i = %c1 to %n step %c1 {\n  %b_val = fir.array_fetch %B, %i\n  %c_val = fir.array_fetch %C, %i\n  %sum = fir.binop add %b_val, %c_val\n  fir.array_update %A, %i, %sum\n}',
                    'llvm_ir': 'for.body:\n  %idx = phi i64 [ 1, %entry ], [ %idx.next, %for.body ]\n  %b_elem = load i32, i32* %B_ptr\n  %c_elem = load i32, i32* %C_ptr\n  %sum_val = add i32 %b_elem, %c_elem\n  store i32 %sum_val, i32* %A_ptr\n  %idx.next = add i64 %idx, 1'
                }
            ]
        },
        'C05': {
            'construct_id': 'C05',
            'name': 'DO CONCURRENT',
            'nodes': [
                {
                    'src_range': '7:3-9:8',
                    'kind': 'DO_CONCURRENT',
                    'text': 'do concurrent (i = 1:n)\n  A(i) = B(i) * 2\nend do',
                    'parse_tree': 'DoConcurrentStmt(\n  Index(Name("i"), Expr(1), Expr(n)),\n  AssignmentStmt(ArrayRef(Var("A"), Index(Var("i"))), ...)\n)',
                    'semantics': 'Concurrent index i [Type: Int32] | No loop-carried dependencies detected',
                    'hlfir_op': 'hlfir.do_concurrent {\n  %prod = hlfir.binop mul %B[%i] to %c2\n  hlfir.assign %prod to %A[%i]\n}',
                    'fir_op': 'fir.do_loop %i = %c1 to %n step %c1 {\n  %b_val = fir.array_fetch %B, %i\n  %prod = fir.binop mul %b_val, %c2\n  fir.array_update %A, %i, %prod\n} {unordered}',
                    'llvm_ir': '; Parallel loop (can be vectorized)\nfor.body:\n  %b_elem = load i32, i32* %B_ptr, !llvm.mem.parallel_loop_access\n  %prod = mul i32 %b_elem, 2\n  store i32 %prod, i32* %A_ptr, !llvm.mem.parallel_loop_access'
                }
            ]
        },
        'C06': {
            'construct_id': 'C06',
            'name': 'Derived Type',
            'nodes': [
                {
                    'src_range': '3:1-5:14',
                    'kind': 'DERIVED_TYPE',
                    'text': 'type :: Point\n  real :: x, y\nend type',
                    'parse_tree': 'DerivedTypeStmt(\n  Name("Point"),\n  ComponentDef(Name("x"), DeclType(Real)),\n  ComponentDef(Name("y"), DeclType(Real))\n)',
                    'semantics': 'Type Point [size: 16 bytes] { x: Real*8@0, y: Real*8@8 }',
                    'hlfir_op': '!fir.type<Point: f64, f64> (HLFIR type wrapping)',
                    'fir_op': '!fir.type<Point{x:f64, y:f64}> = !fir.ptr<!fir.array<1x!fir.type<Point>>',
                    'llvm_ir': '%Point = type { double, double }  ; 16 bytes\n%point_val = alloca %Point\n%x_ptr = getelementptr %Point, %Point* %point_val, i32 0, i32 0'
                }
            ]
        }
    }
    
    # Default to C01 if construct not found
    return bundles.get(construct_id, bundles['C01'])

def get_c01_mock_bundle():
    """Legacy function for backward compatibility."""
    return get_mock_bundle_for_construct('C01')
