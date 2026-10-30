from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from agent_bpmn.server.app import app
import agent_bpmn.blocks.builtin  # Ensures blocks are registered


@pytest.fixture
def client():
    return TestClient(app)


def test_step7_1_health_check_endpoint(client):
    """Verify API server health check returns 200 and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "version" in data


def test_step7_2_capabilities_catalog_endpoint(client):
    """Verify capabilities catalog endpoint exports all certified domain blocks."""
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    catalog = response.json()
    assert "departments" in catalog
    assert "Finance" in catalog["departments"]
    assert "Compliance" in catalog["departments"]

    # Test single block retrieval
    detail_res = client.get("/api/capabilities/finance.invoice_extractor")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["metadata"]["id"] == "finance.invoice_extractor"
    assert "properties" in detail["input_schema"]


def test_step7_3_workflows_listing_and_detail(client):
    """Verify workflows endpoints list samples and return YAML and parsed ASTs."""
    list_res = client.get("/api/workflows")
    assert list_res.status_code == 200
    workflows = list_res.json()
    assert len(workflows) >= 3

    # Find hybrid_routing_workflow.yaml
    found = next((w for w in workflows if "hybrid_routing" in w["file_name"]), None)
    assert found is not None
    assert found["node_count"] >= 4

    # Fetch detail
    detail_res = client.get(f"/api/workflows/{found['file_name']}")
    assert detail_res.status_code == 200
    data = detail_res.json()
    assert "yaml_content" in data
    assert "ast" in data
    assert data["ast"]["metadata"]["id"] == "hybrid_invoice_routing_flow"


def test_step7_4_workflow_linter_endpoint(client):
    """Verify workflow linter endpoint catches syntax and topological issues."""
    valid_yaml = Path("examples/sample_workflows/invoice_processing_workflow.yaml").read_text(encoding="utf-8")
    res = client.post("/api/workflows/lint", json={"yaml_content": valid_yaml})
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert len(data["errors"]) == 0

    bad_yaml = "version: '1.0'\nmetadata:\n  id: test\nnodes: []\nedges: []"
    res_bad = client.post("/api/workflows/lint", json={"yaml_content": bad_yaml})
    assert res_bad.status_code == 200
    data_bad = res_bad.json()
    assert data_bad["is_valid"] is False
    assert len(data_bad["errors"]) > 0


def test_step7_5_workflow_execution_endpoint(client):
    """Verify backend executes a workflow and returns full state updates and telemetry."""
    yaml_content = Path("examples/sample_workflows/invoice_processing_workflow.yaml").read_text(encoding="utf-8")
    payload = {
        "workflow_yaml": yaml_content,
        "input_payload": {
            "invoice_pdf_url": "s3://invoices-2026/q3/apex_cloud_inv9812.pdf",
            "tax_id": "US-94-8192019",
        },
    }
    res = client.post("/api/workflows/execute", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "COMPLETED"
    assert data["final_state"]["extracted_invoice_num"] == "INV-2026-9812"
    assert "extract_invoice" in data["history"]
    assert "check_sanctions" in data["history"]


def test_step7_6_telemetry_and_simulation_endpoints(client):
    """Verify telemetry heatmap retrieval and pre-flight simulation replay endpoints."""
    # Seed traces
    seed_res = client.post("/api/telemetry/seed_demo_traces/hybrid_invoice_routing_flow")
    assert seed_res.status_code == 200

    heatmap_res = client.get("/api/telemetry/heatmaps/hybrid_invoice_routing_flow")
    assert heatmap_res.status_code == 200
    heatmap = heatmap_res.json()
    assert heatmap["total_runs"] > 0
    assert "extract_invoice" in heatmap["node_metrics"]

    # Pre-flight simulation
    candidate_yaml = Path("examples/sample_workflows/candidate_tightened_policy_workflow.yaml").read_text(encoding="utf-8")
    sim_res = client.post("/api/simulation/run", json={"candidate_workflow_yaml": candidate_yaml, "sample_size": 5})
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    assert "diff" in sim_data
    assert "markdown_report" in sim_data
    assert sim_data["diff"]["total_cases"] == 5


def test_step7_7_frontend_studio_spa_served(client):
    """Verify FastAPI server serves the compiled React Web Studio SPA index.html."""
    dist_index = Path("studio/dist/index.html")
    if not dist_index.exists():
        pytest.skip("Frontend studio/dist not compiled yet (normal during headless Python CI)")
    res = client.get("/")
    assert res.status_code == 200
    assert "AgentBPMN Studio" in res.text
    assert '<div id="root">' in res.text


def test_step7_8_workflow_crud_endpoints(client):
    """Verify workflow creation, updating, and deletion endpoints."""
    # 1. Create a new workflow from a template
    create_payload = {
        "name": "Custom AML Compliance Review",
        "workflow_id": "custom_aml_review_test",
        "department": "Regulatory Compliance",
        "description": "Custom AML screening and high-value compliance flow",
        "template": "linear",
    }
    create_res = client.post("/api/workflows", json=create_payload)
    assert create_res.status_code == 200
    created_data = create_res.json()
    assert created_data["workflow_id"] == "custom_aml_review_test"
    assert created_data["file_name"] == "custom_aml_review_test.yaml"
    assert "Extract Invoice Line Items" in created_data["yaml_content"]

    # 2. Verify it is returned in list
    list_res = client.get("/api/workflows")
    assert list_res.status_code == 200
    file_names = [w["file_name"] for w in list_res.json()]
    assert "custom_aml_review_test.yaml" in file_names

    # 3. Update the workflow AST / YAML
    update_payload = {
        "yaml_content": created_data["yaml_content"].replace("Extract Invoice Line Items", "Pre-process Document Feed")
    }
    update_res = client.put("/api/workflows/custom_aml_review_test.yaml", json=update_payload)
    assert update_res.status_code == 200
    assert "Pre-process Document Feed" in update_res.json()["yaml_content"]

    # 4. Clean up / delete the test workflow
    delete_res = client.delete("/api/workflows/custom_aml_review_test.yaml")
    assert delete_res.status_code == 200
    assert "deleted successfully" in delete_res.json()["message"]

    # 5. Verify deletion
    verify_res = client.get("/api/workflows/custom_aml_review_test.yaml")
    assert verify_res.status_code == 404

