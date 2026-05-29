import { cn } from '@/lib/utils';
import { Progress } from '@/components/ui/progress';
import { Card, CardContent } from '@/components/ui/card';
import { motion } from 'framer-motion';
import { Check, Loader2 } from 'lucide-react';
import type { StepType, ReviewProgress } from '../types';

interface ProgressTimelineProps {
  progress: ReviewProgress | null;
  stepHistory: StepType[];
}

const STEP_DEFINITIONS: { key: StepType; label: string; description: string }[] = [
  { key: 'FETCH_PR', label: '拉取 PR', description: '获取 GitHub PR 信息与 Diff' },
  { key: 'DIFF_FILTER', label: '过滤 Diff', description: '过滤无效文件与锁文件' },
  { key: 'DIFF_PARSE', label: '解析 Diff', description: '解析新增/删除/变更行' },
  { key: 'AST_CONTEXT', label: 'AST 上下文', description: '定位变更方法与符号' },
  { key: 'SUMMARY_AGENT', label: '摘要分析', description: '总结 PR 业务意图与影响范围' },
  { key: 'SECURITY_AGENT', label: '安全审查', description: '分析 SQL 注入、XSS 等安全风险' },
  { key: 'PERFORMANCE_AGENT', label: '性能审查', description: '分析 N+1 查询、缓存等性能风险' },
  { key: 'TEST_AGENT', label: '测试审查', description: '分析测试覆盖与边界条件' },
  { key: 'RISK_JUDGE', label: '风险仲裁', description: '合并、去重、评分风险发现' },
  { key: 'REPORT_AGENT', label: '生成报告', description: '生成结构化 Review 报告' },
];

function stepStatus(
  stepKey: StepType,
  currentStep: StepType | undefined,
  stepHistory: StepType[],
): 'done' | 'active' | 'pending' {
  if (stepKey === currentStep) return 'active';
  if (stepHistory.includes(stepKey)) return 'done';
  return 'pending';
}

export function ProgressTimeline({ progress, stepHistory }: ProgressTimelineProps) {
  const currentStep = progress?.step;

  return (
    <Card className="timeline-card py-0 gap-0">
      <CardContent className="p-6">
        <div className="section-label">Agent Workflow</div>

        {progress && (
          <div className="mt-4 mb-5">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs text-zinc-500">{progress.message}</span>
              <span className="text-xs font-mono text-zinc-400">{progress.percent}%</span>
            </div>
            <Progress value={progress.percent} className="h-1.5" />
          </div>
        )}

        <div className="timeline-list">
          {STEP_DEFINITIONS.map((step, index) => {
            const status = stepStatus(step.key, currentStep, stepHistory);
            return (
              <motion.div
                className="timeline-item"
                key={step.key}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.2, delay: index * 0.03 }}
              >
                <span
                  className={cn(
                    'timeline-dot shrink-0',
                    status === 'active' && 'active animate-pulse-glow',
                    status === 'done' && 'bg-emerald-500/70 shadow-[0_0_10px_rgba(34,197,94,0.3)]',
                  )}
                />
                <div className="flex-1 min-w-0">
                  <span
                    className={cn(
                      'text-sm font-medium block truncate',
                      status === 'active' && 'text-zinc-200',
                      status === 'done' && 'text-zinc-500',
                      status === 'pending' && 'text-zinc-700',
                    )}
                  >
                    {step.label}
                  </span>
                  <span className="text-xs text-zinc-700 block truncate">{step.description}</span>
                </div>
                {status === 'done' && <Check className="size-3.5 text-emerald-500 shrink-0" />}
                {status === 'active' && (
                  <Loader2 className="size-3.5 text-zinc-400 shrink-0 animate-spin" />
                )}
              </motion.div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}