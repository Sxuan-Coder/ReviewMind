import type { ChangedFile } from '../types';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import {
  FileCode, FileText, FileJson, FileTerminal, File,
  Settings, Globe, Database, Palette,
} from 'lucide-react';

interface FileChangeListProps {
  files: ChangedFile[];
}

const statusLabels: Record<string, { text: string; variant: 'default' | 'secondary' | 'destructive' | 'outline'; className: string }> = {
  added: { text: '新增', variant: 'default', className: 'text-emerald-400 bg-emerald-950/30 border-emerald-500/20' },
  modified: { text: '修改', variant: 'secondary', className: 'text-amber-400 bg-amber-950/30 border-amber-500/20' },
  removed: { text: '删除', variant: 'destructive', className: 'text-red-400 bg-red-950/30 border-red-500/20' },
  renamed: { text: '重命名', variant: 'outline', className: 'text-purple-400 bg-purple-950/30 border-purple-500/20' },
};

function FileIcon({ filename }: { filename: string }) {
  const ext = filename.split('.').pop() || '';
  const iconClass = 'size-4';
  const iconMap: Record<string, React.ReactNode> = {
    ts: <FileCode className={cn(iconClass, 'text-blue-400')} />,
    tsx: <FileCode className={cn(iconClass, 'text-blue-400')} />,
    js: <FileCode className={cn(iconClass, 'text-yellow-400')} />,
    jsx: <FileCode className={cn(iconClass, 'text-yellow-400')} />,
    py: <FileTerminal className={cn(iconClass, 'text-green-400')} />,
    xml: <FileText className={cn(iconClass, 'text-orange-400')} />,
    css: <Palette className={cn(iconClass, 'text-pink-400')} />,
    html: <Globe className={cn(iconClass, 'text-red-400')} />,
    json: <FileJson className={cn(iconClass, 'text-yellow-300')} />,
    md: <FileText className={cn(iconClass, 'text-zinc-400')} />,
    yml: <Settings className={cn(iconClass, 'text-zinc-400')} />,
    yaml: <Settings className={cn(iconClass, 'text-zinc-400')} />,
    sql: <Database className={cn(iconClass, 'text-cyan-400')} />,
    go: <FileCode className={cn(iconClass, 'text-cyan-300')} />,
    rs: <FileCode className={cn(iconClass, 'text-orange-300')} />,
    java: <FileCode className={cn(iconClass, 'text-red-300')} />,
  };
  return <span className="flex items-center">{iconMap[ext] || <File className={cn(iconClass, 'text-zinc-500')} />}</span>;
}

export function FileChangeList({ files }: FileChangeListProps) {
  if (!files.length) {
    return <p className="text-zinc-600 text-sm py-4">暂无变更文件信息</p>;
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
              'flex items-center gap-3 rounded-lg bg-zinc-900/40 border border-zinc-800/60 border-l-2 px-4 py-3 hover:bg-zinc-800/30 transition-colors',
              riskColor,
            )}
          >
            <FileIcon filename={file.filename} />
            <span className="flex-1 text-sm font-mono text-zinc-300 truncate">{file.filename}</span>
            <Badge variant="outline" className={cn('text-xs font-medium', status.className)}>
              {status.text}
            </Badge>
            <span className="text-xs text-emerald-500 font-mono min-w-[2.5rem] text-right">
              +{file.additions}
            </span>
            <span className="text-xs text-red-500 font-mono min-w-[2.5rem] text-right">
              -{file.deletions}
            </span>
            {(file.risk_count ?? 0) > 0 && (
              <Badge variant="outline" className="text-xs text-orange-400 bg-orange-950/30 border-orange-500/20">
                {file.risk_count} 风险
              </Badge>
            )}
          </div>
        );
      })}
    </div>
  );
}