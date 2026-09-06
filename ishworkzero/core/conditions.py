from __future__ import annotations
from typing import Any
_MISSING = object()

def get_path(data: Any, path: str) -> Any:
    cur=data
    for part in path.split('.'):
        if isinstance(cur, dict) and part in cur: cur=cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part)<len(cur): cur=cur[int(part)]
        else: return _MISSING
    return cur

def evaluate(actual: Any, operator: str, expected: Any) -> bool:
    if actual is _MISSING: return False
    if operator=='equals': return actual==expected
    if operator=='not_equals': return actual!=expected
    if operator=='greater_than': return actual>expected
    if operator=='less_than': return actual<expected
    if operator=='greater_or_equal': return actual>=expected
    if operator=='less_or_equal': return actual<=expected
    if operator=='contains': return expected in actual
    if operator=='not_contains': return expected not in actual
    if operator=='exists': return bool(actual) == bool(expected)
    raise ValueError(f'Unsupported operator: {operator}')
