"""
Control Layer — price_endpoints repo
Computed column endpoint that adds a moving average column to the Price stream.
"""

from __future__ import annotations

from forge.control import computed_attribute_endpoint
from models.price import Price

MOVING_AVG_ID = "e9947f90-da94-4f5e-8602-e79c13c62868"


@computed_attribute_endpoint(
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
    objects: list[Price],
    days: int = 20,
) -> dict:
    if not objects:
        return {}

    df = Price.to_dataframe(objects)
    df = df.sort_values(["symbol", "date"])

    df["moving_avg"] = (
        df.groupby("symbol")["close"]
        .transform(lambda s: s.rolling(window=int(days), min_periods=1).mean())
        .round(2)
    )

    return {
        row["pK"]: {"moving_avg": row["moving_avg"]}
        for _, row in df[["pK", "moving_avg"]].iterrows()
    }
