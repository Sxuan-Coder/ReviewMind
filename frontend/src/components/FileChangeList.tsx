import type { ChangedFile } from '../types';
import { cn } from '../lib/utils';

interface FileChangeListProps {
  files: ChangedFile[];
}

const statusLabels: Record<string, { text: string; color: string }> = {
  added: { text: '新增', color: 'text-emerald-400 bg-emerald-950/40' },
  modified: { text: '修改', color: 'text-amber-400 bg-amber-950/40' },
  removed: { text: '删除', color: 'text-red-400 bg-red-950/40' },
  renamed: { text: '重命名', color: 'text-purple-400 bg-purple-950/40' },
};

function FileIcon({ filename }: { filename: string }) {
  const ext = filename.split('.').pop() || '';
  const iconMap: Record<string, string> = {
    ts: '📘',
    tsx: '📘',
    js: '📒',
    jsx: '📒',
    py: '🐍',
    xml: '📋',
    css: '🎨',
    html: '🌐',
    json: '📦',
    md: '📝',
    yml: '⚙️',
    yaml: '⚙️',
    sql: '🗄️',
    go: '🔵',
    rs: '🦀',
    java: '☕',
  };
  return <span className="text-sm">{iconMap[ext] || '📄'}</span>;
}

export function FileChangeList({ files }: FileChangeListProps) {
  if (!files.length) {
    return <p className="text-gray-500 text-sm py-4">暂无变更文件信息</p>;
  }

  return (
    <div className="space-y-2">
      {files.map((file) => {
        const status = statusLabels[file.status] || statusLabels.modified;
        const riskColor =
          (file.risk_count ?? 0) > 1
            ? 'border-l-orange-500/60'
            : (file.risk_count ?? 0) > 0
              ? 'border-l-yellow-500/40'
              : 'border-l-transparent';

        return (
          <div
            key={file.filename}
            className={cn(
              'flex items-center gap-3 rounded-lg bg-white/[0.02] border border-gray-700/20 border-l-2 px-4 py-3 hover:bg-white/[0.04] transition-colors',
              riskColor,
            )}
          >
            <FileIcon filename={file.filename} />
            <span className="flex-1 text-sm font-mono text-gray-300 truncate">{file.filename}</span>
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${status.color}`}>
              {status.text}
            </span>
            <span className="text-xs text-emerald-400/80 font-mono min-w-[2.5rem] text-right">
              +{file.additions}
            </span>
            <span className="text-xs text-red-400/80 font-mono min-w-[2.5rem] text-right">
              -{file.deletions}
            </span>
            {(file.risk_count ?? 0) > 0 && (
              <span className="text-xs text-orange-400 bg-orange-950/30 rounded-full px-2 py-0.5 font-medium">
                {file.risk_count} 风险
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
