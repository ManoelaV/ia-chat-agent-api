"""Safe math tool: evaluates arithmetic expressions using AST.

This tool accepts a string expression like "2 + 2 * (3 - 1)" and returns
the numeric result. It only allows numeric operators and safe functions
from Python's `math` module.
"""
from typing import Any
import ast
import operator as op
import math

# supported operators map
_operators = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.Pow: op.pow,
    ast.Mod: op.mod,
    ast.USub: op.neg,
    ast.UAdd: op.pos,
}

_allowed_funcs = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}


def _eval(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body)

    # Support numeric literal nodes across Python versions. Newer Python
    # versions may not expose `ast.Num` as a symbol, so build a safe tuple
    # of constant node types to check at runtime.
    number_node_types = (ast.Constant,)
    if hasattr(ast, "Num"):
        number_node_types = (ast.Num, ast.Constant)

    if isinstance(node, number_node_types):
        # ast.Num uses `n`; ast.Constant uses `value`
        if hasattr(node, "n"):
            val = node.n
        else:
            val = node.value
        if isinstance(val, (int, float)):
            return val
        raise ValueError("Only numeric constants are allowed")
    if isinstance(node, ast.BinOp):
        left = _eval(node.left)
        right = _eval(node.right)
        op_type = type(node.op)
        if op_type in _operators:
            return _operators[op_type](left, right)
    if isinstance(node, ast.UnaryOp):
        operand = _eval(node.operand)
        op_type = type(node.op)
        if op_type in _operators:
            return _operators[op_type](operand)
    if isinstance(node, ast.Call):
        # only allow simple names as functions
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in _allowed_funcs:
                args = [_eval(a) for a in node.args]
                return _allowed_funcs[func_name](*args)
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


def evaluate_expression(expr: str) -> dict:
    """Evaluate a math expression safely and return a dict with result or error.

    Returns: {"ok": True, "result": number} or {"ok": False, "error": "msg"}
    """
    try:
        parsed = ast.parse(expr, mode="eval")
        result = _eval(parsed)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    examples = ["2 + 2", "10 / 3", "sin(3.14/2)", "2**10", "abs(-5)"]
    for ex in examples:
        print(ex, evaluate_expression(ex))
