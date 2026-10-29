import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union
from pydantic import BaseModel, ValidationError

from agent_bpmn.sdk.models import (
    CapabilityCatalog,
    DomainBlockContract,
    DomainBlockMetadata,
)


class BlockExecutionError(Exception):
    """Raised when an error occurs during domain block execution."""
    def __init__(self, block_id: str, message: str, details: Optional[Any] = None):
        super().__init__(f"[{block_id}] {message}")
        self.block_id = block_id
        self.details = details


class BlockValidationError(BlockExecutionError):
    """Raised when input or output validation fails against the Pydantic schema."""
    pass


@dataclass
class RegisteredBlock:
    contract: DomainBlockContract
    handler: Callable[..., Any]
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]
    is_async: bool


class CapabilityRegistry:
    """
    Central repository for certified business capability blocks.
    Developers register blocks here; the visual canvas queries this registry
    to populate department-based palettes.
    """

    def __init__(self) -> None:
        self._blocks: Dict[str, RegisteredBlock] = {}

    def register(
        self,
        contract: DomainBlockContract,
        handler: Callable[..., Any],
        input_model: Type[BaseModel],
        output_model: Type[BaseModel],
    ) -> None:
        block_id = contract.metadata.id
        if block_id in self._blocks:
            # Overwrite or warn; allow hot reloading in dev
            pass
        
        is_async = inspect.iscoroutinefunction(handler)
        self._blocks[block_id] = RegisteredBlock(
            contract=contract,
            handler=handler,
            input_model=input_model,
            output_model=output_model,
            is_async=is_async,
        )

    def get(self, block_id: str) -> RegisteredBlock:
        if block_id not in self._blocks:
            raise KeyError(f"Domain block '{block_id}' not found in registry. Available blocks: {list(self._blocks.keys())}")
        return self._blocks[block_id]

    def has(self, block_id: str) -> bool:
        return block_id in self._blocks

    def list_blocks(self) -> List[DomainBlockContract]:
        return [b.contract for b in self._blocks.values()]

    def list_departments(self) -> List[str]:
        departments = {b.contract.metadata.department for b in self._blocks.values()}
        return sorted(list(departments))

    def get_by_department(self, department: str) -> List[DomainBlockContract]:
        return [
            b.contract
            for b in self._blocks.values()
            if b.contract.metadata.department.lower() == department.lower()
        ]

    def to_catalog(self) -> CapabilityCatalog:
        departments_map: Dict[str, List[DomainBlockContract]] = {}
        for b in self._blocks.values():
            dept = b.contract.metadata.department
            if dept not in departments_map:
                departments_map[dept] = []
            departments_map[dept].append(b.contract)

        return CapabilityCatalog(
            total_blocks=len(self._blocks),
            departments=departments_map,
        )

    def export_catalog_json(self, filepath: Optional[Union[str, Path]] = None, indent: int = 2) -> str:
        catalog = self.to_catalog()
        json_str = catalog.model_dump_json(indent=indent)
        if filepath:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json_str, encoding="utf-8")
        return json_str

    async def execute(self, block_id: str, payload: Union[Dict[str, Any], BaseModel]) -> BaseModel:
        """
        Executes a registered domain block with strict runtime schema validation.
        Validates the input payload against the input model, calls the underlying handler,
        and validates the return value against the output model.
        """
        block = self.get(block_id)

        # 1. Input validation
        if isinstance(payload, block.input_model):
            validated_input = payload
        elif isinstance(payload, dict):
            try:
                validated_input = block.input_model.model_validate(payload)
            except ValidationError as e:
                raise BlockValidationError(
                    block_id=block_id,
                    message=f"Input failed schema validation: {e}",
                    details=e.errors(),
                ) from e
        else:
            raise BlockValidationError(
                block_id=block_id,
                message=f"Expected input of type {block.input_model.__name__} or dict, got {type(payload).__name__}",
            )

        # 2. Execution
        try:
            if block.is_async:
                result = await block.handler(validated_input)
            else:
                result = block.handler(validated_input)
        except Exception as e:
            raise BlockExecutionError(
                block_id=block_id,
                message=f"Handler execution raised exception: {str(e)}",
            ) from e

        # 3. Output validation
        if isinstance(result, block.output_model):
            validated_output = result
        elif isinstance(result, dict):
            try:
                validated_output = block.output_model.model_validate(result)
            except ValidationError as e:
                raise BlockValidationError(
                    block_id=block_id,
                    message=f"Output failed schema validation: {e}",
                    details=e.errors(),
                ) from e
        else:
            raise BlockValidationError(
                block_id=block_id,
                message=f"Expected output of type {block.output_model.__name__} or dict, got {type(result).__name__}",
            )

        return validated_output

    def clear(self) -> None:
        self._blocks.clear()


# Default singleton instance
registry = CapabilityRegistry()

