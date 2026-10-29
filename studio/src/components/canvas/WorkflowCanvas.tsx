import React, { useState } from 'react';
import {
  AlertOctagon,
  ArrowRight,
  Bot,
  CheckCircle,
  Clock,
  CornerDownRight,
  DollarSign,
  Flame,
  GitBranch,
  Layers,
  Play,
  RotateCcw,
  Sliders,
  Sparkles,
  StopCircle,
  Table,
  UserCheck,
  XCircle,
} from 'lucide-react';
import { WorkflowDefinition, WorkflowHeatmap, WorkflowNode } from '../../types';

interface WorkflowCanvasProps {
  workflow: WorkflowDefinition;
  onUpdateWorkflow: (updated: WorkflowDefinition) => void;
  heatmapEnabled: boolean;
  heatmap?: WorkflowHeatmap;
  onOpenDMNEditor: (nodeId: string) => void;
}

export const WorkflowCanvas: React.FC<WorkflowCanvasProps> = ({
  workflow,
  onUpdateWorkflow,
  heatmapEnabled,
  heatmap,
  onOpenDMNEditor,
}) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const selectedNode = workflow.nodes.find((n) => n.id === selectedNodeId);

  const getNodeIcon = (type: string) => {
    switch (type) {
      case 'start':
        return <Play className="w-4 h-4 text-emerald-400 fill-emerald-400" />;
      case 'end':
        return <StopCircle className="w-4 h-4 text-rose-400 fill-rose-400" />;
      case 'block':
        return <Bot className="w-4 h-4 text-cyan-400" />;
      case 'dmn_table':
        return <Table className="w-4 h-4 text-purple-400" />;
      case 'semantic_router':
        return <Sparkles className="w-4 h-4 text-amber-400" />;
      case 'human_review':
        return <UserCheck className="w-4 h-4 text-orange-400" />;
      default:
        return <Layers className="w-4 h-4 text-slate-400" />;
    }
  };

  const getHeatmapColor = (nodeId: string) => {
    if (!heatmapEnabled || !heatmap) return 'border-slate-800 bg-slate-900/90';
    const metric = heatmap.node_metrics[nodeId];
    if (!metric) return 'border-slate-800 bg-slate-900/90';

    switch (metric.bottleneck_level) {
      case 'CRITICAL':
        return 'border-rose-500 bg-rose-950/40 shadow-lg shadow-rose-950/60 ring-2 ring-rose-500/50';
      case 'WARNING':
        return 'border-amber-500 bg-amber-950/40 shadow-lg shadow-amber-950/60 ring-2 ring-amber-500/40';
      case 'NORMAL':
        return 'border-emerald-500 bg-emerald-950/30 ring-1 ring-emerald-500/30';
      default:
        return 'border-slate-800 bg-slate-900/90';
    }
  };

  return (
    <div className="flex-1 flex h-[calc(100vh-4rem)] bg-slate-950 relative overflow-hidden select-none">
      {/* Background Dot Grid */}
      <div
        className="absolute inset-0 opacity-20 pointer-events-none"
        style={{
          backgroundImage: 'radial-gradient(#475569 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />

      {/* Canvas Workspace */}
      <div className="flex-1 overflow-auto p-12 flex flex-col items-center">
        {/* Guardrail Status Bar */}
        <div className="w-full max-w-4xl bg-slate-900/80 backdrop-blur border border-slate-800 rounded-xl px-5 py-3 mb-10 flex items-center justify-between shadow-xl">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold text-white uppercase tracking-wider">Visual Guardrails</span>
            </div>
            <div className="flex items-center gap-4 text-xs font-mono">
              <span className="flex items-center gap-1.5 text-slate-300">
                <span className="text-slate-500">Max Spend:</span>
                <span className="text-emerald-400 font-semibold">${workflow.guardrails?.max_total_budget_usd ?? 0.25} USD</span>
              </span>
              <span className="flex items-center gap-1.5 text-slate-300">
                <span className="text-slate-500">Loop Bounds:</span>
                <span className="text-purple-400 font-semibold">{workflow.guardrails?.max_loop_iterations ?? 3} retries</span>
              </span>
              <span className="flex items-center gap-1.5 text-slate-300">
                <span className="text-slate-500">Timeout:</span>
                <span className="text-amber-400 font-semibold">{workflow.guardrails?.workflow_timeout_seconds ?? 600}s</span>
              </span>
            </div>
          </div>

          {heatmapEnabled && heatmap && (
            <div className="flex items-center gap-3 text-xs bg-rose-950/60 border border-rose-800/80 px-3 py-1 rounded-md text-rose-300 font-medium">
              <Flame className="w-3.5 h-3.5 text-rose-400 fill-rose-400" />
              <span>Optimize Overlay: <strong>{heatmap.total_runs}</strong> traces analyzed</span>
              <span className="text-rose-400 font-mono">Avg Spend: ${heatmap.avg_run_cost_usd.toFixed(4)}</span>
            </div>
          )}
        </div>

        {/* Nodes DAG Pipeline */}
        <div className="flex flex-col items-center gap-4 w-full max-w-3xl">
          {/* Start Node */}
          <div className="w-12 h-12 rounded-full bg-emerald-950/80 border-2 border-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Play className="w-5 h-5 text-emerald-400 fill-emerald-400 ml-0.5" />
          </div>
          <ArrowRight className="w-4 h-4 text-slate-600 rotate-90" />

          {/* Workflow Graph Nodes */}
          {workflow.nodes.map((node, idx) => {
            const isSelected = selectedNodeId === node.id;
            const metric = heatmap?.node_metrics[node.id];

            return (
              <React.Fragment key={node.id}>
                <div
                  onClick={() => setSelectedNodeId(node.id)}
                  className={`w-full max-w-md rounded-xl p-4 cursor-pointer transition-all border ${getHeatmapColor(
                    node.id
                  )} ${isSelected ? 'ring-2 ring-cyan-400 shadow-xl shadow-cyan-950/50' : 'hover:border-slate-700'}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <div className="p-2 rounded-lg bg-slate-800/80 border border-slate-700">
                        {getNodeIcon(node.type)}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] uppercase font-bold text-cyan-400 tracking-wider">
                            {node.type.replace('_', ' ')}
                          </span>
                          {node.max_retries && (
                            <span className="text-[9px] bg-purple-950 text-purple-300 px-1.5 py-0.2 rounded border border-purple-800">
                              max {node.max_retries} retries
                            </span>
                          )}
                        </div>
                        <h4 className="text-sm font-bold text-white mt-0.5">{node.name || node.id}</h4>
                        <code className="text-[10px] font-mono text-slate-400">{node.id}</code>
                      </div>
                    </div>

                    {/* DMN or Review Action Trigger */}
                    {node.type === 'dmn_table' && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenDMNEditor(node.id);
                        }}
                        className="px-2.5 py-1 rounded bg-purple-900/60 hover:bg-purple-800 text-purple-200 text-xs font-semibold flex items-center gap-1 border border-purple-700 transition-colors"
                      >
                        <Table className="w-3 h-3" />
                        Edit Rules
                      </button>
                    )}

                    {node.type === 'human_review' && (
                      <span className="px-2 py-0.5 rounded bg-orange-950 text-orange-400 border border-orange-800 text-[10px] font-mono">
                        {node.human_review_config?.assigned_role || 'role:operator'}
                      </span>
                    )}
                  </div>

                  {/* Heatmap Metrics Overlay Pill */}
                  {heatmapEnabled && metric && (
                    <div className="mt-3 pt-2.5 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono">
                      <div className="flex items-center gap-3">
                        <span className="text-slate-300 flex items-center gap-1">
                          <Clock className="w-3 h-3 text-amber-400" />
                          {metric.avg_latency_ms.toFixed(0)}ms (P95: {metric.p95_latency_ms.toFixed(0)}ms)
                        </span>
                        <span className="text-slate-300 flex items-center gap-1">
                          <DollarSign className="w-3 h-3 text-emerald-400" />
                          ${metric.avg_cost_usd.toFixed(4)}
                        </span>
                      </div>
                      <span
                        className={`text-[9px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider ${
                          metric.bottleneck_level === 'CRITICAL'
                            ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                            : metric.bottleneck_level === 'WARNING'
                            ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                            : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                        }`}
                      >
                        {metric.bottleneck_level}
                      </span>
                    </div>
                  )}
                </div>

                {/* Connecting Edge Indicator */}
                {idx < workflow.nodes.length - 1 && (
                  <ArrowRight className="w-4 h-4 text-slate-600 rotate-90 my-0.5" />
                )}
              </React.Fragment>
            );
          })}

          <ArrowRight className="w-4 h-4 text-slate-600 rotate-90" />
          {/* End Node */}
          <div className="w-12 h-12 rounded-full bg-rose-950/80 border-2 border-rose-500 flex items-center justify-center shadow-lg shadow-rose-500/20">
            <StopCircle className="w-5 h-5 text-rose-400 fill-rose-400" />
          </div>
        </div>
      </div>

      {/* Right Properties Drawer */}
      {selectedNode && (
        <aside className="w-84 bg-slate-900 border-l border-slate-800 p-5 flex flex-col h-full shadow-2xl overflow-y-auto">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div>
              <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider">Node Inspector</span>
              <h3 className="text-sm font-bold text-white">{selectedNode.name || selectedNode.id}</h3>
            </div>
            <button
              onClick={() => setSelectedNodeId(null)}
              className="text-slate-400 hover:text-white text-xs px-2 py-1 rounded bg-slate-800"
            >
              ✕
            </button>
          </div>

          <div className="mt-4 space-y-4 text-xs">
            <div>
              <label className="text-slate-400 block mb-1 font-medium">Node ID</label>
              <input
                type="text"
                disabled
                value={selectedNode.id}
                className="w-full bg-slate-950 font-mono text-slate-300 p-2 rounded border border-slate-800"
              />
            </div>

            <div>
              <label className="text-slate-400 block mb-1 font-medium">Display Name</label>
              <input
                type="text"
                value={selectedNode.name || ''}
                onChange={(e) => {
                  const updatedNodes = workflow.nodes.map((n) =>
                    n.id === selectedNode.id ? { ...n, name: e.target.value } : n
                  );
                  onUpdateWorkflow({ ...workflow, nodes: updatedNodes });
                }}
                className="w-full bg-slate-950 text-slate-200 p-2 rounded border border-slate-800 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {selectedNode.block && (
              <div>
                <label className="text-slate-400 block mb-1 font-medium">Bound Domain Block</label>
                <div className="bg-slate-950 p-2 rounded border border-slate-800 font-mono text-cyan-400">
                  {selectedNode.block}
                </div>
              </div>
            )}

            <div>
              <label className="text-slate-400 block mb-1 font-medium">Loop Retry Cap (Circuit Breaker)</label>
              <input
                type="number"
                min={1}
                max={10}
                value={selectedNode.max_retries ?? 3}
                onChange={(e) => {
                  const val = parseInt(e.target.value) || 3;
                  const updatedNodes = workflow.nodes.map((n) =>
                    n.id === selectedNode.id ? { ...n, max_retries: val } : n
                  );
                  onUpdateWorkflow({ ...workflow, nodes: updatedNodes });
                }}
                className="w-full bg-slate-950 font-mono text-slate-200 p-2 rounded border border-slate-800 focus:outline-none focus:border-cyan-500"
              />
            </div>

            {selectedNode.input_mapping && (
              <div>
                <label className="text-slate-400 block mb-1 font-medium">Input Mappings</label>
                <pre className="bg-slate-950 p-2.5 rounded font-mono text-[10px] text-slate-300 border border-slate-800 overflow-x-auto">
                  {JSON.stringify(selectedNode.input_mapping, null, 2)}
                </pre>
              </div>
            )}

            {selectedNode.output_mapping && (
              <div>
                <label className="text-slate-400 block mb-1 font-medium">Output Mappings</label>
                <pre className="bg-slate-950 p-2.5 rounded font-mono text-[10px] text-emerald-400 border border-slate-800 overflow-x-auto">
                  {JSON.stringify(selectedNode.output_mapping, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </aside>
      )}
    </div>
  );
};

