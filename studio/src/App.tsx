import React, { useEffect, useState } from 'react';
import { Header } from './components/Header';
import { BlockPalette } from './components/palette/BlockPalette';
import { WorkflowCanvas } from './components/canvas/WorkflowCanvas';
import { DMNEditor } from './components/dmn/DMNEditor';
import { ApprovalInbox } from './components/inbox/ApprovalInbox';
import { SimulationModal } from './components/simulation/SimulationModal';
import { ProposeChangeModal } from './components/governance/ProposeChangeModal';
import {
  ApprovalTask,
  CapabilityCatalog,
  DMNRule,
  DomainBlockContract,
  WorkflowDefinition,
  WorkflowHeatmap,
} from './types';
import {
  fetchCapabilitiesCatalog,
  fetchHeatmap,
  fetchInboxTasks,
  fetchWorkflowDetail,
  fetchWorkflowsList,
  resolveTask,
} from './api';

export const App: React.FC = () => {
  const [catalog, setCatalog] = useState<CapabilityCatalog>({ total_blocks: 0, departments: {} });
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [currentFile, setCurrentFile] = useState<string>('hybrid_routing_workflow.yaml');
  const [currentYaml, setCurrentYaml] = useState<string>('');
  const [currentWorkflow, setCurrentWorkflow] = useState<WorkflowDefinition | null>(null);

  const [activeView, setActiveView] = useState<'canvas' | 'dmn' | 'inbox' | 'yaml'>('canvas');
  const [heatmapEnabled, setHeatmapEnabled] = useState<boolean>(false);
  const [heatmap, setHeatmap] = useState<WorkflowHeatmap | undefined>(undefined);

  const [tasks, setTasks] = useState<ApprovalTask[]>([]);
  const [editingDmnNodeId, setEditingDmnNodeId] = useState<string | null>(null);
  const [simulationOpen, setSimulationOpen] = useState<boolean>(false);
  const [proposeChangeOpen, setProposeChangeOpen] = useState<boolean>(false);

  // Initialize initial data
  useEffect(() => {
    async function loadInitial() {
      const cat = await fetchCapabilitiesCatalog();
      setCatalog(cat);

      const wfs = await fetchWorkflowsList();
      setWorkflows(wfs);

      const inboxTasks = await fetchInboxTasks();
      setTasks(inboxTasks);
    }
    loadInitial();
  }, []);

  // Load selected workflow
  useEffect(() => {
    async function loadWorkflow() {
      if (!currentFile) return;
      try {
        const detail = await fetchWorkflowDetail(currentFile);
        setCurrentYaml(detail.yaml_content);
        setCurrentWorkflow(detail.ast);

        if (detail.ast?.metadata?.id) {
          const hm = await fetchHeatmap(detail.ast.metadata.id);
          setHeatmap(hm);
        }
      } catch (e) {
        console.error('Failed to load workflow:', e);
      }
    }
    loadWorkflow();
  }, [currentFile]);

  const handleAddBlockToCanvas = (block: DomainBlockContract) => {
    if (!currentWorkflow) return;
    const newNodeId = `${block.metadata.id.split('.').pop()}_${Date.now().toString().slice(-4)}`;
    const newNode = {
      id: newNodeId,
      type: 'block' as const,
      name: block.metadata.name,
      block: block.metadata.id,
      input_mapping: {},
      output_mapping: {},
      max_retries: 3,
    };
    setCurrentWorkflow({
      ...currentWorkflow,
      nodes: [...currentWorkflow.nodes, newNode],
    });
  };

  const handleSaveDMNRules = (nodeId: string, rules: DMNRule[], defaultTarget: string) => {
    if (!currentWorkflow) return;
    const updatedNodes = currentWorkflow.nodes.map((n) => {
      if (n.id === nodeId) {
        return {
          ...n,
          dmn_config: {
            hit_policy: 'FIRST_MATCH' as const,
            rules,
            default_target: defaultTarget,
          },
        };
      }
      return n;
    });
    setCurrentWorkflow({ ...currentWorkflow, nodes: updatedNodes });
  };

  const handleResolveTask = async (
    taskId: string,
    action: string,
    comments?: string,
    updatedFields?: Record<string, any>
  ) => {
    await resolveTask(taskId, action, comments, updatedFields);
    setTasks(tasks.filter((t) => t.task_id !== taskId));
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Top Studio Navbar */}
      <Header
        workflows={workflows}
        currentWorkflowFile={currentFile}
        onSelectWorkflow={setCurrentFile}
        activeView={activeView}
        setActiveView={setActiveView}
        heatmapEnabled={heatmapEnabled}
        setHeatmapEnabled={setHeatmapEnabled}
        onOpenSimulation={() => setSimulationOpen(true)}
        onOpenProposeChange={() => setProposeChangeOpen(true)}
        pendingTaskCount={tasks.length}
      />

      {/* Main Studio Body */}
      <div className="flex-1 flex overflow-hidden">
        {activeView === 'canvas' && (
          <>
            <BlockPalette catalog={catalog} onAddBlockToCanvas={handleAddBlockToCanvas} />
            {currentWorkflow ? (
              <WorkflowCanvas
                workflow={currentWorkflow}
                onUpdateWorkflow={setCurrentWorkflow}
                heatmapEnabled={heatmapEnabled}
                heatmap={heatmap}
                onOpenDMNEditor={(nodeId) => setEditingDmnNodeId(nodeId)}
              />
            ) : (
              <div className="flex-1 flex items-center justify-center text-slate-500 text-xs">
                Loading workflow AST...
              </div>
            )}
          </>
        )}

        {activeView === 'dmn' && currentWorkflow && (
          <div className="flex-1 p-8 overflow-y-auto">
            <div className="max-w-4xl mx-auto space-y-6">
              <h2 className="text-lg font-bold text-white">DMN Decision Tables Overview</h2>
              {currentWorkflow.nodes
                .filter((n) => n.type === 'dmn_table')
                .map((node) => (
                  <div key={node.id} className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-lg">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <span className="text-[10px] font-bold text-purple-400 uppercase">DMN Table Node</span>
                        <h3 className="text-sm font-bold text-white">{node.name || node.id}</h3>
                      </div>
                      <button
                        onClick={() => setEditingDmnNodeId(node.id)}
                        className="px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold"
                      >
                        Open Spreadsheet Editor
                      </button>
                    </div>
                    <div className="space-y-1.5">
                      {node.dmn_config?.rules?.map((r, i) => (
                        <div key={i} className="text-xs font-mono bg-slate-950 p-2 rounded border border-slate-800 flex items-center justify-between">
                          <span className="text-cyan-300">IF {r.condition}</span>
                          <span className="text-purple-400">THEN {r.target}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}

        {activeView === 'inbox' && (
          <ApprovalInbox tasks={tasks} onResolveTask={handleResolveTask} />
        )}

        {activeView === 'yaml' && (
          <div className="flex-1 p-8 bg-slate-950 overflow-auto">
            <div className="max-w-4xl mx-auto space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-bold text-white uppercase tracking-wider">Declarative Specification (`agent-bpmn.yaml`)</h2>
                  <p className="text-xs text-slate-400">Human-readable, Git-versioned workflow definition.</p>
                </div>
              </div>
              <pre className="bg-slate-900 border border-slate-800 rounded-xl p-5 text-xs font-mono text-cyan-300 overflow-x-auto shadow-2xl leading-relaxed">
                {currentYaml}
              </pre>
            </div>
          </div>
        )}
      </div>

      {/* DMN Modal Editor */}
      {editingDmnNodeId && currentWorkflow && (
        <DMNEditor
          node={currentWorkflow.nodes.find((n) => n.id === editingDmnNodeId)!}
          availableNodes={currentWorkflow.nodes.filter((n) => n.id !== editingDmnNodeId).map((n) => n.id)}
          onSaveDMNConfig={handleSaveDMNRules}
          onClose={() => setEditingDmnNodeId(null)}
        />
      )}

      {/* Pre-Flight Simulation Replay Modal */}
      {simulationOpen && (
        <SimulationModal currentYaml={currentYaml} onClose={() => setSimulationOpen(false)} />
      )}

      {/* Propose Change Git Governance Modal */}
      {proposeChangeOpen && currentWorkflow && (
        <ProposeChangeModal
          workflowId={currentWorkflow.metadata.id}
          workflowVersion={currentWorkflow.metadata.version}
          onClose={() => setProposeChangeOpen(false)}
        />
      )}
    </div>
  );
};
export default App;

