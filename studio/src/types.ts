export interface DomainBlockMetadata {
  id: string;
  name: string;
  department: string;
  description: string;
  icon?: string;
  estimated_cost_usd: number;
  p95_latency_ms: number;
  tags: string[];
}

export interface DomainBlockContract {
  metadata: DomainBlockMetadata;
  input_schema: Record<string, any>;
  output_schema: Record<string, any>;
}

export interface CapabilityCatalog {
  total_blocks: number;
  departments: Record<string, DomainBlockContract[]>;
}

export interface DMNRule {
  condition?: string;
  target: string;
  description?: string;
}

export interface DMNTableConfig {
  hit_policy: 'FIRST_MATCH' | 'RULE_ORDER';
  rules: DMNRule[];
  default_target?: string;
}

export interface HumanReviewConfig {
  assigned_role: string;
  title: string;
  description?: string;
  sla_timeout_seconds: number;
  allowed_actions: string[];
  escalation_target?: string;
  form_fields?: Record<string, any>;
}

export interface WorkflowNode {
  id: string;
  type: 'start' | 'end' | 'block' | 'dmn_table' | 'semantic_router' | 'human_review';
  name?: string;
  block?: string;
  max_retries?: number;
  dmn_config?: DMNTableConfig;
  human_review_config?: HumanReviewConfig;
  input_mapping?: Record<string, any>;
  output_mapping?: Record<string, any>;
}

export interface WorkflowEdge {
  source: string;
  target: string;
  condition?: string;
  is_loop_back?: boolean;
}

export interface WorkflowGuardrails {
  max_total_budget_usd?: number;
  workflow_timeout_seconds?: number;
  max_loop_iterations?: number;
}

export interface WorkflowMetadata {
  id: string;
  name: string;
  version: string;
  description?: string;
  owner_department?: string;
}

export interface WorkflowDefinition {
  version: string;
  metadata: WorkflowMetadata;
  guardrails: WorkflowGuardrails;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
}

export interface ApprovalTask {
  task_id: string;
  thread_id: string;
  workflow_id: string;
  node_id: string;
  title: string;
  assigned_role: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'OVERDUE' | 'ESCALATED';
  state_snapshot: Record<string, any>;
  allowed_actions: string[];
  created_at: string;
  sla_deadline: string;
  description?: string;
}

export interface NodeHeatmapMetric {
  node_id: string;
  call_count: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  avg_cost_usd: number;
  human_override_rate: number;
  bottleneck_level: 'NORMAL' | 'WARNING' | 'CRITICAL';
}

export interface WorkflowHeatmap {
  workflow_id: string;
  total_runs: number;
  total_cost_usd: number;
  avg_run_cost_usd: number;
  node_metrics: Record<string, NodeHeatmapMetric>;
}

export interface RouteShiftMetric {
  node_id: string;
  baseline_count: number;
  candidate_count: number;
  baseline_pct: number;
  candidate_pct: number;
  shift_pct_points: number;
}

export interface SimulationImpactDiff {
  total_cases: number;
  candidate_success_count: number;
  candidate_failure_count: number;
  candidate_guardrail_trip_count: number;
  candidate_success_rate: number;
  route_shifts: Record<string, RouteShiftMetric>;
  baseline_avg_cost_usd: number;
  candidate_avg_cost_usd: number;
  cost_delta_usd: number;
  cost_delta_pct: number;
  baseline_avg_latency_ms: number;
  candidate_avg_latency_ms: number;
  latency_delta_ms: number;
  latency_delta_pct: number;
  schema_failures: number;
  critical_findings: string[];
}

export interface SimulationReport {
  simulation_id: string;
  baseline_workflow_id: string;
  candidate_workflow_id: string;
  candidate_version: string;
  diff: SimulationImpactDiff;
  markdown_report: string;
}

