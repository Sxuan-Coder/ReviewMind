import type { RiskStats, OverallRiskLevel } from '../types';
import { cn } from '../lib/utils';

interface RiskSummaryProps {
  riskLevel: OverallRiskLevel | undefined;
  stats: RiskStats | undefined;
}

const riskLevelMeta: Record<
  OverallRiskLevel,
  { label: string; color: string; bg: string; border: string }
> = {
  CRITICAL: {
    label: '严重风险',
    color: 'text-red-400',
    bg: 'bg-red-950/40',
    border: 'border-red-500/30',
  },
  HIGH: {
    label: '高风险',
    color: 'text-orange-400',
    bg: 'bg-orange-950/40',
    border: 'border-orange-500/30',
  },
  MEDIUM: {
    label: '中等风险',
    color: 'text-yellow-400',
    bg: 'bg-yellow-950/40',
    border: 'border-yellow-500/30',
  },
  LOW: {
    label: '低风险',
    color: 'text-blue-400',
    bg: 'bg-blue-950/40',
    border: 'border-blue-500/30',
  },
  PASS: {
    label: '无风险',
    color: 'text-emerald-400',
    bg: 'bg-emerald-950/40',
    border: 'border-emerald-500/30',
  },
};

const statItems: { key: keyof RiskStats; label: string; color: string }[] = [
  { key: 'critical', label: '严重', color: 'text-red-400' },
  { key: 'high', label: '高危', color: 'text-orange-400' },
  { key: 'medium', label: '中等', color: 'text-yellow-400' },
  { key: 'low', label: '低危', color: 'text-blue-400' },
  { key: 'suggestion', label: '建议', color: 'text-gray-400' },
];

export function RiskSummary({ riskLevel, stats }: RiskSummaryProps) {
  const meta = riskLevel ? riskLevelMeta[riskLevel] : riskLevelMeta.PASS;

  return (
    <div className="space-y-4">
      {/* Overall risk level */}
      <div
        className={cn(
          'rounded-xl border p-5',
          meta.bg,
          meta.border,
        )}
      >
        <span className="text-xs text-gray-400 block mb-1">综合风险等级</span>
        <span className={cn('text-2xl font-bold', meta.color)}>{meta.label}</span>
        <span className="text-sm text-gray-500 ml-2">{riskLevel}</span>
      </div>

      {/* Stats grid */}
      {stats && (
        <div className="grid grid-cols-5 gap-2">
          {statItems.map(({ key, label, color }) => (
            <div
              key={key}
              className="rounded-lg bg-white/[0.02] border border-gray-700/20 p-3 text-center"
            >
              <span className={cn('text-lg font-bold block', color)}>{stats[key]}</span>
              <span className="text-xs text-gray-500">{label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
