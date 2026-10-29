# AgentBPMN: Architecture & Master Implementation Plan

> **Enterprise Process Orchestration & Governance Platform for AI Agents**  
> Document Version: 1.0.0  
> Status: Architectural Blueprint & Planning

---

## 1. Executive Summary & Philosophy

Existing multi-agent frameworks force a false dichotomy:
- **Developer-only code (LangGraph, AutoGen, CrewAI):** Complete programmatic control, but zero visibility for business stakeholders, risk officers, and compliance auditors.
- **Low-code drag-and-drop builders (Langflow, Flowise, Dify):** Leak model parameters, prompt engineering, and raw code into visual cards, resulting in fragile workflows, security holes, and accidental prompt regressions.

**AgentBPMN** bridges this divide by introducing a **Two-Persona Separation of Concerns**:
- **Engineers** write and maintain robust, typed, encapsulated Python code decorated as **Domain Blocks** (`@domain_block`). Engineering owns models, system prompts, vector stores, MCP tools, and Pydantic schemas.
- **Management & Operations** orchestrate these pre-certified domain blocks on a BPMN-inspired canvas using **DMN decision tables**, **semantic routers**, **SLA timers**, **approval inboxes**, and **cost guardrails**.
- The canvas compiles directly to a deterministic, cyclic **LangGraph `StateGraph`** backed by Git-driven governance (`agent-bpmn.yaml`).

---

## 2. Core System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PRESENTATION TIER                               │
│                                                                        │
│   ┌─────────────────────────────┐   ┌──────────────────────────────┐   │
│   │   AgentBPMN Canvas Studio   │   │   Enterprise Approval Inbox  │   │
│   │   (React Flow / BPMN.io)    │   │   (Dynamic Pydantic Forms)   │   │
│   ├─────────────────────────────┤   ├──────────────────────────────┤   │
│   │   DMN Decision Table UI     │   │   Simulation Diff & Heatmap  │   │
│   │   (Handsontable / TanStack) │   │   (Process Intelligence)     │   │
│   └─────────────────────────────┘   └──────────────────────────────┘   │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │ REST / WebSocket / SSE
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       APPLICATION & COMPILER TIER                      │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │ FastApi Gateway & RBAC Auth (Okta / SAML / OIDC)               │   │
│   ├──────────────────────────────┬─────────────────────────────────┤   │
│   │ Specification Parser (YAML)  │ AST Validator & Linter          │   │
│   ├──────────────────────────────┼─────────────────────────────────┤   │
│   │ DMN Decision Table Compiler  │ Semantic Router Synthesizer     │   │
│   ├──────────────────────────────┼─────────────────────────────────┤   │
│   │ LangGraph Graph Compiler     │ SLA & Escalation Timer Engine   │   │
│   ├──────────────────────────────┼─────────────────────────────────┤   │
│   │ Simulation & Replay Runner   │ Git Governance & PR Generator   │   │
│   └──────────────────────────────┴─────────────────────────────────┘   │
└─────────────────────────────────┬──────────────────────────────────────┘
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        EXECUTION RUNTIME TIER                          │
│                                                                        │
│   ┌──────────────────────────────┬─────────────────────────────────┐   │
│   │ LangGraph StateGraph Runtime │ Domain Block SDK Registry       │   │
│   ├──────────────────────────────┼─────────────────────────────────┤   │
│   │ Checkpointer Engine          │ Unit Economics & Loop Guardrail │   │
│   │ (Postgres / SQLite)          │ Interceptor                     │   │
│   └──────────────────────────────┴─────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Deep-Dive Specification of the Six Pillars

### Pillar 1: "Domain Blocks" Instead of "Technical Nodes"

#### Concept & Developer Experience
Engineers encapsulate all LLM configuration, prompts, subgraphs, and toolchains within decorated Python functions. The management canvas never sees raw prompts or model selectors.

```python
from pydantic import BaseModel, Field
from agent_bpmn.sdk import domain_block

class InvoiceExtractionInput(BaseModel):
    document_url: str = Field(description="Cloud storage URL to invoice PDF")
    vendor_tax_id: str | None = None

class InvoiceExtractionOutput(BaseModel):
    invoice_number: str
    total_amount_usd: float
    line_items: list[dict[str, str | float]]
    confidence_score: float = Field(ge=0.0, le=1.0)

@domain_block(
    id="finance.invoice_extractor",
    name="Extract Invoice Line Items",
    department="Finance",
    description="Parses PDF invoices and extracts structured line items and totals.",
    icon="receipt-text",
    estimated_cost_usd=0.012,
    p95_latency_ms=1800,
)
async def extract_invoice(input_data: InvoiceExtractionInput) -> InvoiceExtractionOutput:
    # Developer owns model choice, OCR / vision prompts, MCP tool bindings, and error retry logic
    ...
```

