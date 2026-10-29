import React, { useState } from 'react';
import {
  Bot,
  Check,
  ChevronDown,
  Layers,
  Play,
  Shield,
  Sliders,
  Sparkles,
  Table,
  UserCheck,
  X,
  Zap,
} from 'lucide-react';
import { createWorkflow } from '../../api';

interface NewWorkflowModalProps {
  onClose: () => void;
  onWorkflowCreated: (newWf: { file_name: string; workflow_id: string; yaml_content: string; ast: any }) => void;
}

export const NewWorkflowModal: React.FC<NewWorkflowModalProps> = ({ onClose, onWorkflowCreated }) => {
  const [name, setName] = useState('');
  const [workflowId, setWorkflowId] = useState('');
  const [isSlugManuallyEdited, setIsSlugManuallyEdited] = useState(false);
  const [department, setDepartment] = useState('Finance Operations');
  const [description, setDescription] = useState('');
  const [template, setTemplate] = useState<'blank' | 'linear' | 'dmn' | 'hitl'>('linear');
  const [maxBudget, setMaxBudget] = useState<number>(0.5);
  const [maxLoops, setMaxLoops] = useState<number>(3);
  const [timeoutSecs, setTimeoutSecs] = useState<number>(600);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleNameChange = (val: string) => {
    setName(val);
    if (!isSlugManuallyEdited) {
      const slug = val
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '');
      setWorkflowId(slug);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Please provide a workflow name.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const finalId = workflowId.trim() || name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
      const res = await createWorkflow({
        name: name.trim(),
        workflow_id: finalId,
        department,
        description: description.trim(),
        template,
        max_budget_usd: maxBudget,
        max_loop_iterations: maxLoops,
        workflow_timeout_seconds: timeoutSecs,
      });

      onWorkflowCreated(res);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to create workflow.');
    } finally {
      setLoading(false);
    }
  };

  const templateOptions = [
    {
      id: 'blank',
      title: 'Blank Starter Canvas',
      icon: <Layers className="w-5 h-5 text-slate-400" />,
      description: 'Clean starter flow with START, sample block, and END. Best for custom-tailored topologies.',
      badge: 'Minimal',
    },
    {
      id: 'linear',
      title: 'Straight-Through (STP) Pipeline',
      icon: <Zap className="w-5 h-5 text-cyan-400" />,
      description: 'Linear sequential processing: Document Extraction → Sanctions Screening → Auto Settlement.',
      badge: 'Popular',
    },
    {
      id: 'dmn',
      title: 'DMN Business Rules Router',
      icon: <Table className="w-5 h-5 text-purple-400" />,
      description: 'FIRST_MATCH DMN decision table evaluating sanctions risk and invoice amounts before branching.',
      badge: 'Hybrid AI',
    },
    {
      id: 'hitl',
      title: 'Executive Human Approval Gate',
      icon: <UserCheck className="w-5 h-5 text-amber-400" />,
      description: 'LangGraph Interrupt checkpoint for role-based governance with SLA watchdog deadlines.',
      badge: 'Enterprise HITL',
    },
  ];

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-cyan-950 text-cyan-400 border border-cyan-800/60">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Create New Workflow</h2>
              <p className="text-xs text-slate-400">Design and register a certified agentic orchestration pipeline</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto space-y-5">
          {error && (
            <div className="p-3 bg-rose-950/60 border border-rose-800 rounded-lg text-rose-300 text-xs">
              {error}
            </div>
          )}

          {/* Workflow Name & ID */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Workflow Name <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="e.g. KYC Onboarding & AML Screening"
                value={name}
                onChange={(e) => handleNameChange(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 placeholder:text-slate-600 transition-colors"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                Workflow Identifier (Slug)
              </label>
              <input
                type="text"
                placeholder="e.g. kyc_onboarding_aml_screening"
                value={workflowId}
                onChange={(e) => {
                  setIsSlugManuallyEdited(true);
                  setWorkflowId(e.target.value);
                }}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-cyan-300 focus:outline-none focus:border-cyan-500 placeholder:text-slate-600 transition-colors"
              />
            </div>
          </div>

          {/* Department & Description */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Owner Department</label>
              <select
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 transition-colors"
              >
                <option value="Finance Operations">Finance Operations</option>
                <option value="Regulatory Compliance">Regulatory Compliance</option>
                <option value="Customer Support">Customer Support</option>
                <option value="Risk & Fraud Operations">Risk & Fraud Operations</option>
                <option value="General Operations">General Operations</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Description</label>
              <input
                type="text"
                placeholder="Brief business summary of this workflow..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 placeholder:text-slate-600 transition-colors"
              />
            </div>
          </div>

          {/* Template Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-2">
              Choose Workflow Template
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {templateOptions.map((opt) => {
                const isSelected = template === opt.id;
                return (
                  <div
                    key={opt.id}
                    onClick={() => setTemplate(opt.id as any)}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? 'border-cyan-500 bg-cyan-950/30 ring-1 ring-cyan-500/50 shadow-md shadow-cyan-950/40'
                        : 'border-slate-800 bg-slate-950/60 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-start justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        {opt.icon}
                        <span className="text-xs font-bold text-white">{opt.title}</span>
                      </div>
                      <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                        {opt.badge}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 leading-relaxed">{opt.description}</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Guardrails Configuration */}
          <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-3.5 space-y-3">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-300">
              <Sliders className="w-3.5 h-3.5 text-cyan-400" />
              Runtime Guardrails Defaults
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-[10px] text-slate-400 mb-1">Max Spend ($ USD)</label>
                <input
                  type="number"
                  step="0.05"
                  min="0.01"
                  max="10.0"
                  value={maxBudget}
                  onChange={(e) => setMaxBudget(parseFloat(e.target.value) || 0.5)}
                  className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1 text-xs font-mono text-emerald-400 focus:outline-none focus:border-cyan-500"
                />
              </div>
              <div>
                <label className="block text-[10px] text-slate-400 mb-1">Max Loop Retries</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={maxLoops}
                  onChange={(e) => setMaxLoops(parseInt(e.target.value) || 3)}
                  className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1 text-xs font-mono text-purple-400 focus:outline-none focus:border-cyan-500"
                />
              </div>
              <div>
                <label className="block text-[10px] text-slate-400 mb-1">Timeout (Seconds)</label>
                <input
                  type="number"
                  min="30"
                  max="3600"
                  value={timeoutSecs}
                  onChange={(e) => setTimeoutSecs(parseInt(e.target.value) || 600)}
                  className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1 text-xs font-mono text-amber-400 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>
          </div>

          {/* Modal Footer */}
          <div className="pt-3 border-t border-slate-800 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !name.trim()}
              className="px-5 py-2 rounded-lg text-xs font-bold bg-gradient-to-r from-cyan-500 to-indigo-600 hover:from-cyan-400 hover:to-indigo-500 text-white shadow-lg shadow-cyan-500/25 disabled:opacity-50 transition-all flex items-center gap-2"
            >
              {loading ? (
                <span>Creating Workflow...</span>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  <span>Create Workflow</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
