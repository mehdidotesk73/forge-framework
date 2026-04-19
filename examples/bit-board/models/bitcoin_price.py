"""
Model Layer — BitcoinPrice (snapshot)
Backed by dataset f0e4b4e0-607a-4c2a-8b2b-fe0af3aae278.
After `forge model build`, mutations go to the snapshot copy.
"""

from forge.model import forge_model, field_def, ForgeSnapshotModel

DATASET_ID = "f0e4b4e0-607a-4c2a-8b2b-fe0af3aae278"


@forge_model(mode="snapshot", backing_dataset=DATASET_ID)
class BitcoinPrice(ForgeSnapshotModel):
    pK: str = field_def(primary_key=True, display="pK")
    Date: str = field_def(display="Date", display_hint="date")
    Close: float = field_def(display="Close")
    High: float = field_def(display="High")
    Low: float = field_def(display="Low")
    Open: float = field_def(display="Open")
    Volume: int = field_def(display="Volume")
