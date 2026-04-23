"""index_skills pipeline — scans both skill locations and writes the SkillIndex dataset.

Run this pipeline whenever skills are added, updated, or deleted to keep the
Forge Suite UI in sync with the filesystem.
"""
from __future__ import annotations

import pandas as pd

from forge.pipeline.decorator import ForgeOutput, pipeline

from ai_chat_endpoints.skills import build_index_rows
from models.models import SKILL_INDEX_DATASET_ID


@pipeline(
    pipeline_id="a1ca4000-0003-0000-0000-000000000001",
    name="index_skills",
    inputs={},
    outputs={"skill_index": ForgeOutput(SKILL_INDEX_DATASET_ID)},
)
def run(inputs, outputs) -> None:  # type: ignore[override]
    """Scan both skill locations and write one row per skill file to SkillIndex."""
    rows = build_index_rows()
    df = pd.DataFrame(rows) if rows else _empty_dataframe()
    outputs.skill_index.write(df)


def _empty_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "id", "name", "description", "version",
        "depends_on", "triggers", "file_path", "source", "last_indexed_at",
    ])
