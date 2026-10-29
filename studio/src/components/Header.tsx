import React from 'react';
import {
  Activity,
  CheckCircle,
  FileCode,
  Flame,
  GitPullRequest,
  Inbox,
  Layers,
  Play,
  RotateCcw,
  Sliders,
  Table,
} from 'lucide-react';

interface HeaderProps {
  workflows: any[];
  currentWorkflowFile: string;
  onSelectWorkflow: (fileName: string) => void;
  activeView: 'canvas' | 'dmn' | 'inbox' | 'yaml';
  setActiveView: (view: 'canvas' | 'dmn' | 'inbox' | 'yaml') => void;
  heatmapEnabled: boolean;
  setHeatmapEnabled: (v: boolean) => void;
  onOpenSimulation: () => void;
  onOpenProposeChange: () => void;
  pendingTaskCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  workflows,
  currentWorkflowFile,
  onSelectWorkflow,
  activeView,
  setActiveView,
  heatmapEnabled,
  setHeatmapEnabled,
  onOpenSimulation,
  onOpenProposeChange,
  pendingTaskCount,
}) => {
  return (
    <header className="h-16 bg-slate-900 border-b border-slate-800 px-6 flex items-center justify-between select-none">
      {/* Brand & Persona Divider */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Layers className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-base tracking-tight text-white">Agent<span className="text-cyan-400">BPMN</span></span>
              <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-cyan-950/80 text-cyan-400 border border-cyan-800/60 tracking-wider">Studio v0.7</span>
            </div>
            <p className="text-[11px] text-slate-400">Management Persona Canvas</p>
          </div>
        </div>

        {/* Workflow File Selector */}
        <div className="h-6 w-px bg-slate-800 mx-2" />
        <select
          value={currentWorkflowFile}
          onChange={(e) => onSelectWorkflow(e.target.value)}
          className="bg-slate-800/90 text-slate-200 text-xs rounded-md border border-slate-700 px-3 py-1.5 focus:outline-none focus:border-cyan-500 transition-colors"
        >
          {workflows.map((wf) => (
            <option key={wf.file_name} value={wf.file_name}>
              {wf.metadata?.name || wf.file_name} ({wf.metadata?.version || 'v1.0'})
            </option>
          ))}
        </select>
      </div>

      {/* Center Nav Views */}
      <div className="flex items-center bg-slate-950/80 p-1 rounded-lg border border-slate-800">
        <button
          onClick={() => setActiveView('canvas')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
            activeView === 'canvas' ? 'bg-cyan-500 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          Canvas
        </button>

        <button
          onClick={() => setActiveView('dmn')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
            activeView === 'dmn' ? 'bg-cyan-500 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Table className="w-3.5 h-3.5" />
          DMN Rules
        </button>

        <button
          onClick={() => setActiveView('inbox')}
          className={`relative flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
            activeView === 'inbox' ? 'bg-cyan-500 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <Inbox className="w-3.5 h-3.5" />
          Approval Inbox
          {pendingTaskCount > 0 && (
            <span className="w-4 h-4 text-[10px] font-bold rounded-full bg-amber-500 text-slate-950 flex items-center justify-center">
              {pendingTaskCount}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveView('yaml')}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
            activeView === 'yaml' ? 'bg-cyan-500 text-white shadow-sm' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileCode className="w-3.5 h-3.5" />
          YAML Spec
        </button>
      </div>

      {/* Right Action Tools: Heatmap Toggle, Simulation, Propose Change */}
      <div className="flex items-center gap-3">
        {/* Heatmap Toggle */}
        <button
          onClick={() => setHeatmapEnabled(!heatmapEnabled)}
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border transition-colors ${
            heatmapEnabled
              ? 'bg-rose-950/70 text-rose-400 border-rose-800 shadow-sm shadow-rose-900/30'
              : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-750'
          }`}
          title="Toggle Process Intelligence Heatmap (Camunda Optimize style)"
        >
          <Flame className={`w-3.5 h-3.5 ${heatmapEnabled ? 'text-rose-400 fill-rose-400' : 'text-slate-400'}`} />
          Heatmap {heatmapEnabled ? 'ON' : 'OFF'}
        </button>

        {/* Pre-Flight Simulation */}
        <button
          onClick={onOpenSimulation}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
          title="Pre-flight replay historical production runs in sandbox"
        >
          <Play className="w-3.5 h-3.5 text-cyan-400 fill-cyan-400" />
          Simulate Impact
        </button>

        {/* Propose Change Git Button */}
        <button
          onClick={onOpenProposeChange}
          className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-semibold bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white shadow-md shadow-emerald-500/20 transition-all active:scale-95"
        >
          <GitPullRequest className="w-3.5 h-3.5" />
          Propose Change
        </button>
      </div>
    </header>
  );
};

