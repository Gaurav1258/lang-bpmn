import asyncio
import pytest
from pydantic import BaseModel, Field

from agent_bpmn.sdk import (
    BlockExecutionError,
    BlockValidationError,
    CapabilityRegistry,
    domain_block,
)
from agent_bpmn.blocks.builtin import (
    SanctionCheckInput,
    SanctionCheckOutput,
    screen_sanctions,
    extract_invoice,
    triage_ticket,
)


class DummyInput(BaseModel):
    message: str


class DummyOutput(BaseModel):
    echo: str


def test_step1_1_domain_block_metadata_and_contracts_attached():
    """Verify @domain_block correctly attaches business metadata and Pydantic model names."""
    contract = getattr(screen_sanctions, "__domain_block_contract__", None)
    assert contract is not None
    assert contract.metadata.id == "compliance.sanctions_screener"
    assert contract.metadata.department == "Compliance"
    assert contract.metadata.estimated_cost_usd == 0.004
    assert contract.input_model_name == "SanctionCheckInput"
    assert contract.output_model_name == "SanctionCheckOutput"


def test_step1_2_clean_json_schemas_generated_without_code_leakage():
    """Verify input/output Pydantic schemas export clean JSON schemas for canvas use."""
    contract = getattr(screen_sanctions, "__domain_block_contract__")
    input_schema = contract.input_schema
    assert "properties" in input_schema
    assert "entity_name" in input_schema["properties"]
    assert "transaction_amount_usd" in input_schema["properties"]

    output_schema = contract.output_schema
    assert "properties" in output_schema
    assert "is_flagged" in output_schema["properties"]
    assert "risk_score" in output_schema["properties"]


def test_step1_3_decorator_rejects_missing_pydantic_type_annotations():
    """Verify @domain_block strictly enforces Pydantic BaseModel annotations on input and output."""
    local_registry = CapabilityRegistry()

    with pytest.raises(TypeError, match="must accept an input payload annotated with a Pydantic BaseModel"):
        @domain_block(id="bad.block_1", name="Bad 1", department="Test", description="Bad", registry=local_registry)
        def bad_block_no_args():
            pass

    with pytest.raises(TypeError, match="must be annotated with a Pydantic BaseModel subclass"):
        @domain_block(id="bad.block_2", name="Bad 2", department="Test", description="Bad", registry=local_registry)
        def bad_block_untyped_arg(x: str):
            return x

    with pytest.raises(TypeError, match="return type must be annotated with a Pydantic BaseModel subclass"):
        @domain_block(id="bad.block_3", name="Bad 3", department="Test", description="Bad", registry=local_registry)
        def bad_block_untyped_return(payload: DummyInput):
            return {"echo": payload.message}


@pytest.mark.asyncio
async def test_step1_4_registry_execution_with_valid_typed_payload():
    """Verify CapabilityRegistry executes sync and async blocks and validates returned types."""
    local_reg = CapabilityRegistry()

    @domain_block(
        id="test.echo",
        name="Echo Service",
        department="Testing",
        description="Echoes input",
        registry=local_reg,
    )
    def echo_fn(payload: DummyInput) -> DummyOutput:
        return DummyOutput(echo=f"Echo: {payload.message}")

    # Test via dict payload
    res = await local_reg.execute("test.echo", {"message": "hello world"})
    assert isinstance(res, DummyOutput)
    assert res.echo == "Echo: hello world"

    # Test via model payload
    res2 = await local_reg.execute("test.echo", DummyInput(message="again"))
    assert res2.echo == "Echo: again"


@pytest.mark.asyncio
async def test_step1_5_registry_execution_rejects_invalid_schema_payload():
    """Verify runtime guardrail catches schema violations and raises BlockValidationError before execution."""
    local_reg = CapabilityRegistry()

    @domain_block(
        id="test.typed",
        name="Typed Service",
        department="Testing",
        description="Requires integer count",
        registry=local_reg,
    )
    def typed_fn(payload: SanctionCheckInput) -> SanctionCheckOutput:
        return SanctionCheckOutput(is_flagged=False, risk_score=0.1, compliance_note="ok")

    # Pass invalid transaction_amount_usd (negative number not allowed by ge=0.0)
    with pytest.raises(BlockValidationError):
        await local_reg.execute("test.typed", {
            "entity_name": "Test LLC",
            "country_code": "US",
            "transaction_amount_usd": -50.0,
        })


def test_step1_6_catalog_department_grouping_and_json_export():
    """Verify capability catalog groups blocks by department and serializes to JSON."""
    from agent_bpmn.sdk import registry

    catalog = registry.to_catalog()
    assert catalog.total_blocks >= 3
    assert "Compliance" in catalog.departments
    assert "Finance" in catalog.departments
    assert "Customer Care" in catalog.departments

    json_catalog = registry.export_catalog_json()
    assert "compliance.sanctions_screener" in json_catalog
    assert "finance.invoice_extractor" in json_catalog
    assert "support.ticket_triage" in json_catalog
