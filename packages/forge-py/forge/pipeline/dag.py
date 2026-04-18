"""Pipeline dependency DAG computation."""
from __future__ import annotations

from dataclasses import dataclass

from forge.config import ProjectConfig
from forge.pipeline.decorator import PipelineDefinition


@dataclass
class DAGNode:
    pipeline_name: str
    input_dataset_ids: list[str]
    output_dataset_ids: list[str]


def build_dag(
    pipelines: list[PipelineDefinition],
) -> tuple[list[DAGNode], list[tuple[str, str]]]:
    """Return nodes and edges (pipeline_name → pipeline_name) based on dataset flow."""
    nodes = []
    # dataset_id → pipeline that produces it
    producers: dict[str, str] = {}

    for defn in pipelines:
        node = DAGNode(
            pipeline_name=defn.name,
            input_dataset_ids=[v.dataset_id for v in defn.inputs.values()],
            output_dataset_ids=[v.dataset_id for v in defn.outputs.values()],
        )
        nodes.append(node)
        for dataset_id in node.output_dataset_ids:
            producers[dataset_id] = defn.name

    edges: list[tuple[str, str]] = []
    for node in nodes:
        for dataset_id in node.input_dataset_ids:
            producer = producers.get(dataset_id)
            if producer and producer != node.pipeline_name:
                edges.append((producer, node.pipeline_name))

    return nodes, edges


def render_dag(nodes: list[DAGNode], edges: list[tuple[str, str]]) -> str:
    """Return an ASCII/text representation of the DAG."""
    if not nodes:
        return "(no pipelines registered)"

    lines = ["Pipeline Dependency DAG", "=" * 40]
    adj: dict[str, list[str]] = {n.pipeline_name: [] for n in nodes}
    for src, dst in edges:
        adj[src].append(dst)

    roots = {n.pipeline_name for n in nodes} - {dst for _, dst in edges}

    def render_node(name: str, indent: int, visited: set[str]) -> None:
        prefix = "  " * indent + ("└─ " if indent > 0 else "")
        lines.append(f"{prefix}{name}")
        if name in visited:
            return
        visited.add(name)
        for child in adj.get(name, []):
            render_node(child, indent + 1, visited)

    visited: set[str] = set()
    for root in sorted(roots):
        render_node(root, 0, visited)

    # Any remaining disconnected nodes
    for node in nodes:
        if node.pipeline_name not in visited:
            render_node(node.pipeline_name, 0, visited)

    return "\n".join(lines)
