"""
Control Layer — computed_endpoints
Returns structured data for visualizations: DAG, layer lineage, and project health.
"""
from __future__ import annotations

from forge.control import action_endpoint

PIPELINE_DAG_ID   = "cccccccc-0008-0000-0000-000000000000"
LAYER_LINEAGE_ID  = "cccccccc-0009-0000-0000-000000000000"
PROJECT_HEALTH_ID = "cccccccc-0010-0000-0000-000000000000"


@action_endpoint(
    name="pipeline_dag",
    endpoint_id=PIPELINE_DAG_ID,
    description="Return DAG nodes and edges for the pipeline visualization",
    params=[
        {"name": "project_id", "type": "string", "required": False, "default": ""},
    ],
)
def pipeline_dag(project_id: str = "") -> dict:
    from forge_suite.operations.viz import pipeline_dag as _op
    return _op(project_id)


@action_endpoint(
    name="layer_lineage",
    endpoint_id=LAYER_LINEAGE_ID,
    description="Return layer band data for the lineage visualization",
    params=[
        {"name": "project_id", "type": "string", "required": False, "default": ""},
    ],
)
def layer_lineage(project_id: str = "") -> dict:
    from forge_suite.operations.viz import layer_lineage as _op
    return _op(project_id)


@action_endpoint(
    name="project_health",
    endpoint_id=PROJECT_HEALTH_ID,
    description="Return health metrics for a project",
    params=[
        {"name": "project_id", "type": "string", "required": False, "default": ""},
    ],
)
def project_health(project_id: str = "") -> dict:
    from forge_suite.operations.viz import project_health as _op
    return _op(project_id)
