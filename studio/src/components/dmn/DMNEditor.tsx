import React, { useState } from 'react';
import { Plus, Trash2, Table, ShieldCheck, Check, ArrowRight } from 'lucide-react';
import { DMNRule, WorkflowNode } from '../../types';

interface DMNEditorProps {
  node: WorkflowNode;
  availableNodes: string[];
  onSaveDMNConfig: (nodeId: string, rules: DMNRule[], defaultTarget: string) => void;
  onClose: () => void;
}

export const DMNEditor: React.FC<DMNEditorProps> = ({
  node,
  availableNodes,
  onSaveDMNConfig,
  onClose,
}) => {
  const [rules, setRules] = useState<DMNRule[]>(
    node.dmn_config?.rules ? [...node.dmn_config.rules] : []
  );
  const [defaultTarget, setDefaultTarget] = useState<string>(
    node.dmn_config?.default_target || 'END'
  );

  const handleAddRule = () => {
    setRules([
      ...rules,
      {
        condition: 'invoice_total_usd > 10000.0',
        target: availableNodes[0] || 'END',
        description: 'New decision rule',
      },
    ]);
  };

  const handleUpdateRule = (index: number, field: keyof DMNRule, value: string) => {
    const updated = [...rules];
    updated[index] = { ...updated[index], [field]: value };
    setRules(updated);
  };

  const handleDeleteRule = (index: number) => {
    setRules(rules.filter((_, i) => i !== index));
  };

  const handleSave = () => {
    onSaveDMNConfig(node.id, rules, defaultTarget);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-6 select-none">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-4xl w-full p-6 shadow-2xl flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-purple-950/80 border border-purple-800 text-purple-400">
              <Table className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-purple-400">DMN Decision Table</span>
                <span className="text-[10px] font-mono bg-slate-800 px-2 py-0.5 rounded text-slate-400">Policy: FIRST_MATCH</span>
              </div>
              <h2 className="text-base font-bold text-white mt-0.5">{node.name || node.id}</h2>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white px-3 py-1.5 rounded-md bg-slate-800 text-xs font-semibold"
          >
            ✕ Close
          </button>
        </div>

        {/* Info banner */}
        <div className="mt-4 p-3 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between text-xs text-slate-300">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Sandboxed AST Expression Evaluation: Evaluated safely without arbitrary code execution.</span>
          </div>
          <button
            onClick={handleAddRule}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-md font-semibold text-xs transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Rule
          </button>
        </div>

        {/* Spreadsheet Table */}
        <div className="flex-1 overflow-y-auto mt-4 border border-slate-800 rounded-xl bg-slate-950">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 uppercase text-[10px] font-bold tracking-wider">
              <tr>
                <th className="py-3 px-4 w-12 text-center">#</th>
                <th className="py-3 px-4 w-2/5">Condition (Safe Expression)</th>
                <th className="py-3 px-4 w-1/4">Target Destination Node</th>
                <th className="py-3 px-4">Business Description</th>
                <th className="py-3 px-4 w-12 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {rules.map((rule, idx) => (
                <tr key={idx} className="hover:bg-slate-900/50 transition-colors">
                  <td className="py-2.5 px-4 text-center text-slate-500">{idx + 1}</td>
                  <td className="py-2.5 px-4">
                    <input
                      type="text"
                      value={rule.condition || ''}
                      onChange={(e) => handleUpdateRule(idx, 'condition', e.target.value)}
                      placeholder="e.g. amount > 10000 and is_flagged == true"
                      className="w-full bg-slate-900 text-cyan-300 font-mono text-xs px-2.5 py-1.5 rounded border border-slate-800 focus:outline-none focus:border-cyan-500"
                    />
                  </td>
                  <td className="py-2.5 px-4">
                    <select
                      value={rule.target}
                      onChange={(e) => handleUpdateRule(idx, 'target', e.target.value)}
                      className="w-full bg-slate-900 text-purple-300 font-mono text-xs px-2.5 py-1.5 rounded border border-slate-800 focus:outline-none focus:border-purple-500"
                    >
                      {availableNodes.map((targetId) => (
                        <option key={targetId} value={targetId}>
                          {targetId}
                        </option>
                      ))}
                      <option value="END">END</option>
                    </select>
                  </td>
                  <td className="py-2.5 px-4 font-sans">
                    <input
                      type="text"
                      value={rule.description || ''}
                      onChange={(e) => handleUpdateRule(idx, 'description', e.target.value)}
                      placeholder="Policy reason..."
                      className="w-full bg-slate-900 text-slate-300 text-xs px-2.5 py-1.5 rounded border border-slate-800 focus:outline-none focus:border-slate-700"
                    />
                  </td>
                  <td className="py-2.5 px-4 text-center">
                    <button
                      onClick={() => handleDeleteRule(idx)}
                      className="text-slate-500 hover:text-rose-400 transition-colors"
                      title="Delete Rule"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}

              {/* Default Fallback Row */}
              <tr className="bg-slate-900/80 font-mono">
                <td className="py-3 px-4 text-center text-purple-400 font-bold">*</td>
                <td className="py-3 px-4 text-slate-400 font-sans italic">Default Fallback (When no rules match)</td>
                <td className="py-3 px-4">
                  <select
                    value={defaultTarget}
                    onChange={(e) => setDefaultTarget(e.target.value)}
                    className="w-full bg-slate-950 text-purple-300 font-mono text-xs px-2.5 py-1.5 rounded border border-purple-800/80 focus:outline-none"
                  >
                    {availableNodes.map((targetId) => (
                      <option key={targetId} value={targetId}>
                        {targetId}
                      </option>
                    ))}
                    <option value="END">END</option>
                  </select>
                </td>
                <td className="py-3 px-4 text-slate-500 font-sans text-xs italic" colSpan={2}>
                  Standard non-exceptional operational path
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-4 mt-4 border-t border-slate-800">
          <span className="text-xs text-slate-500">Changes update workflow AST in memory.</span>
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold shadow-lg shadow-purple-600/20 transition-colors"
            >
              <Check className="w-4 h-4" />
              Save Rules
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