#### Mechanism:
1. **Registry Introspection:** On startup, the backend scans for `@domain_block` decorators and generates a `capabilities_registry.json`.
2. **Schema Reflection:** The Pydantic `input_schema` and `output_schema` are exported as JSON Schema.
3. **Canvas Palette:** Management sees categorised business blocks (**Finance**, **Compliance**, **Customer Care**). Dropping a block onto the canvas only allows connecting compatible inputs and outputs.

---

### Pillar 2: Hybrid Routing (DMN Decision Tables + Semantic Routing)

#### Problem Addressed
Eliminates arbitrary code expressions (e.g. `eval("x > 10")`) and unstructured LLM prompts ("Decide where to route").

#### Paradigm A: Deterministic DMN Decision Table
A spreadsheet-like matrix mapped directly to LangGraph `add_conditional_edges`.

* **Hit Policy:** `FIRST_MATCH` or `PRIORITY`.
* **Execution:** Safe AST-based evaluation (using Python's `ast` module or safe expression parser; zero arbitrary `eval`).

```yaml
type: dmn_table
id: invoice_routing_dmn
hit_policy: FIRST_MATCH
rules:
  - condition: "invoice.total_amount_usd > 50000 and compliance.risk_score >= 0.7"
    target_node: "cfo_emergency_review"
  - condition: "invoice.total_amount_usd > 10000"
    target_node: "finance_manager_review"
  - condition: "compliance.is_flagged == true"
    target_node: "compliance_l2_review"
  - default: "auto_disbursement_node"
```

#### Paradigm B: Semantic Intent Classifier
For natural language branching without hard-coded numbers.

```yaml
type: semantic_router
id: customer_inquiry_router
input_field: "customer_message.text"
routes:
  - id: billing_issue
    description: "Customer questions charges, refunds, disputed transactions, or invoices"
    target_node: "billing_agent_group"
  - id: technical_defect
    description: "Bug reports, system outages, 500 errors, or device connectivity issues"
    target_node: "tech_support_triage"
  - id: cancellation_churn
    description: "Requests to cancel subscription, close account, or switch to competitor"
    target_node: "retention_specialist_node"
```

* **Compilation:** Compiles into a LangGraph node that calls an LLM with structured output (`Pydantic` enum of the route IDs) using prompt caching and low temperature.

---

### Pillar 3: First-Class "Approval Inbox" (True Enterprise HITL)

#### Problem Addressed
LangGraph's `interrupt_before` is an engine primitive. Business enterprises need a human-in-the-loop task inbox with RBAC, dynamic forms, and SLA timers.

#### Mechanism:
1. **Node Definition:**
   ```yaml
   - id: l2_compliance_review
     type: human_review
     assigned_role: "role:compliance_officer"
     title: "High Risk Sanction Alert Review"
     form_schema: "compliance.review_submission"
     sla:
       duration_hours: 4
       on_breach:
         escalate_to_role: "role:chief_compliance_officer"
         route_target: "compliance_director_override"
   ```
2. **Execution & Interruption:**
   - The compiler wraps this step with `interrupt_before=["l2_compliance_review"]`.
   - When the graph reaches this checkpoint, execution pauses and an event is emitted: `TASK_PENDING_APPROVAL`.
3. **Approval Inbox UI:**
   - Members of `role:compliance_officer` see the pending item in their Task Inbox.
   - The UI auto-renders the current Pydantic state into read-only summary badges and an editable decision card (**Approve**, **Reject**, or **Edit & Approve**).
4. **Resolution Dispatch:**
   - Clicking **Approve** sends an authenticated API call to the backend.
   - The backend dispatches `graph.invoke(Command(resume={"action": "APPROVED", "reviewer": user.email}))`.
5. **SLA Watchdog:**
   - A background scheduler (e.g., Celery / APScheduler) checks pending approval timestamps against their SLA deadline. If breached, it automatically executes the escalation target edge.

---

### Pillar 4: Cost, Latency & Loop Guardrails as Visual Knobs

#### Problem Addressed
Cyclic agent interactions can run infinitely or consume excessive LLM tokens.

#### Guardrail Architecture:
Every cyclic loop or agent subgraph is wrapped with an **Interceptor Node**:

1. **Loop Iteration Counter:**
   - Injected into LangGraph state: `__sys_iteration_count: dict[str, int]`.
   - If iteration count exceeds `max_iterations`, routing forces the flow down the **Fallback Edge** (e.g., escalate to human or fail gracefully).
2. **Unit Economic Budget Cap:**
   - Each executed node accumulates token consumption and API cost: `__sys_total_cost_usd: float`.
   - If `total_cost > max_budget_usd`, execution halts immediately with `BUDGET_EXCEEDED` error status.
3. **Historical Overlay (Heatmap):**
   - Telemetry from production runs (stored in checkpointer/analytics DB) is aggregated per node.
   - When managers open the canvas, they toggle the **Heatmap Mode**:
     - 🔴 High cost nodes (e.g. > $0.05/run)
     - ⏱️ Latency bottlenecks (e.g. P95 > 5.2s)
     - 👤 High human rejection / override rates

---

### Pillar 5: "Shadow Mode" & Sandbox Simulation (Pre-Flight Testing)

#### Problem Addressed
Managers cannot evaluate the real-world impact of modifying a routing threshold or block connection without deploying to production.

#### Simulation Engine:
1. **Replay Dataset Selection:** Manager selects: *"Run against last 50 production cases from 'Invoice Processing'"*.
2. **State Rehydration:** Backend pulls historical initial states from the LangGraph checkpointer storage.
3. **Sandboxed Concurrent Run:** The candidate workflow topology runs in a mock/sandbox runtime. Real LLM calls can be replayed from cache or executed in dry-run mode; external write-tools are mocked or switched to sandboxed endpoints.
4. **Impact Diff Analysis:**
   - **Routing Shift:** `Auto-approved: 82% -> 74% (-8%)`, `Manual Review: 18% -> 26% (+8%)`
   - **Cost Delta:** `Avg Cost: $0.042 -> $0.035 (-16.6%)`
   - **Latency Delta:** `P95 Latency: 4.8s -> 3.9s`
   - **Schema Failures:** `0 errors detected`
5. **Report Presentation:** A visual diff report allows managers to proceed with confidence before clicking "Propose Change."

---

### Pillar 6: Git-Backed Governance Without Exposing Git

#### Problem Addressed
Proprietary visual builder databases break enterprise change management, SOC2 audit trails, and version rollback.

#### Governance Lifecycle:
1. **Declarative Storage:** The canvas is a direct projection of a human-readable `agent-bpmn.yaml` file.
2. **Change Proposal:** When a manager finishes canvas edits:
   - They click **"Propose Change"**.
   - A modal requires a **Business Reason** (e.g., *"Lowered L2 review threshold from $25k to $10k due to Q3 compliance policy update"*).
3. **Automated Git Flow (Backend-Driven):**
   - The backend checks out a new branch: `governance/wf-<id>-change-<timestamp>`.
   - Writes the updated `agent-bpmn.yaml`.
   - Opens a GitHub/GitLab Pull Request with auto-generated Markdown summary and simulation diff results.
   - Triggers automated CI regression tests.
4. **Deployment:** Once approved by designated engineering/management reviewers in GitHub or the AgentBPMN Admin Portal, the PR merges to `main` and production deploys via standard CI/CD.

---

## 4. Repository Structure & Monorepo Organization

```
lang-bpmn/
├── README.md
├── ARCHITECTURE_AND_PLAN.md
├── LICENSE
├── pyproject.toml
│
├── agent_bpmn/                     # Core Python Engine & SDK
│   ├── __init__.py
│   ├── sdk/                       # Developer SDK
│   │   ├── __init__.py
│   │   ├── decorator.py           # @domain_block decorator
│   │   ├── registry.py            # Capability registry & introspection
│   │   └── models.py              # Base schemas & metadata definitions
│   │
│   ├── dsl/                       # Declarative Spec & AST
│   │   ├── __init__.py
│   │   ├── schema.py              # Pydantic models for agent-bpmn.yaml
│   │   ├── parser.py              # YAML/JSON parser with validation
│   │   └── linter.py              # Graph topology validation (cycles, orphans)
│   │
│   ├── compiler/                  # LangGraph Compilation Engine
│   │   ├── __init__.py
│   │   ├── graph_compiler.py      # Transforms AST -> langgraph.graph.StateGraph
│   │   ├── dmn_compiler.py        # Compiles DMN tables into conditional edges
│   │   ├── semantic_compiler.py   # Compiles semantic routers into LLM classifiers
│   │   └── guardrail_injector.py  # Injects iteration counters & budget circuit breakers
│   │
│   ├── runtime/                   # Execution & HITL Services
│   │   ├── __init__.py
│   │   ├── engine.py              # LangGraph runner & checkpointer wrapper
│   │   ├── hitl_inbox.py          # Approval inbox service (interrupt/resume)
│   │   ├── sla_watchdog.py        # Background task for SLA escalations
│   │   └── telemetry.py           # Cost, latency & token usage tracker
│   │
│   ├── simulation/                # Pre-Flight Shadow Mode & Replay
│   │   ├── __init__.py
│   │   ├── replay_runner.py       # Replays historical states against candidate graph
│   │   └── diff_reporter.py       # Generates comparative impact metrics
│   │
│   ├── governance/                # Git & Enterprise Audit Bridge
│   │   ├── __init__.py
│   │   ├── git_client.py          # Branching, commits & PR creation
│   │   └── audit_logger.py        # Immutable audit records
│   │
│   └── api/                       # REST & WebSocket API
│       ├── __init__.py
│       ├── app.py                 # FastAPI application
│       └── routes/                # Canvas, Inbox, Execution, Governance endpoints
│
├── studio/                        # Frontend Web Canvas & Inbox (React + Vite)
│   ├── package.json
│   ├── src/
│   │   ├── components/
│   │   │   ├── canvas/            # React Flow / BPMN diagram canvas
│   │   │   ├── palette/           # Categorized Domain Block sidebar
│   │   │   ├── dmn/               # DMN Decision Table spreadsheet editor
│   │   │   ├── inbox/             # Enterprise Human Approval Inbox
│   │   │   ├── guardrails/        # Budget & SLA visual knobs
│   │   │   ├── simulation/        # Pre-flight diff report viewer
│   │   │   └── heatmap/           # Latency/Cost visual heatmap overlay
│   │   └── App.tsx
│
├── verify_domain_blocks.py        # Domain block verification & demo script
├── verify_workflow_compiler.py    # Declarative compiler verification script
├── verify_hybrid_routing.py       # Hybrid routing (DMN + Semantic) verification script
├── verify_approval_inbox.py       # Enterprise HITL & Approval Inbox verification script
├── verify_guardrails_and_heatmap.py # Guardrails & Process Heatmap verification script
├── verify_simulation_replay.py    # Shadow Mode & Pre-Flight Simulation verification script
├── verify_web_studio.py           # Web Studio & API Gateway verification script
├── verify_git_governance.py       # Git Governance & RBAC Security verification script
└── tests/                         # Comprehensive Test Suite
    ├── test_domain_block_sdk.py
    ├── test_workflow_compiler.py
    ├── test_hybrid_routing.py
    ├── test_approval_inbox.py
    ├── test_guardrails_and_heatmap.py
    ├── test_simulation_replay.py
    ├── test_server_api.py
    └── test_git_governance.py
```

---

## 5. Phased Implementation Roadmap

### Phase 1: SDK Foundation & Capability Registry
* [x] Implement `@domain_block` decorator with Pydantic type validation and metadata reflection.
* [x] Build registry scanner to discover and serialize capabilities into JSON Schema contracts.
* [x] Unit test block registration, schema validation, and execution isolation.

### Phase 2: Declarative Spec (DSL) & LangGraph Compiler
* [x] Define Pydantic schema for `agent-bpmn.yaml` (nodes, edges, guardrails, metadata).
* [x] Build graph linter (detect dead ends, disconnected nodes, unbound schemas).
* [x] Build `GraphCompiler` to transform declarative YAML AST into executable `langgraph.graph.StateGraph`.
* [x] Automated unit test suite (`tests/test_workflow_compiler.py`) passing 100%.
* [x] Verification runner (`verify_workflow_compiler.py`) demonstrated in visible terminal.

### Phase 3: Hybrid Routing (DMN Decision Tables + Semantic Enums)
* [x] Implement safe DMN expression evaluator supporting comparison, logical operators, and regex.
* [x] Wire DMN tables to LangGraph `add_conditional_edges()`.
* [x] Implement Semantic Intent Router synthesizer: automatically generates route classifiers.
* [x] Test complex conditional graphs with both deterministic and semantic forks.
* [x] Automated unit test suite (`tests/test_hybrid_routing.py`) passing 100%.
* [x] Verification runner (`verify_hybrid_routing.py`) demonstrated in visible terminal.

### Phase 4: Enterprise Human-in-the-Loop (HITL) Task Engine
* [x] Implement `HumanReviewNode` compiler integration using LangGraph interrupt checkpointing.
* [x] Build Task Inbox backend service with role-based filtering (`assigned_role`).
* [x] Implement dynamic resume command dispatcher (`Command(resume=...)`) supporting actions and state edits.
* [x] Build background SLA timer watchdog to handle automatic escalation on timeout.
* [x] Automated unit test suite (`tests/test_approval_inbox.py`) passing 100%.
* [x] Verification runner (`verify_approval_inbox.py`) demonstrated in visible terminal.

### Phase 5: Budget Guardrails & Operational Heatmap Telemetry
* [x] Inject iteration counter guardrails into cyclic loop edges (`max_loop_iterations` / `max_retries`).
* [x] Build token & USD cost tracking interceptor with hard circuit breakers (`BudgetExceededError`).
* [x] Create telemetry aggregation database models (P95 latency, average cost, rejection/override rate).
* [x] Automated unit test suite (`tests/test_guardrails_and_heatmap.py`) passing 100% (5/5 tests).
* [x] Verification runner (`verify_guardrails_and_heatmap.py`) demonstrated in visible terminal.

### Phase 6: Shadow Mode & Pre-Flight Replay Engine
* [x] Build checkpointer & historical telemetry dataset replayer to run $N$ production cases through modified ASTs.
* [x] Build sandboxed simulation executor preventing live side-effects during pre-flight evaluation.
* [x] Build impact diff calculator comparing route distribution shifts, financial cost deltas, and latency changes.
* [x] Automated unit test suite (`tests/test_simulation_replay.py`) passing 100% (6/6 tests).
* [x] Verification runner (`verify_simulation_replay.py`) demonstrated in visible terminal.

### Phase 7: Web Studio UI (React + React Flow / BPMN)
* [x] Scaffold React + Vite + Tailwind CSS frontend in `studio/`.
* [x] Build Domain Block drag-and-drop / click-to-add palette with Pydantic contract inspection.
* [x] Build DMN spreadsheet editor and Semantic Route card builder.
* [x] Build Human Review Task Inbox with dynamic Pydantic state preview and resume actions.
* [x] Build visual Process Intelligence Heatmap overlay toggle.
* [x] Build FastAPI Enterprise Gateway (`agent_bpmn/server/`) serving API endpoints and compiled SPA.
* [x] Automated unit test suite (`tests/test_server_api.py`) passing 100% (7/7 tests).
* [x] Verification runner (`verify_web_studio.py`) demonstrated in visible terminal.

### Phase 8: Git Governance & Enterprise Security
* [x] Build Git Governance client (branch creation, PR generation with simulation diffs, separation of duties).
* [x] Implement enterprise RBAC identity service with Okta / OIDC role claims (`UserPrincipal`).
* [x] Build tamper-evident cryptographic audit ledger with SHA-256 hash chaining (SOC2 compliant).
* [x] Automated unit test suite (`tests/test_git_governance.py`) passing 100% (5/5 tests).
* [x] Verification runner (`verify_git_governance.py`) demonstrated in visible terminal.

---

## 6. Verification & Acceptance Criteria

| Capability | Target Milestone | Acceptance Criteria |
| :--- | :--- | :--- |
| **Domain Blocks** | Phase 1 | Python functions decorated with `@domain_block` export clean JSON Schemas without leaking prompt code. |
| **Graph Compilation** | Phase 2 | A 5-node `agent-bpmn.yaml` compiles and runs via LangGraph `StateGraph.invoke()`. |
| **DMN Decision Tables** | Phase 3 | Multi-condition table routes execution deterministically without arbitrary Python `eval`. |
| **HITL Approval Inbox** | Phase 4 | Graph pauses on human node; inbox displays state; user approval resumes execution cleanly via `Command(resume=...)`. |
| **Loop Guardrails** | Phase 5 | Cyclic loop terminates at `max_iterations = 3` and executes fallback escalation edge without hanging. |
| **Pre-Flight Simulation** | Phase 6 | Running 50 historical inputs against a modified workflow generates a complete metric diff report. |
| **Git Governance** | Phase 8 | Clicking "Propose Change" opens a valid GitHub Pull Request containing clean `agent-bpmn.yaml`. |

