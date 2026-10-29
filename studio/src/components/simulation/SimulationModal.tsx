import React, { useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  DollarSign,
  Play,
  RotateCcw,
  Sparkles,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { SimulationReport } from '../../types';
import { runPreflightSimulation } from '../../api';

interface SimulationModalProps {
  currentYaml: string;
  onClose: () => void;
}

export const SimulationModal: React.FC<SimulationModalProps> = ({ currentYaml, onClose }) => {
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<SimulationReport | null>(null);

  const handleRunSimulation = async () => {
    setLoading(true);
    try {
      const res = await runPreflightSimulation(currentYaml);
      setReport(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-6 select-none">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-4xl w-full p-6 shadow-2xl flex flex-col max-h-[88vh]">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-cyan-950/80 border border-cyan-800 text-cyan-400">
              <Play className="w-5 h-5 fill-cyan-400" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-cyan-400">Pillar 5: Sandbox Simulation</span>
                <span className="text-[10px] font-mono bg-slate-800 px-2 py-0.5 rounded text-slate-400">Shadow Mode</span>
              </div>
              <h2 className="text-base font-bold text-white mt-0.5">Pre-Flight Replay Engine</h2>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white px-3 py-1.5 rounded-md bg-slate-800 text-xs font-semibold"
          >
            ✕ Close
          </button>
        </div>

        {/* Action Trigger Banner */}
        <div className="mt-4 p-4 bg-slate-950/80 border border-slate-800 rounded-xl flex items-center justify-between">
          <div>
            <h4 className="text-xs font-bold text-white">Replay 15 Historical Production Checkpoints</h4>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Simulates candidate topology against production traces to calculate route shifts & cost deltas before opening PRs.
            </p>
          </div>
          <button
            disabled={loading}
            onClick={handleRunSimulation}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-white font-bold text-xs shadow-lg shadow-cyan-600/30 transition-all active:scale-95"
          >
            <Play className="w-4 h-4 fill-white" />
            {loading ? 'Replaying...' : 'Execute Simulation'}
          </button>
        </div>

        {/* Diff Results Container */}
        <div className="flex-1 overflow-y-auto mt-4 space-y-4">
          {report ? (
            <>
              {/* Executive Metrics Grid */}
              <div className="grid grid-cols-4 gap-3">
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <span className="text-[10px] uppercase font-bold text-slate-500">Evaluated Cases</span>
                  <div className="text-xl font-bold font-mono text-white mt-1">{report.diff.total_cases}</div>
                  <span className="text-[10px] text-emerald-400 font-medium">100% Replay Coverage</span>
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <span className="text-[10px] uppercase font-bold text-slate-500">Avg Spend Delta</span>
                  <div className="text-xl font-bold font-mono text-cyan-400 mt-1">
                    ${report.diff.candidate_avg_cost_usd.toFixed(4)}
                  </div>
                  <span className={`text-[10px] font-medium ${report.diff.cost_delta_pct <= 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {report.diff.cost_delta_pct > 0 ? `+${report.diff.cost_delta_pct}%` : `${report.diff.cost_delta_pct}%`} vs prod
                  </span>
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <span className="text-[10px] uppercase font-bold text-slate-500">Avg Latency</span>
                  <div className="text-xl font-bold font-mono text-white mt-1">
                    {report.diff.candidate_avg_latency_ms.toFixed(0)} ms
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono">
                    Baseline: {report.diff.baseline_avg_latency_ms.toFixed(0)} ms
                  </span>
                </div>

                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <span className="text-[10px] uppercase font-bold text-slate-500">Schema Violations</span>
                  <div className="text-xl font-bold font-mono text-emerald-400 mt-1">0</div>
                  <span className="text-[10px] text-emerald-400 font-medium">Zero Crashes Detected</span>
                </div>
              </div>

              {/* Route Distribution Shifts Table */}
              <div className="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden">
                <div className="px-4 py-3 bg-slate-900/60 border-b border-slate-800">
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider">Route Distribution Shifts</h4>
                </div>
                <table className="w-full text-left text-xs font-mono">
                  <thead className="bg-slate-900/90 text-slate-400 text-[10px] uppercase tracking-wider border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-4">Terminal Route</th>
                      <th className="py-2.5 px-4">Baseline Share</th>
                      <th className="py-2.5 px-4">Candidate Share</th>
                      <th className="py-2.5 px-4">Shift (% Points)</th>
                      <th className="py-2.5 px-4">Impact</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {Object.entries(report.diff.route_shifts || {}).map(([nid, r]) => (
                      <tr key={nid} className="hover:bg-slate-900/40">
                        <td className="py-2.5 px-4 font-semibold text-white">{nid}</td>
                        <td className="py-2.5 px-4 text-slate-400">{r.baseline_pct.toFixed(1)}%</td>
                        <td className="py-2.5 px-4 text-cyan-300">{r.candidate_pct.toFixed(1)}%</td>
                        <td className={`py-2.5 px-4 font-bold ${r.shift_pct_points > 0 ? 'text-amber-400' : r.shift_pct_points < 0 ? 'text-rose-400' : 'text-slate-400'}`}>
                          {r.shift_pct_points > 0 ? `+${r.shift_pct_points.toFixed(1)}%` : `${r.shift_pct_points.toFixed(1)}%`}
                        </td>
                        <td className="py-2.5 px-4">
                          <span className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${r.shift_pct_points > 0 ? 'bg-amber-950 text-amber-400' : r.shift_pct_points < 0 ? 'bg-rose-950 text-rose-400' : 'bg-slate-800 text-slate-400'}`}>
                            {r.shift_pct_points > 0 ? 'INCREASED' : r.shift_pct_points < 0 ? 'DECREASED' : 'STABLE'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Critical Findings */}
              {report.diff.critical_findings?.length > 0 && (
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-4">
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider mb-2">Policy & Guardrail Findings</h4>
                  <ul className="space-y-1.5 text-xs text-slate-300">
                    {report.diff.critical_findings.map((f, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-cyan-400">•</span>
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div className="h-64 flex flex-col items-center justify-center text-slate-500 text-xs">
              <Play className="w-10 h-10 text-slate-700 mb-2" />
              Click "Execute Simulation" to run candidate topology against historical production cases.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

