import {
  ApprovalTask,
  CapabilityCatalog,
  SimulationReport,
  WorkflowDefinition,
  WorkflowHeatmap,
} from './types';

const API_BASE = '/api';

export async function fetchCapabilitiesCatalog(): Promise<CapabilityCatalog> {
  try {
    const res = await fetch(`${API_BASE}/capabilities`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    // Fallback catalog for standalone demo / offline preview
    return {
      total_blocks: 4,
      departments: {
        'Finance Operations': [
          {
            metadata: {
              id: 'finance.invoice_extractor',
              name: 'Extract Invoice Line Items',
              department: 'Finance Operations',
              description: 'Multimodal vision model parsing invoices, calculating line-item sums and vendor details.',
              estimated_cost_usd: 0.015,
              p95_latency_ms: 1800,
              tags: ['finance', 'pdf', 'ocr'],
            },
            input_schema: { type: 'object', properties: { document_url: { type: 'string' }, vendor_tax_id: { type: 'string' } } },
            output_schema: { type: 'object', properties: { invoice_number: { type: 'string' }, total_amount_usd: { type: 'number' } } },
          },
          {
            metadata: {
              id: 'finance.auto_settlement',
              name: 'Automated Payment Settlement',
              department: 'Finance Operations',
              description: 'Integrates with corporate ERP / banking rails to disburse funds for approved accounts payable.',
              estimated_cost_usd: 0.005,
              p95_latency_ms: 650,
              tags: ['finance', 'erp', 'banking'],
            },
            input_schema: { type: 'object', properties: { invoice_number: { type: 'string' }, amount_usd: { type: 'number' } } },
            output_schema: { type: 'object', properties: { transaction_id: { type: 'string' }, status: { type: 'string' } } },
          },
        ],
        'Regulatory Compliance': [
          {
            metadata: {
              id: 'compliance.sanctions_screener',
              name: 'Screen Against Sanctions List',
              department: 'Regulatory Compliance',
              description: 'Cross-references counterparties against OFAC, EU, UN, and PEP international watchlists.',
              estimated_cost_usd: 0.004,
              p95_latency_ms: 1200,
              tags: ['compliance', 'ofac', 'aml'],
            },
            input_schema: { type: 'object', properties: { entity_name: { type: 'string' }, country_code: { type: 'string' } } },
            output_schema: { type: 'object', properties: { is_flagged: { type: 'boolean' }, risk_score: { type: 'number' } } },
          },
          {
            metadata: {
              id: 'compliance.emergency_review',
              name: 'L2 Sanctions Investigation',
              department: 'Regulatory Compliance',
              description: 'Generates detailed evidence docket for sanctions hits and alerts Senior Compliance Officer.',
              estimated_cost_usd: 0.012,
              p95_latency_ms: 2400,
              tags: ['compliance', 'investigation'],
            },
            input_schema: { type: 'object', properties: { entity_name: { type: 'string' }, risk_score: { type: 'number' } } },
            output_schema: { type: 'object', properties: { case_docket_id: { type: 'string' }, status: { type: 'string' } } },
          },
        ],
      },
    };
  }
}

export async function fetchWorkflowsList(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE}/workflows`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    return [
      {
        file_name: 'hybrid_routing_workflow.yaml',
        metadata: { id: 'hybrid_invoice_routing_flow', name: 'Enterprise Hybrid Invoice Routing (DMN Table)', version: '1.2.0' },
        node_count: 5,
        edge_count: 5,
      },
      {
        file_name: 'enterprise_hitl_workflow.yaml',
        metadata: { id: 'executive_hitl_invoicing_flow', name: 'Executive Approval Workflow (LangGraph Interrupt)', version: '2.0.0' },
        node_count: 4,
        edge_count: 4,
      },
    ];
  }
}

export async function fetchWorkflowDetail(fileName: string): Promise<{ yaml_content: string; ast: WorkflowDefinition }> {
  const res = await fetch(`${API_BASE}/workflows/${fileName}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function createWorkflow(payload: {
  name: string;
  workflow_id?: string;
  department?: string;
  description?: string;
  template?: string;
  yaml_content?: string;
  max_budget_usd?: number;
  max_loop_iterations?: number;
  workflow_timeout_seconds?: number;
}): Promise<{ file_name: string; workflow_id: string; yaml_content: string; ast: WorkflowDefinition; message: string }> {
  const res = await fetch(`${API_BASE}/workflows`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to create workflow' }));
    throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
  }
  return await res.json();
}

export async function updateWorkflow(
  fileName: string,
  payload: { yaml_content?: string; ast?: Partial<WorkflowDefinition> }
): Promise<{ file_name: string; workflow_id: string; yaml_content: string; ast: WorkflowDefinition; message: string }> {
  const res = await fetch(`${API_BASE}/workflows/${fileName}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to update workflow' }));
    throw new Error(typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail));
  }
  return await res.json();
}

export async function deleteWorkflow(fileName: string): Promise<{ message: string; file_name: string }> {
  const res = await fetch(`${API_BASE}/workflows/${fileName}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function executeWorkflow(payload: {
  workflow_yaml?: string;
  workflow_id?: string;
  input_payload: Record<string, any>;
}): Promise<{
  status: 'COMPLETED' | 'INTERRUPTED' | 'FAILED';
  final_state: Record<string, any>;
  history: string[];
  total_cost_usd: number;
  telemetry: Record<string, any>;
  error_type?: string;
  error_message?: string;
}> {
  const res = await fetch(`${API_BASE}/workflows/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function lintWorkflow(yamlContent: string): Promise<{
  is_valid: boolean;
  errors: string[];
  warnings: string[];
  workflow_id?: string;
}> {
  const res = await fetch(`${API_BASE}/workflows/lint`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ yaml_content: yamlContent }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function fetchHeatmap(workflowId: string): Promise<WorkflowHeatmap> {
  try {
    const res = await fetch(`${API_BASE}/telemetry/heatmaps/${workflowId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    return {
      workflow_id: workflowId,
      total_runs: 12,
      total_cost_usd: 0.228,
      avg_run_cost_usd: 0.019,
      node_metrics: {
        extract_invoice: { node_id: 'extract_invoice', call_count: 12, avg_latency_ms: 450, p95_latency_ms: 2100, avg_cost_usd: 0.015, human_override_rate: 0, bottleneck_level: 'WARNING' },
        screen_sanctions: { node_id: 'screen_sanctions', call_count: 12, avg_latency_ms: 55, p95_latency_ms: 70, avg_cost_usd: 0.004, human_override_rate: 0, bottleneck_level: 'NORMAL' },
        emergency_compliance_review: { node_id: 'emergency_compliance_review', call_count: 4, avg_latency_ms: 1850, p95_latency_ms: 2800, avg_cost_usd: 0.012, human_override_rate: 0.5, bottleneck_level: 'CRITICAL' },
      },
    };
  }
}

export async function fetchInboxTasks(): Promise<ApprovalTask[]> {
  try {
    const res = await fetch(`${API_BASE}/inbox/tasks`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    return [
      {
        task_id: 'task_demo_8819',
        thread_id: 'thread_run_9821',
        workflow_id: 'executive_hitl_invoicing_flow',
        node_id: 'cfo_approval_node',
        title: 'High-Value Invoice Approval ($14,500.00 USD)',
        assigned_role: 'role:finance_executive',
        status: 'PENDING',
        state_snapshot: {
          invoice_number: 'INV-2026-9812',
          vendor_name: 'Apex Cloud Infrastructure Ltd',
          invoice_total_usd: 14500.0,
          sanctions_is_flagged: false,
          sanctions_risk_score: 0.05,
        },
        allowed_actions: ['APPROVE', 'REJECT', 'EDIT_AND_APPROVE'],
        created_at: new Date().toISOString(),
        sla_deadline: new Date(Date.now() + 4 * 3600 * 1000).toISOString(),
        description: 'Invoice exceeds automated payment limit of $10,000. Executive sign-off required.',
      },
    ];
  }
}

export async function resolveTask(taskId: string, action: string, comments?: string, updatedFields?: Record<string, any>) {
  const res = await fetch(`${API_BASE}/inbox/tasks/${taskId}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, comments, updated_fields: updatedFields }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function runPreflightSimulation(candidateYaml: string): Promise<SimulationReport> {
  const res = await fetch(`${API_BASE}/simulation/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ candidate_workflow_yaml: candidateYaml, sample_size: 15 }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

