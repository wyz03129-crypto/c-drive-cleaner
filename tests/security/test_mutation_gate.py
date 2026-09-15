from __future__ import annotations

from scripts.check_mutation_gate import find_violations


def test_no_delete_calls_exist_outside_approved_gateways() -> None:
    assert find_violations() == []
