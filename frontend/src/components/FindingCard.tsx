import { cn } from '../lib/utils';
import { RiskBadge } from './RiskBadge';
import type { Finding } from '../types';

interface FindingCardProps {
  finding: Finding;
  expanded?: boolean;
  onToggle?: () => void;
}

const levelBorderColors: Record<string, string> = {
  CRITICAL: 'border-red-500/25',
  HIGH: 'border-orange-500/25',
  MEDIUM: 'border-yellow-500/25',
  LOW: 'border-blue-500/25',
  SUGGESTION: 'border-gray-500/25',
};

export function FindingCard({ finding, expanded = false, onToggle }: FindingCardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border bg-white/[0.03] p-5 transition-all hover:bg-white/[0.05]',
        levelBorderColors[finding.level] || 'border-gray-500/25',
      )}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <RiskBadge level={finding.level} />
          <span className="text-xs font-mono text-cyan-400/80 bg-cyan-950/30 px-2 py-0.5 rounded">
            {finding.type}
          </span>
          <span className="text-xs text-gray-500">{finding.agent}</span>
        </div>
        {onToggle && (
          <button
            onClick={onToggle}
            className="text-xs text-gray-500 hover:text-gray-300 shrink-0 transition-colors"
          >
            {expanded ? '收起' : '展开'}
          </button>
        )}
      </div>

      <div className="flex items-center gap-2 text-sm font-mono text-gray-400 mb-2">
        <span className="text-gray-500">{finding.file}</span>
        <span className="text-cyan-500/60">L{finding.line}</span>
        {finding.symbol && (
          <span className="text-purple-400/70 truncate">→ {finding.symbol}</span>
        )}
      </div>

      <p className="text-sm text-gray-300 leading-relaxed mb-3">{finding.description}</p>

      <div className="bg-emerald-950/20 border border-emerald-500/15 rounded-lg p-3">
        <span className="text-xs font-semibold text-emerald-400/80">建议: </span>
        <span className="text-sm text-emerald-300/80">{finding.suggestion}</span>
      </div>

      {expanded && finding.code_snippet && (
        <pre className="mt-3 rounded-lg bg-gray-950/70 border border-gray-700/30 p-3 text-xs font-mono text-gray-300 overflow-auto whitespace-pre-wrap">
          {finding.code_snippet}
        </pre>
      )}

      {finding.confidence > 0 && (
        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs text-gray-500">置信度</span>
          <div className="h-1.5 w-20 rounded-full bg-gray-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-cyan-500/60 transition-all"
              style={{ width: `${Math.round(finding.confidence * 100)}%` }}
            />
          </div>
          <span className="text-xs text-gray-500">{Math.round(finding.confidence * 100)}%</span>
        </div>
      )}
    </div>
  );
}
