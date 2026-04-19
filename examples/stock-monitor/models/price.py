"""
Model Layer — Price (stream)
Read-only stream object backed by the prices pipeline output.
When price_pipeline reruns, this object set reflects the new data automatically.
"""

from forge.model import forge_model, field_def

PRICES_DATASET_ID = "9dac026d-5f47-43c3-a216-6235be88f9dd"


@forge_model(mode="stream", backing_dataset=PRICES_DATASET_ID)
class Price:
    pK: str = field_def(display="pK", primary_key=True)
    symbol: str = field_def(display="Symbol")
    date: str = field_def(display="Date", display_hint="date")
    open: float = field_def(display="Open", display_hint="currency")
    high: float = field_def(display="High", display_hint="currency")
    low: float = field_def(display="Low", display_hint="currency")
    close: float = field_def(display="Close", display_hint="currency")
    volume: int = field_def(display="Volume")
