import React, { useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CheckCircle2,
  Clock,
  DollarSign,
  Inbox,
  Play,
  RotateCcw,
  Sparkles,
  StopCircle,
  X,
  XCircle,
} from 'lucide-react';
import { executeWorkflow } from '../../api';

interface TestWorkflowModalProps {
  workflowId: string;
  workflowName: string;
  currentYaml: string;
  onClose: () => void;
  onGoToInbox: () => void;
}

export const TestWorkflowModal: React.FC<TestWorkflowModalProps> = ({
  workflowId,
  workflowName,
  currentYaml,
  onClose,
  onGoToInbox,
}) => {
  const [inputPayloadStr, setInputPayloadStr] = useState<string>(
    JSON.stringify(
      {
        invoice_pdf_url: 's3://invoices-2026/q3/apex_cloud_inv9812.pdf',
        tax_id: 'US-94-8192019',
        country_code: 'US',
        entity_name: 'Apex Cloud Infrastructure Ltd',
        inquiry_text: 'Please review urgent invoice payout for quarterly cloud compute cluster',
      },
      null,
      2
    )
  );

  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleExecute = async () => {
    let parsedInput: Record<string, any>;
    try {
      parsedInput = JSON.parse(inputPayloadStr);
    } catch (e: any) {
      setError(`Invalid JSON payload: ${e.message}`);
      return;
    }

    setIsRunning(true);
    setError(null);
    setResult(null);

    try {
      const res = await executeWorkflow({
        workflow_yaml: currentYaml,
        input_payload: parsedInput,
      });
      setResult(res);
    } catch (err: any) {
      setError(err.message || 'Execution failed');
    } finally {
      setIsRunning(false);
    }
  };

  const loadSamplePreset = (preset: 'clean' | 'high_value' | 'sanction_flag') => {
    if (preset === 'clean') {
      setInputPayloadStr(
        JSON.stringify(
          {
            invoice_pdf_url: 's3://invoices-2026/q3/vendor_clean_inv101.pdf',
            tax_id: 'US-94-8192019',
            country_code: 'US',
            entity_name: 'Standard Clean Tech LLC',
          },
          null,
          2
        )
      );
    } else if (preset === 'high_value') {
      setInputPayloadStr(
        JSON.stringify(
          {
            invoice_pdf_url: 's3://invoices-2026/q3/apex_cloud_inv9812.pdf',
            tax_id: 'US-94-8192019',
            country_code: 'US',
            entity_name: 'Apex Cloud Infrastructure Ltd',
            simulated_amount_usd: 14500.0,
          },
          null,
          2
        )
      );
    } else {
      setInputPayloadStr(
        JSON.stringify(
          {
            invoice_pdf_url: 's3://invoices-2026/q3/sanctions_match_doc.pdf',
            tax_id: 'IR-44-00192',
            country_code: 'IR',
            entity_name: 'acme contraband corp',
          },
          null,
          2
        )
      );
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-emerald-950 text-emerald-400 border border-emerald-800/60">
              <Play className="w-5 h-5 fill-emerald-400" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Live Execution Runner</h2>
              <p className="text-xs text-slate-400">
                Execute <span className="text-cyan-400 font-mono">{workflowName}</span> in sandbox
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-5">
          {/* Presets and Input */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-300">Input JSON State Payload</label>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-slate-500">Presets:</span>
                <button
                  onClick={() => loadSamplePreset('clean')}
                  className="text-[10px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-750 text-slate-300 border border-slate-700"
                >
                  Standard Clean
                </button>
                <button
                  onClick={() => loadSamplePreset('high_value')}
                  className="text-[10px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-750 text-amber-300 border border-slate-700"
                >
                  High Value ($14.5k)
                </button>
                <button
                  onClick={() => loadSamplePreset('sanction_flag')}
                  className="text-[10px] px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-750 text-rose-300 border border-slate-700"
                >
                  Sanctions Flag
                </button>
              </div>
            </div>

            <textarea
              rows={5}
              value={inputPayloadStr}
              onChange={(e) => setInputPayloadStr(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 font-mono text-xs text-cyan-300 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Action Trigger */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">
              Runs synchronously against compiled LangGraph engine with spend guardrails
            </span>
            <button
              onClick={handleExecute}
              disabled={isRunning}
              className="px-5 py-2 rounded-lg text-xs font-bold bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white shadow-lg shadow-emerald-500/20 disabled:opacity-50 transition-all flex items-center gap-2"
            >
              <Play className="w-3.5 h-3.5 fill-white" />
              {isRunning ? 'Executing Graph...' : 'Run Workflow'}
            </button>
          </div>

          {error && (
            <div className="p-3 bg-rose-950/60 border border-rose-800 rounded-lg text-rose-300 text-xs flex items-center gap-2">
              <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Execution Result */}
          {result && (
            <div className="space-y-4 pt-3 border-t border-slate-800">
              {/* Status Header */}
              <div className="flex items-center justify-between bg-slate-950 p-4 rounded-xl border border-slate-800">
                <div className="flex items-center gap-3">
                  {result.status === 'COMPLETED' ? (
                    <div className="p-2 rounded-lg bg-emerald-950 text-emerald-400 border border-emerald-800">
                      <CheckCircle2 className="w-5 h-5" />
                    </div>
                  ) : result.status === 'INTERRUPTED' ? (
                    <div className="p-2 rounded-lg bg-amber-950 text-amber-400 border border-amber-800">
                      <Clock className="w-5 h-5" />
                    </div>
                  ) : (
                    <div className="p-2 rounded-lg bg-rose-950 text-rose-400 border border-rose-800">
                      <XCircle className="w-5 h-5" />
                    </div>
                  )}
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-white uppercase tracking-wider">
                        Execution Status:
                      </span>
                      <span
                        className={`text-xs font-bold px-2 py-0.5 rounded ${
                          result.status === 'COMPLETED'
                            ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                            : result.status === 'INTERRUPTED'
                            ? 'bg-amber-950 text-amber-400 border border-amber-800'
                            : 'bg-rose-950 text-rose-400 border border-rose-800'
                        }`}
                      >
                        {result.status}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                      {result.status === 'COMPLETED'
                        ? 'All nodes in workflow path executed to completion successfully.'
                        : result.status === 'INTERRUPTED'
                        ? 'Execution suspended at Human-in-the-Loop checkpoint awaiting sign-off.'
                        : `Execution failed: ${result.error_message || 'Runtime exception'}`}
                    </p>
                  </div>
                </div>

                <div className="text-right font-mono text-xs">
                  <span className="text-slate-400 block text-[10px]">Total Cost</span>
                  <span className="text-emerald-400 font-bold">${result.total_cost_usd?.toFixed(4) || '0.0000'} USD</span>
                </div>
              </div>

              {/* Interruption Notice */}
              {result.status === 'INTERRUPTED' && (
                <div className="p-3 bg-amber-950/40 border border-amber-800/80 rounded-xl flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs text-amber-300">
                    <Inbox className="w-4 h-4 text-amber-400 shrink-0" />
                    <span>A pending approval task is ready in your <strong>Approval Inbox</strong>.</span>
                  </div>
                  <button
                    onClick={() => {
                      onClose();
                      onGoToInbox();
                    }}
                    className="px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-slate-950 font-bold text-xs flex items-center gap-1.5 transition-colors"
                  >
                    Open Inbox
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* Execution Path History */}
              {result.history && result.history.length > 0 && (
                <div>
                  <span className="text-xs font-semibold text-slate-300 block mb-2">Step Execution Trace</span>
                  <div className="flex flex-wrap items-center gap-2 bg-slate-950 p-3 rounded-xl border border-slate-800">
                    <span className="text-[11px] font-bold text-emerald-400 bg-emerald-950 px-2 py-0.5 rounded border border-emerald-800">
                      START
                    </span>
                    {result.history.map((step: string, idx: number) => (
                      <React.Fragment key={idx}>
                        <ArrowRight className="w-3.5 h-3.5 text-slate-600" />
                        <span className="text-[11px] font-mono text-cyan-300 bg-slate-900 px-2 py-0.5 rounded border border-slate-700">
                          {step}
                        </span>
                      </React.Fragment>
                    ))}
                    {result.status === 'COMPLETED' && (
                      <>
                        <ArrowRight className="w-3.5 h-3.5 text-slate-600" />
                        <span className="text-[11px] font-bold text-rose-400 bg-rose-950 px-2 py-0.5 rounded border border-rose-800">
                          END
                        </span>
                      </>
                    )}
                  </div>
                </div>
              )}

              {/* Final State Output */}
              <div>
                <span className="text-xs font-semibold text-slate-300 block mb-1.5">Final State Data</span>
                <pre className="bg-slate-950 border border-slate-800 rounded-xl p-3 font-mono text-[11px] text-slate-300 max-h-48 overflow-auto leading-relaxed">
                  {JSON.stringify(result.final_state, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

