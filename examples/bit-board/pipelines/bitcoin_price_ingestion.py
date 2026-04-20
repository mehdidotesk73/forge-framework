"""
Pipeline Layer — bitcoin_price_ingestion
"""

from forge.pipeline import pipeline, ForgeOutput

# These UUIDs were generated for this pipeline. Load data into them with:
#   forge dataset load <file.csv> --name source     (to populate INPUT_DATASET_ID)
# Or replace them with existing dataset UUIDs from `forge dataset list`.

import hashlib
import yfinance as yf

PIPELINE_ID       = "cccccccc-0000-0000-0000-000000000001"
OUTPUT_DATASET_ID = "f0e4b4e0-607a-4c2a-8b2b-fe0af3aae278"


@pipeline(
    pipeline_id=PIPELINE_ID,
    inputs={},
    outputs={"result": ForgeOutput(OUTPUT_DATASET_ID)},
)
def run(inputs, outputs):
    df = yf.download("BTC-USD", period="10y", interval="1d")
    if df is None or df.empty:
        raise ValueError("yfinance returned no data for BTC-USD")
    df = df.reset_index()
    if hasattr(df.columns, "levels"):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    df["pK"] = (
        df["Date"].astype(str).apply(lambda d: hashlib.md5(d.encode()).hexdigest())
    )

    print(df.head())
    outputs.result.write(df)
