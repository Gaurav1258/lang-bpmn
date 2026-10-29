import React, { useState } from 'react';
import {
  AlertCircle,
  CheckCircle,
  Clock,
  Edit3,
  FileText,
  Inbox,
  Shield,
  ThumbsDown,
  ThumbsUp,
  User,
  XCircle,
} from 'lucide-react';
import { ApprovalTask } from '../../types';

interface ApprovalInboxProps {
  tasks: ApprovalTask[];
  onResolveTask: (taskId: string, action: string, comments?: string, updatedFields?: Record<string, any>) => void;
}

export const ApprovalInbox: React.FC<ApprovalInboxProps> = ({ tasks, onResolveTask }) => {
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(
    tasks.length > 0 ? tasks[0].task_id : null
  );
  const [comments, setComments] = useState<string>('');
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editedFields, setEditedFields] = useState<Record<string, any>>({});

  const selectedTask = tasks.find((t) => t.task_id === selectedTaskId) || tasks[0];

  const handleAction = (action: string) => {
    if (!selectedTask) return;
    onResolveTask(
      selectedTask.task_id,
      action,
      comments,
      action === 'EDIT_AND_APPROVE' ? editedFields : undefined
    );
    setComments('');
    setIsEditing(false);
  };

  return (
    <div className="flex-1 flex h-[calc(100vh-4rem)] bg-slate-950 select-none overflow-hidden">
      {/* Tasks Master List */}
      <div className="w-96 bg-slate-900 border-r border-slate-800 flex flex-col h-full">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Inbox className="w-4 h-4 text-cyan-400" />
            <h2 className="text-xs font-bold text-white uppercase tracking-wider">Enterprise Approval Queue</h2>
          </div>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-400 border border-cyan-800">
            {tasks.length} pending
          </span>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {tasks.map((task) => {
            const isSelected = selectedTask?.task_id === task.task_id;
            return (
              <div
                key={task.task_id}
                onClick={() => {
                  setSelectedTaskId(task.task_id);
                  setEditedFields(task.state_snapshot || {});
                }}
                className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                  isSelected
                    ? 'bg-slate-800/90 border-cyan-500 shadow-md shadow-cyan-950/40'
                    : 'bg-slate-950/70 border-slate-800/80 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-orange-950/80 text-orange-400 border border-orange-800/60 font-semibold">
                    {task.assigned_role}
                  </span>
                  <span className="text-[10px] font-mono text-amber-400 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    SLA: 3h 45m
                  </span>
                </div>
                <h4 className="text-xs font-bold text-white leading-tight mt-1">{task.title}</h4>
                <p className="text-[11px] text-slate-400 mt-1 line-clamp-1">{task.description}</p>
                <div className="mt-2 text-[10px] font-mono text-slate-500">
                  Node: <span className="text-slate-400">{task.node_id}</span>
                </div>
              </div>
            );
          })}

          {tasks.length === 0 && (
            <div className="p-8 text-center text-slate-500 text-xs">
              <CheckCircle className="w-8 h-8 mx-auto text-emerald-500 mb-2 opacity-60" />
              All approval queues cleared!
            </div>
          )}
        </div>
      </div>

      {/* Task Details & Action Card */}
      {selectedTask ? (
        <div className="flex-1 flex flex-col h-full overflow-y-auto p-8 bg-slate-950">
          <div className="max-w-3xl mx-auto w-full space-y-6">
            {/* Task Card Header */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-xs font-bold px-2.5 py-0.5 rounded bg-orange-950 text-orange-400 border border-orange-800/80 uppercase tracking-wider">
                      {selectedTask.assigned_role}
                    </span>
                    <span className="text-xs font-mono text-slate-400">Task ID: {selectedTask.task_id}</span>
                  </div>
                  <h1 className="text-lg font-extrabold text-white">{selectedTask.title}</h1>
                  <p className="text-xs text-slate-400 mt-1">{selectedTask.description}</p>
                </div>
                <div className="text-right">
                  <span className="text-[10px] uppercase font-bold text-slate-500 block">SLA Timeout</span>
                  <span className="text-sm font-bold font-mono text-amber-400">3 hrs 42 mins</span>
                </div>
              </div>
            </div>

            {/* State Snapshot Form (Dynamic Pydantic Rendering) */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-cyan-400" />
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider">Execution State Snapshot</h3>
                </div>
                <button
                  onClick={() => setIsEditing(!isEditing)}
                  className="flex items-center gap-1 text-xs font-semibold text-cyan-400 hover:text-cyan-300"
                >
                  <Edit3 className="w-3.5 h-3.5" />
                  {isEditing ? 'Cancel Edit' : 'Edit Fields'}
                </button>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {Object.entries(selectedTask.state_snapshot || {}).map(([key, val]) => (
                  <div key={key} className="bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <label className="text-[10px] font-mono uppercase text-slate-400 block mb-1">{key}</label>
                    {isEditing ? (
                      <input
                        type="text"
                        value={editedFields[key] ?? String(val)}
                        onChange={(e) => setEditedFields({ ...editedFields, [key]: e.target.value })}
                        className="w-full bg-slate-900 text-xs font-mono text-cyan-300 p-1.5 rounded border border-slate-700 focus:outline-none focus:border-cyan-500"
                      />
                    ) : (
                      <span className="text-xs font-mono font-medium text-slate-200">
                        {typeof val === 'boolean' ? (val ? 'TRUE' : 'FALSE') : String(val)}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Resolution Form: Comments & Action Buttons */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-4">
              <h3 className="text-xs font-bold text-white uppercase tracking-wider">Reviewer Action</h3>
              <textarea
                placeholder="Audit trail comments (optional reasoning for decision)..."
                value={comments}
                onChange={(e) => setComments(e.target.value)}
                className="w-full bg-slate-950 text-xs text-slate-200 p-3 rounded-xl border border-slate-800 focus:outline-none focus:border-cyan-500 placeholder-slate-600 resize-none h-20"
              />

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  onClick={() => handleAction('REJECT')}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-rose-950/80 hover:bg-rose-900 text-rose-300 border border-rose-800 text-xs font-bold shadow-md transition-all active:scale-95"
                >
                  <ThumbsDown className="w-4 h-4" />
                  Reject Task
                </button>

                {isEditing ? (
                  <button
                    onClick={() => handleAction('EDIT_AND_APPROVE')}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-slate-950 text-xs font-extrabold shadow-md transition-all active:scale-95"
                  >
                    <Edit3 className="w-4 h-4" />
                    Save & Approve
                  </button>
                ) : (
                  <button
                    onClick={() => handleAction('APPROVE')}
                    className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-extrabold shadow-lg shadow-emerald-600/30 transition-all active:scale-95"
                  >
                    <ThumbsUp className="w-4 h-4" />
                    Approve & Resume
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-slate-500 text-xs">
          Select an approval task from the queue.
        </div>
      )}
    </div>
  );
};

