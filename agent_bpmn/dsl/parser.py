import json
from pathlib import Path
from typing import Union
import yaml

from agent_bpmn.dsl.schema import WorkflowDefinition


class WorkflowParseError(Exception):
    """Raised when parsing a workflow definition fails."""
    pass


def parse_workflow_yaml(content_or_path: Union[str, Path]) -> WorkflowDefinition:
    """Parses a YAML string or file path into a strongly-typed WorkflowDefinition AST."""
    raw_str = ""
    if isinstance(content_or_path, Path) or (isinstance(content_or_path, str) and "\n" not in content_or_path and Path(content_or_path).is_file()):
        raw_str = Path(content_or_path).read_text(encoding="utf-8")
    else:
        raw_str = str(content_or_path)

    try:
        data = yaml.safe_load(raw_str)
        if not isinstance(data, dict):
            raise WorkflowParseError("YAML content must resolve to a top-level dictionary")
        return WorkflowDefinition.model_validate(data)
    except Exception as e:
        raise WorkflowParseError(f"Failed to parse workflow YAML: {str(e)}") from e


def parse_workflow_json(content_or_path: Union[str, Path]) -> WorkflowDefinition:
    """Parses a JSON string or file path into a strongly-typed WorkflowDefinition AST."""
    raw_str = ""
    if isinstance(content_or_path, Path) or (isinstance(content_or_path, str) and "\n" not in content_or_path and Path(content_or_path).is_file()):
        raw_str = Path(content_or_path).read_text(encoding="utf-8")
    else:
        raw_str = str(content_or_path)

    try:
        data = json.loads(raw_str)
        if not isinstance(data, dict):
            raise WorkflowParseError("JSON content must resolve to a top-level dictionary")
        return WorkflowDefinition.model_validate(data)
    except Exception as e:
        raise WorkflowParseError(f"Failed to parse workflow JSON: {str(e)}") from e


def dump_workflow_yaml(workflow: WorkflowDefinition) -> str:
    """Serializes a WorkflowDefinition AST into a clean, Git-friendly YAML document."""
    data = workflow.model_dump(exclude_none=True, mode="json")
    return yaml.dump(data, sort_keys=False, indent=2)


def dump_workflow_json(workflow: WorkflowDefinition, indent: int = 2) -> str:
    """Serializes a WorkflowDefinition AST into a formatted JSON document."""
    return workflow.model_dump_json(exclude_none=True, indent=indent)

