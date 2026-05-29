import type { RiskStats, OverallRiskLevel } from '../types';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { motion } from 'framer-motion';

interface RiskSummaryProps {
  riskLevel: OverallRiskLevel | undefined;
  stats: RiskStats | undefined;
}

const riskLevelMeta: Record<
  OverallRiskLevel,
  { label: string; color: string; bg: string; border: string }
> = {
  CRITICAL: { label: '严重风险', color: 'text-red-400', bg: 'bg-red-950/30', border: 'border-red-500/20' },
  HIGH: { label: '高风险', color: 'text-orange-400', bg: 'bg-orange-950/30', border: 'border-orange-500/20' },
  MEDIUM: { label: '中等风险', color: 'text-yellow-400', bg: 'bg-yellow-950/30', border: 'border-yellow-500/20' },
  LOW: { label: '低风险', color: 'text-blue-400', bg: 'bg-blue-950/30', border: 'border-blue-500/20' },
  PASS: { label: '无风险', color: 'text-emerald-400', bg: 'bg-emerald-950/30', border: 'border-emerald-500/20' },
};

const statItems: { key: keyof RiskStats; label: string; color: string }[] = [
  { key: 'critical', label: '严重', color: 'text-red-400' },
  { key: 'high', label: '高危', color: 'text-orange-400' },
  { key: 'medium', label: '中等', color: 'text-yellow-400' },
  { key: 'low', label: '低危', color: 'text-blue-400' },
  { key: 'suggestion', label: '建议', color: 'text-zinc-400' },
];

function AnimatedNumber({ value }: { value: number }) {
  return (
    <motion.span
      key={value}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
    >
      {value}
    </motion.span>
  );
}

export function RiskSummary({ riskLevel, stats }: RiskSummaryProps) {
  const meta = riskLevel ? riskLevelMeta[riskLevel] : riskLevelMeta.PASS;

  return (
    <div className="space-y-4">
      <div className={cn('rounded-xl border p-5', meta.bg, meta.border)}>
        <span className="text-xs text-zinc-500 block mb-1">综合风险等级</span>
        <span className={cn('text-2xl font-bold', meta.color)}>{meta.label}</span>
        <span className="text-sm text-zinc-500 ml-2">{riskLevel}</span>
      </div>

      {stats && (
        <div className="grid grid-cols-5 gap-2">
          {statItems.map(({ key, label, color }) => (
            <Card key={key} className="bg-zinc-900/40 border-zinc-800/60 py-2 gap-0">
              <CardContent className="p-3 text-center">
                <span className={cn('text-lg font-bold block', color)}>
                  <AnimatedNumber value={stats[key]} />
                </span>
                <span className="text-xs text-zinc-600">{label}</span>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}