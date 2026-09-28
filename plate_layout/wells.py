"""Well coordinate helpers for fixed 8-row x 12-column plates.

Rows are letters A-H (1-indexed), columns are numbers 1-12 (1-indexed).
Canonical well labels look like ``A1`` or ``H12`` (no zero padding).
"""

from __future__ import annotations

ROWS = 8
COLS = 12
ROW_LETTERS = "ABCDEFGH"


def parse_well(value: str) -> tuple[int, int]:
    """Parse a well label like ``C7`` into a 1-based ``(row, col)`` tuple.

    Raises ``ValueError`` for malformed or out-of-range labels.
    """
    text = (value or "").strip().upper()
    if len(text) < 2 or not text[0].isalpha() or not text[1:].isdigit():
        raise ValueError(f"invalid well {value!r}: expected form like 'A1'")
    row = ord(text[0]) - ord("A") + 1
    col = int(text[1:])
    if not 1 <= row <= ROWS or not 1 <= col <= COLS:
        raise ValueError(
            f"invalid well {value!r}: row must be A-{ROW_LETTERS[-1]}, "
            f"column 1-{COLS}"
        )
    return row, col


def well_label(row: int, col: int) -> str:
    """Format a 1-based ``(row, col)`` pair as a canonical well label."""
    return f"{ROW_LETTERS[row - 1]}{col}"


def all_wells() -> list[str]:
    """Return all 96 labels in row-major (先 A1..A12, then B...) order."""
    return [
        well_label(row, col)
        for row in range(1, ROWS + 1)
        for col in range(1, COLS + 1)
    ]
