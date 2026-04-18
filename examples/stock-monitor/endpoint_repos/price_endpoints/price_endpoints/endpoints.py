"""
Control Layer — price_endpoints repo
Computed column endpoint that adds a moving average column to the Price stream.
"""
from __future__ import annotations

from typing import Any

from forge.control import computed_column_endpoint

MOVING_AVG_ID = "22222222-0000-0000-0000-000000000001"


@computed_column_endpoint(
    object_type="Price",
    columns=["moving_avg"],
    endpoint_id=MOVING_AVG_ID,
    name="compute_moving_average",
    description="Compute a rolling moving average of the close price",
    params=[
        {
            "name": "days",
            "type": "integer",
            "required": False,
            "description": "Rolling window in trading days",
            "default": 20,
        }
    ],
)
def compute_moving_average(
    objects: list[dict[str, Any]],
    days: int = 20,
) -> dict[str, list[Any]]:
    """
    Given a list of Price records, return per-record moving average of close price.
    Groups by symbol and computes rolling mean within each group.
    """
    if not objects:
        return {"moving_avg": []}

    import pandas as pd

    df = pd.DataFrame(objects)
    df = df.sort_values(["symbol", "date"])

    # Compute rolling mean per symbol
    df["moving_avg"] = (
        df.groupby("symbol")["close"]
        .transform(lambda s: s.rolling(window=int(days), min_periods=1).mean())
        .round(2)
    )

    return {"moving_avg": df["moving_avg"].tolist()}
