import React, { useState } from 'react';
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Clock,
  DollarSign,
  HelpCircle,
  Info,
  Plus,
  Search,
  Shield,
  Tag,
} from 'lucide-react';
import { CapabilityCatalog, DomainBlockContract } from '../../types';

interface BlockPaletteProps {
  catalog: CapabilityCatalog;
  onAddBlockToCanvas: (block: DomainBlockContract) => void;
}

export const BlockPalette: React.FC<BlockPaletteProps> = ({ catalog, onAddBlockToCanvas }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDept, setSelectedDept] = useState<string>('ALL');
  const [inspectingBlock, setInspectingBlock] = useState<DomainBlockContract | null>(null);

  const departments = Object.keys(catalog.departments || {});

  const filteredBlocks = Object.entries(catalog.departments || {}).flatMap(([dept, blocks]) => {
    if (selectedDept !== 'ALL' && selectedDept !== dept) return [];
    return blocks.filter(
      (b) =>
        b.metadata.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        b.metadata.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
        b.metadata.id.toLowerCase().includes(searchTerm.toLowerCase())
    );
  });

  return (
    <aside className="w-80 bg-slate-900 border-r border-slate-800 flex flex-col h-[calc(100vh-4rem)] select-none">
      {/* Palette Header */}
      <div className="p-4 border-b border-slate-800">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Building2 className="w-4 h-4 text-cyan-400" />
            <h2 className="text-xs font-bold text-slate-200 uppercase tracking-wider">Certified Domain Blocks</h2>
          </div>
          <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded-full text-slate-400 font-medium">
            {catalog.total_blocks} blocks
          </span>
        </div>
        <p className="text-[11px] text-slate-400">Zero prompt leakage. Pre-approved business capabilities.</p>

        {/* Search */}
        <div className="relative mt-3">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
          <input
            type="text"
            placeholder="Search capabilities..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-950 text-xs text-slate-200 pl-8 pr-3 py-1.5 rounded-md border border-slate-800 focus:outline-none focus:border-cyan-500 placeholder-slate-500 transition-colors"
          />
        </div>

        {/* Department Filters */}
        <div className="flex flex-wrap gap-1.5 mt-3">
          <button
            onClick={() => setSelectedDept('ALL')}
            className={`text-[10px] px-2 py-0.5 rounded-md font-medium transition-colors ${
              selectedDept === 'ALL' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            All
          </button>
          {departments.map((dept) => (
            <button
              key={dept}
              onClick={() => setSelectedDept(dept)}
              className={`text-[10px] px-2 py-0.5 rounded-md font-medium transition-colors ${
                selectedDept === dept ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'bg-slate-800 text-slate-400 hover:text-slate-200'
              }`}
            >
              {dept}
            </button>
          ))}
        </div>
      </div>

      {/* Block List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {filteredBlocks.map((block) => (
          <div
            key={block.metadata.id}
            className="bg-slate-950/70 border border-slate-800/80 hover:border-cyan-500/50 rounded-lg p-3 transition-all hover:shadow-md hover:shadow-cyan-950/30 group"
          >
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] font-semibold text-cyan-400 uppercase tracking-wider">{block.metadata.department}</span>
                <h3 className="text-xs font-semibold text-slate-100 group-hover:text-cyan-300 transition-colors">
                  {block.metadata.name}
                </h3>
              </div>
              <button
                onClick={() => onAddBlockToCanvas(block)}
                className="w-6 h-6 rounded bg-slate-800 hover:bg-cyan-500 text-slate-300 hover:text-white flex items-center justify-center transition-colors"
                title="Add Block to Canvas"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
            </div>

            <p className="text-[11px] text-slate-400 mt-1 line-clamp-2 leading-relaxed">
              {block.metadata.description}
            </p>

            {/* Badges: Cost & Latency */}
            <div className="flex items-center gap-3 mt-2.5 text-[10px] text-slate-400 border-t border-slate-800/60 pt-2">
              <span className="flex items-center gap-1 font-mono text-emerald-400">
                <DollarSign className="w-3 h-3" />
                ${block.metadata.estimated_cost_usd.toFixed(4)}
              </span>
              <span className="flex items-center gap-1 font-mono text-amber-400">
                <Clock className="w-3 h-3" />
                {block.metadata.p95_latency_ms}ms P95
              </span>
              <button
                onClick={() => setInspectingBlock(block)}
                className="ml-auto text-slate-500 hover:text-cyan-400 text-[10px] flex items-center gap-0.5"
              >
                <Info className="w-3 h-3" />
                Schema
              </button>
            </div>
          </div>
        ))}

        {filteredBlocks.length === 0 && (
          <div className="p-6 text-center text-slate-500 text-xs">
            No domain blocks matching filter.
          </div>
        )}
      </div>

      {/* Schema Contract Modal (Zero Code Leakage) */}
      {inspectingBlock && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-lg w-full p-5 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <span className="text-[10px] font-bold text-cyan-400 uppercase">{inspectingBlock.metadata.department}</span>
                <h3 className="text-sm font-bold text-white">{inspectingBlock.metadata.name}</h3>
                <code className="text-[11px] font-mono text-slate-400">{inspectingBlock.metadata.id}</code>
              </div>
              <button
                onClick={() => setInspectingBlock(null)}
                className="text-slate-400 hover:text-white text-xs px-2 py-1 rounded bg-slate-800"
              >
                ✕ Close
              </button>
            </div>

            <div className="mt-4 space-y-3">
              <div>
                <h4 className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">Input Schema (Pydantic Contract)</h4>
                <pre className="bg-slate-950 p-3 rounded-md text-[11px] font-mono text-cyan-300 overflow-x-auto max-h-36 border border-slate-800">
                  {JSON.stringify(inspectingBlock.input_schema, null, 2)}
                </pre>
              </div>

              <div>
                <h4 className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">Output Schema (Guaranteed State)</h4>
                <pre className="bg-slate-950 p-3 rounded-md text-[11px] font-mono text-emerald-300 overflow-x-auto max-h-36 border border-slate-800">
                  {JSON.stringify(inspectingBlock.output_schema, null, 2)}
                </pre>
              </div>

              <div className="p-2.5 rounded bg-cyan-950/40 border border-cyan-800/40 text-[11px] text-cyan-300 flex items-start gap-2">
                <Shield className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                <span>
                  <strong>Strict Persona Isolation:</strong> Internal model prompts, API keys, and tool invocations remain safely encapsulated inside developer Python code.
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};

