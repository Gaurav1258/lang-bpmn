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
  Plus,
  RotateCcw,
  Sliders,
  Sparkles,
  StopCircle,
  Table,
  Trash2,
  UserCheck,
  XCircle,
} from 'lucide-react';
import {
  CapabilityCatalog,
  WorkflowDefinition,
  WorkflowEdge,
  WorkflowHeatmap,
  WorkflowNode,
} from '../../types';

interface WorkflowCanvasProps {
  workflow: WorkflowDefinition;
  onUpdateWorkflow: (updated: WorkflowDefinition) => void;
  catalog: CapabilityCatalog;
  heatmapEnabled: boolean;
  heatmap?: WorkflowHeatmap;
  onOpenDMNEditor: (nodeId: string) => void;
}

export const WorkflowCanvas: React.FC<WorkflowCanvasProps> = ({
  workflow,
  onUpdateWorkflow,
  catalog,
  heatmapEnabled,
  heatmap,
  onOpenDMNEditor,
}) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const selectedNode = workflow.nodes.find((n) => n.id === selectedNodeId);

  // Collect flat list of all registered domain blocks from catalog
  const availableBlocks = Object.entries(catalog.departments || {}).flatMap(
    ([dept, blocks]) => blocks.map((b) => ({ ...b, departmentName: dept }))
  );

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

  const handleDeleteNode = (nodeId: string) => {
    const incoming = workflow.edges.filter((e) => e.target === nodeId);
    const outgoing = workflow.edges.filter((e) => e.source === nodeId);

    const newEdges: WorkflowEdge[] = [];
    workflow.edges.forEach((e) => {
      if (e.source !== nodeId && e.target !== nodeId) {
        newEdges.push(e);
      }
    });

    // Re-link incoming directly to outgoing
    incoming.forEach((inEdge) => {
      outgoing.forEach((outEdge) => {
        if (
          inEdge.source !== outEdge.target &&
          !newEdges.some((e) => e.source === inEdge.source && e.target === outEdge.target)
        ) {
          newEdges.push({
            source: inEdge.source,
            target: outEdge.target,
            condition: outEdge.condition || inEdge.condition,
          });
        }
      });
    });

    const updatedNodes = workflow.nodes.filter((n) => n.id !== nodeId);
    if (selectedNodeId === nodeId) {
      setSelectedNodeId(null);
    }

    onUpdateWorkflow({
      ...workflow,
      nodes: updatedNodes,
      edges: newEdges,
    });
  };

  const handleAddNode = (type: 'block' | 'dmn_table' | 'human_review', blockId?: string) => {
    const ts = Date.now().toString().slice(-4);
    let newNode: WorkflowNode;
    const lastNode = workflow.nodes.length > 0 ? workflow.nodes[workflow.nodes.length - 1] : null;

    if (type === 'block') {
      const defaultBlock = blockId || availableBlocks[0]?.metadata.id || 'finance.invoice_extractor';
      const blockMeta = availableBlocks.find((b) => b.metadata.id === defaultBlock);
      newNode = {
        id: `step_${ts}`,
        type: 'block',
        name: blockMeta?.metadata.name || 'AI Task',
        block: defaultBlock,
        input_mapping: {},
        output_mapping: {},
        max_retries: 3,
      };
    } else if (type === 'dmn_table') {
      newNode = {
        id: `dmn_${ts}`,
        type: 'dmn_table',
        name: 'DMN Business Rules Table',
        dmn_config: {
          hit_policy: 'FIRST_MATCH',
          rules: [{ condition: 'true', target: 'END', description: 'Default fallback' }],
          default_target: 'END',
        },
      };
    } else {
      newNode = {
        id: `review_${ts}`,
        type: 'human_review',
        name: 'Human Review Checkpoint',
        human_review_config: {
          assigned_role: 'role:finance_executive',
          title: 'Executive Approval Request',
          sla_timeout_seconds: 14400,
          allowed_actions: ['APPROVE', 'REJECT', 'EDIT_AND_APPROVE'],
        },
      };
    }

    const updatedNodes = [...workflow.nodes, newNode];
    const updatedEdges = [...workflow.edges];

    // Reconnect edges
    const endEdgeIdx = updatedEdges.findIndex((e) => e.target === 'END');
    if (endEdgeIdx !== -1) {
      const prevSource = updatedEdges[endEdgeIdx].source;
      updatedEdges.splice(endEdgeIdx, 1);
      updatedEdges.push({ source: prevSource, target: newNode.id });
      updatedEdges.push({ source: newNode.id, target: 'END' });
    } else {
      updatedEdges.push({ source: lastNode ? lastNode.id : 'START', target: newNode.id });
      updatedEdges.push({ source: newNode.id, target: 'END' });
    }

    onUpdateWorkflow({
      ...workflow,
      nodes: updatedNodes,
      edges: updatedEdges,
    });
    setSelectedNodeId(newNode.id);
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
      <div className="flex-1 overflow-auto p-8 flex flex-col items-center">
        {/* Top BPMN Modeler Toolbar */}
        <div className="w-full max-w-4xl bg-slate-900/90 backdrop-blur border border-slate-800 rounded-xl px-5 py-3 mb-6 flex items-center justify-between shadow-xl">
          <div className="flex items-center gap-3">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Plus className="w-3.5 h-3.5 text-cyan-400" />
              Add BPMN Element:
            </span>
            <button
              onClick={() => handleAddNode('block')}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-cyan-950/80 hover:bg-cyan-900 text-cyan-300 border border-cyan-800/80 transition-colors"
            >
              <Bot className="w-3.5 h-3.5" />
              AI Service Task
            </button>
            <button
              onClick={() => handleAddNode('dmn_table')}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-purple-950/80 hover:bg-purple-900 text-purple-300 border border-purple-800/80 transition-colors"
            >
              <Table className="w-3.5 h-3.5" />
              DMN Decision Table
            </button>
            <button
              onClick={() => handleAddNode('human_review')}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-orange-950/80 hover:bg-orange-900 text-orange-300 border border-orange-800/80 transition-colors"
            >
              <UserCheck className="w-3.5 h-3.5" />
              User Task (HITL)
            </button>
          </div>

          {/* Quick Guardrail Summary */}
          <div className="flex items-center gap-4 text-xs font-mono">
            <span className="text-slate-400">
              Budget:{' '}
              <span className="text-emerald-400 font-bold">${workflow.guardrails?.max_total_budget_usd ?? 0.5}</span>
            </span>
            <span className="text-slate-400">
              Retries:{' '}
              <span className="text-purple-400 font-bold">{workflow.guardrails?.max_loop_iterations ?? 3}</span>
            </span>
          </div>
        </div>

        {/* Nodes DAG Pipeline */}
        <div className="flex flex-col items-center gap-4 w-full max-w-3xl pb-16">
          {/* Start Event */}
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 rounded-full bg-emerald-950/80 border-2 border-emerald-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <Play className="w-5 h-5 text-emerald-400 fill-emerald-400 ml-0.5" />
            </div>
            <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mt-1">Start Event</span>
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
                  className={`w-full max-w-md rounded-xl p-4 cursor-pointer transition-all border group relative ${getHeatmapColor(
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

                    <div className="flex items-center gap-2">
                      {/* DMN Edit rules trigger */}
                      {node.type === 'dmn_table' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenDMNEditor(node.id);
                          }}
                          className="px-2.5 py-1 rounded bg-purple-900/60 hover:bg-purple-800 text-purple-200 text-xs font-semibold flex items-center gap-1 border border-purple-700 transition-colors"
                        >
                          <Table className="w-3 h-3" />
                          Rules
                        </button>
                      )}

                      {/* Human Review role badge */}
                      {node.type === 'human_review' && (
                        <span className="px-2 py-0.5 rounded bg-orange-950 text-orange-400 border border-orange-800 text-[10px] font-mono">
                          {node.human_review_config?.assigned_role || 'role:operator'}
                        </span>
                      )}

                      {/* Delete node quick action */}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteNode(node.id);
                        }}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-rose-950 text-slate-500 hover:text-rose-400 transition-all"
                        title="Delete this node"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Heatmap Metrics Overlay */}
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

                {/* Connecting Edge */}
                {idx < workflow.nodes.length - 1 && (
                  <ArrowRight className="w-4 h-4 text-slate-600 rotate-90 my-0.5" />
                )}
              </React.Fragment>
            );
          })}

          <ArrowRight className="w-4 h-4 text-slate-600 rotate-90" />
          {/* End Event */}
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 rounded-full bg-rose-950/80 border-2 border-rose-500 flex items-center justify-center shadow-lg shadow-rose-500/20">
              <StopCircle className="w-5 h-5 text-rose-400 fill-rose-400" />
            </div>
            <span className="text-[10px] font-bold text-rose-400 uppercase tracking-wider mt-1">End Event</span>
          </div>
        </div>
      </div>

      {/* Right Properties Panel / Inspector (Camunda Modeler Style) */}
      {selectedNode && (
        <aside className="w-88 bg-slate-900 border-l border-slate-800 p-5 flex flex-col h-full shadow-2xl overflow-y-auto">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div>
              <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-wider">Properties Panel</span>
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
                value={selectedNode.id}
                onChange={(e) => {
                  const newId = e.target.value;
                  const oldId = selectedNode.id;
                  const updatedNodes = workflow.nodes.map((n) => (n.id === oldId ? { ...n, id: newId } : n));
                  const updatedEdges = workflow.edges.map((edge) => ({
                    ...edge,
                    source: edge.source === oldId ? newId : edge.source,
                    target: edge.target === oldId ? newId : edge.target,
                  }));
                  onUpdateWorkflow({ ...workflow, nodes: updatedNodes, edges: updatedEdges });
                  setSelectedNodeId(newId);
                }}
                className="w-full bg-slate-950 font-mono text-cyan-300 p-2 rounded border border-slate-800 focus:outline-none focus:border-cyan-500"
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

            {/* Block selector for AI Task */}
            {selectedNode.type === 'block' && (
              <div>
                <label className="text-slate-400 block mb-1 font-medium">Domain Capability Block</label>
                <select
                  value={selectedNode.block || ''}
                  onChange={(e) => {
                    const chosenId = e.target.value;
                    const meta = availableBlocks.find((b) => b.metadata.id === chosenId);
                    const updatedNodes = workflow.nodes.map((n) =>
                      n.id === selectedNode.id
                        ? { ...n, block: chosenId, name: meta ? meta.metadata.name : n.name }
                        : n
                    );
                    onUpdateWorkflow({ ...workflow, nodes: updatedNodes });
                  }}
                  className="w-full bg-slate-950 text-cyan-400 p-2 rounded border border-slate-800 focus:outline-none focus:border-cyan-500"
                >
                  {availableBlocks.map((b) => (
                    <option key={b.metadata.id} value={b.metadata.id}>
                      {b.metadata.name} ({b.metadata.id})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Human Review Config */}
            {selectedNode.type === 'human_review' && (
              <div className="space-y-3 bg-slate-950 p-3 rounded-lg border border-slate-800">
                <span className="text-[10px] font-bold text-orange-400 uppercase tracking-wider block">
                  HITL Review Configuration
                </span>
                <div>
                  <label className="text-slate-400 block mb-1 text-[11px]">Assigned Role</label>
                  <input
                    type="text"
                    value={selectedNode.human_review_config?.assigned_role || 'role:finance_executive'}
                    onChange={(e) => {
                      const updatedNodes = workflow.nodes.map((n) =>
                        n.id === selectedNode.id
                          ? {
                              ...n,
                              human_review_config: {
                                ...(n.human_review_config || {
                                  title: n.name || 'Approval Request',
                                  sla_timeout_seconds: 14400,
                                  allowed_actions: ['APPROVE', 'REJECT'],
                                }),
                                assigned_role: e.target.value,
                              },
                            }
                          : n
                      );
                      onUpdateWorkflow({ ...workflow, nodes: updatedNodes });
                    }}
                    className="w-full bg-slate-900 font-mono text-xs text-orange-300 p-2 rounded border border-slate-800 focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>
            )}

            {/* DMN Config */}
            {selectedNode.type === 'dmn_table' && (
              <div className="space-y-3 bg-slate-950 p-3 rounded-lg border border-slate-800">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-purple-400 uppercase tracking-wider">
                    DMN Table Rules
                  </span>
                  <button
                    onClick={() => onOpenDMNEditor(selectedNode.id)}
                    className="text-[10px] font-semibold text-white bg-purple-600 hover:bg-purple-500 px-2 py-0.5 rounded"
                  >
                    Open Spreadsheet
                  </button>
                </div>
                <div className="text-[11px] text-slate-400">
                  {selectedNode.dmn_config?.rules?.length || 0} active decision rules configured.
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

            {/* Delete button */}
            <div className="pt-4 border-t border-slate-800">
              <button
                onClick={() => handleDeleteNode(selectedNode.id)}
                className="w-full py-2 px-3 bg-rose-950/60 hover:bg-rose-900/80 text-rose-300 rounded-lg font-semibold flex items-center justify-center gap-2 border border-rose-800/80 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete Node
              </button>
            </div>
          </div>
        </aside>
      )}
    </div>
  );
};
