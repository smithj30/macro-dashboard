"""
ComputedProvider — creates derived series from two existing feeds.

Stores operand_a (feed_id), operand_b (feed_id), and operation in the
feed's params dict.  Because it implements BaseProvider.fetch_series(),
computed feeds work everywhere: dashboards, Chart Builder, refresh script.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

from providers.base_provider import BaseProvider


# Supported binary operations
OPERATIONS = {
    "div": ("A / B", lambda a, b: a / b),
    "sub": ("A - B", lambda a, b: a - b),
    "add": ("A + B", lambda a, b: a + b),
    "mul": ("A * B", lambda a, b: a * b),
    "pct_diff": ("% diff (A-B)/B", lambda a, b: (a - b) / b * 100),
}

OP_LABELS = {k: v[0] for k, v in OPERATIONS.items()}


class ComputedProvider(BaseProvider):
    """Provider that computes a derived series from two feed operands."""

    @property
    def name(self) -> str:
        return "Computed"

    def fetch_series(
        self,
        series_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Compute a derived series from two feed operands.

        Required kwargs (or stored in feed params):
            operand_a : feed_id for the first operand
            operand_b : feed_id for the second operand
            operation : one of div, sub, add, mul, pct_diff
        """
        from services.data_resolver import resolve_feed_data

        operand_a = kwargs.get("operand_a")
        operand_b = kwargs.get("operand_b")
        operation = kwargs.get("operation", "div")

        if not operand_a or not operand_b:
            raise ValueError("ComputedProvider requires operand_a and operand_b feed IDs")

        if operation not in OPERATIONS:
            raise ValueError(f"Unknown operation {operation!r}. Supported: {list(OPERATIONS)}")

        df_a = resolve_feed_data(operand_a, start_date=start_date, end_date=end_date)
        if df_a.empty:
            raise ValueError(f"Operand A feed returned no data: {operand_a}")

        df_b = resolve_feed_data(operand_b, start_date=start_date, end_date=end_date)
        if df_b.empty:
            raise ValueError(f"Operand B feed returned no data: {operand_b}")

        # Get first numeric column from each
        sa = df_a.select_dtypes(include="number").iloc[:, 0]
        sb = df_b.select_dtypes(include="number").iloc[:, 0]

        # Align on DatetimeIndex
        sa, sb = sa.align(sb, join="inner")

        # Apply operation
        _, op_fn = OPERATIONS[operation]
        result = op_fn(sa, sb)

        return result.to_frame(name="value")
