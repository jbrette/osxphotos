"""Perform diffs of dictionaries; this is optimized for osxphotos and is not a general purpose diff tool"""

from __future__ import annotations

import sys
from typing import Any

EPSILON = sys.float_info.epsilon


def _compare(a: Any, b: Any, tolerance: float | None) -> bool:
    """Compare two values, return True if equal, False if not"""
    if tolerance is None:
        return bool(a == b)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tolerance
    else:
        return bool(a == b)


def dictdiff(
    d1: dict[Any, Any],
    d2: dict[Any, Any],
    tolerance: float = EPSILON,
) -> list[list[Any]]:
    """Perform recursive diff of two dictionaries

    Args:
        d1: first dictionary
        d2: second dictionary
        tolerance: tolerance for comparing floats

    Returns:
        list of differences in the form of a list of tuples of the form:
        [path, change_type, (old_value, new_value)]
        where:
            path: path to the key in the dictionary
            change_type: one of "added", "removed", "changed"
            old_value: old value of the key
            new_value: new value of the key
    """
    return _dictdiff(d1, d2, tolerance)


def _dictdiff(
    d1: dict[Any, Any],
    d2: dict[Any, Any],
    tolerance: float = EPSILON,
    path: str = "",
) -> list[list[Any]]:
    """Perform recursive diff of two dictionaries

    Args:
        d1: first dictionary
        d2: second dictionary
        tolerance: tolerance for comparing floats
        path: path to current key in dictionary (used for recursion)

    Returns:
        list of differences in the form of a list of tuples of the form:
        [path, change_type, (old_value, new_value)]
        where:
            path: path to the key in the dictionary
            change_type: one of "added", "removed", "changed"
            old_value: old value of the key
            new_value: new value of the key
    """
    diffs: list[list[Any]] = []
    for k, value in d1.items():
        new_path = f"{path}[{k}]" if path else k
        if k not in d2:
            diffs.append([new_path, "removed", (value,)])
        elif isinstance(value, dict) and isinstance(d2[k], dict):
            diffs.extend(_dictdiff(value, d2[k], tolerance, new_path))
        elif isinstance(value, (list, set, tuple)) and isinstance(
            d2[k], (list, set, tuple)
        ):
            added: set[Any] = set()
            removed: set[Any] = set()
            try:
                added = set(d2[k]) - set(value)
                removed = set(value) - set(d2[k])
            except TypeError:
                # can't compare sets of unhashable types
                if value != d2[k]:
                    diffs.append([new_path, "changed", (value, d2[k])])
            if added:
                diffs.append([new_path, "added", list(added)])
            if removed:
                diffs.append([new_path, "removed", list(removed)])
        elif not _compare(value, d2[k], tolerance):
            diffs.append([new_path, "changed", (value, d2[k])])
    for k in set(d2.keys()) - set(d1.keys()):
        new_path = f"{path}[{k}]" if path else k
        diffs.append([new_path, "added", (d2[k],)])
    return diffs
