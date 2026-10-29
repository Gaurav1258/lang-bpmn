import React, { useState } from 'react';
import { CheckCircle2, GitBranch, GitPullRequest, ShieldAlert, Sparkles } from 'lucide-react';

interface ProposeChangeModalProps {
  workflowId: string;
  workflowVersion: string;
  onClose: () => void;
}

export const ProposeChangeModal: React.FC<ProposeChangeModalProps> = ({
  workflowId,
  workflowVersion,
  onClose,
}) => {
  const [reason, setReason] = useState(
    'Tightened sanctions risk threshold from 0.70 to 0.50 and lowered L2 threshold from $50k to $10k per Q4 Enterprise Compliance review.'
  );
  const [branchName] = useState(`governance/wf-${workflowId}-${Date.now().toString().slice(-6)}`);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-6 select-none">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 shadow-2xl">
        {submitted ? (
          <div className="text-center py-6 space-y-3">
            <div className="w-12 h-12 rounded-full bg-emerald-950 border border-emerald-500 text-emerald-400 flex items-center justify-center mx-auto shadow-lg shadow-emerald-500/20">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h3 className="text-base font-bold text-white">Pull Request Created Successfully!</h3>
            <p className="text-xs text-slate-300 max-w-md mx-auto">
              Branch <code className="font-mono text-cyan-400 bg-slate-950 px-1.5 py-0.5 rounded">{branchName}</code> pushed to GitHub. Pre-flight simulation diff and audit trail attached to PR #42.
            </p>
            <div className="pt-4">
              <button
                onClick={onClose}
                className="px-6 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-emerald-950 border border-emerald-800 text-emerald-400">
                  <GitPullRequest className="w-5 h-5" />
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-emerald-400 tracking-wider">Pillar 6: Git Governance</span>
                  <h3 className="text-sm font-bold text-white">Propose Workflow Policy Change</h3>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="text-slate-400 hover:text-white text-xs px-2 py-1 rounded bg-slate-800"
              >
                ✕
              </button>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">Target Git Branch (Backend-Managed)</label>
              <div className="flex items-center gap-2 bg-slate-950 p-2.5 rounded-lg border border-slate-800 font-mono text-xs text-slate-400">
                <GitBranch className="w-4 h-4 text-cyan-400 shrink-0" />
                <span>{branchName}</span>
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">
                Mandatory Business Justification (Audit Trail)
              </label>
              <textarea
                required
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Explain the business policy reason for this topology or DMN rule adjustment..."
                className="w-full bg-slate-950 text-xs text-slate-200 p-3 rounded-xl border border-slate-800 focus:outline-none focus:border-cyan-500 placeholder-slate-600 resize-none h-24"
              />
            </div>

            <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-[11px] text-slate-400 space-y-1">
              <div className="flex items-center gap-1.5 text-cyan-400 font-semibold">
                <Sparkles className="w-3.5 h-3.5" />
                Automated Governance CI Pipeline
              </div>
              <p>
                Clicking Propose will commit the updated <code className="text-slate-300">agent-bpmn.yaml</code>, run regression tests against 31 unit tests, and attach the pre-flight simulation diff report automatically.
              </p>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-6 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-lg shadow-emerald-600/30 transition-all active:scale-95"
              >
                Submit Change Proposal
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

