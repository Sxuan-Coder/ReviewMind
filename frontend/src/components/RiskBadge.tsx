import type { RiskLevel } from '../types';

const levelStyles: Record<RiskLevel, string> = {
  CRITICAL: 'bg-red-950/60 text-red-400 border-red-500/30',
  HIGH: 'bg-orange-950/60 text-orange-400 border-orange-500/30',
  MEDIUM: 'bg-yellow-950/60 text-yellow-400 border-yellow-500/30',
  LOW: 'bg-blue-950/60 text-blue-400 border-blue-500/30',
  SUGGESTION: 'bg-gray-800 text-gray-400 border-gray-600/30',
};

export function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${levelStyles[level] || levelStyles.SUGGESTION}`}
    >
      {level}
    </span>
  );
}
