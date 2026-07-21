"""Compiled Kleene predicates (Item 7 / D2/D3) — one function per constraint definition.

Compile-once, class-per-assertion (INV-1): every constraint module instantiated from the same
source assertion imports its function from here rather than duplicating the compiled predicate.
"""

import math
from typing import NamedTuple


class _PredicateResult(NamedTuple):
    actual_value: object  # True/False/None (None = indeterminate)
    status: str           # satisfied | violated | indeterminate
    margin: object         # signed float or None (simple-inequality roots only)


def _fin(x):
    return isinstance(x, (int, float)) and math.isfinite(x)


def _cmp(op, a, b):
    """Leaf comparison: unknown (None) if either operand is non-finite."""
    if not _fin(a) or not _fin(b):
        return None
    if op == "<=": return a <= b
    if op == ">=": return a >= b
    if op == "<":  return a < b
    if op == ">":  return a > b
    raise ValueError(f"not a comparison: {op}")


def _and(*vals):
    if any(v is False for v in vals): return False
    if any(v is None for v in vals): return None
    return True


def _or(*vals):
    if any(v is True for v in vals): return True
    if any(v is None for v in vals): return None
    return False


def _not(v):
    return None if v is None else (not v)


def _norm0(x):
    """Normalize an exact-boundary signed zero (-0.0) to 0.0 (`[HARD]`)."""
    return 0.0 if x == 0.0 else x

# f1_arithmetic::Fixture::f1_division_check
def constraint_pred_f1_arithmetic__fixture__f1_division_check(a, b):
    value = _cmp('>', (a / b), 0.0)
    if value is None:
        status = "indeterminate"
    elif value == True:
        status = "satisfied"
    else:
        status = "violated"
    return _PredicateResult(actual_value=value, status=status, margin=(_norm0(((a / b) - 0.0)) if (_fin((a / b)) and _fin(0.0)) else None))

# f1_arithmetic::Fixture::f2_power_check
def constraint_pred_f1_arithmetic__fixture__f2_power_check(a, b):
    value = _cmp('>', (a ** b), 0.0)
    if value is None:
        status = "indeterminate"
    elif value == True:
        status = "satisfied"
    else:
        status = "violated"
    return _PredicateResult(actual_value=value, status=status, margin=(_norm0(((a ** b) - 0.0)) if (_fin((a ** b)) and _fin(0.0)) else None))

# f1_arithmetic::Fixture::f3_nested_check
def constraint_pred_f1_arithmetic__fixture__f3_nested_check(a, b):
    value = _and(_cmp('>', (a / b), 0.0), _cmp('>', a, -1.0))
    if value is None:
        status = "indeterminate"
    elif value == True:
        status = "satisfied"
    else:
        status = "violated"
    return _PredicateResult(actual_value=value, status=status, margin=None)
