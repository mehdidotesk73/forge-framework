"""
Control Layer — bitcoin_processing
"""

from __future__ import annotations

from forge.control import computed_column_endpoint
from models.bitcoin_price import BitcoinPrice

GET_BITCOIN_METRICS_ID = "2fecbcfc-e136-49c1-aa5c-c3a36c608169"
MOVING_AVERAGE_WINDOW = 7  # default window in days


@computed_column_endpoint(
    object_type="BitcoinPrice",
    columns=["moving_average"],
    endpoint_id=GET_BITCOIN_METRICS_ID,
    name="get_bitcoin_metrics",
    description="Returns bitcoin moving average computed data over a specified window (default 7 days).",
)
# def get_bitcoin_metrics(objects: list[BitcoinPrice]) -> dict:
#     # TODO: compute a value per object; keys must be object IDs
#     return {obj.Date: {"my_column": None} for obj in objects}
def get_bitcoin_metrics(
    objects: list[BitcoinPrice], window: int = MOVING_AVERAGE_WINDOW
) -> dict:
    print(f"[get_bitcoin_metrics] called with {len(objects)} objects, window={window}")
    price_df = BitcoinPrice.to_dataframe(objects)
    price_df = price_df.sort_values("Date")
    print(
        f"[get_bitcoin_metrics] dataframe shape: {price_df.shape}, columns: {list(price_df.columns)}"
    )

    price_df["moving_average"] = (
        price_df["Close"].rolling(window=window, min_periods=1).mean().round(2)
    )

    result = {
        row["pK"]: {"moving_average": row["moving_average"]}
        for _, row in price_df[["pK", "moving_average"]].iterrows()
    }
    print(f"[get_bitcoin_metrics] returning {len(result)} entries")
    return result
