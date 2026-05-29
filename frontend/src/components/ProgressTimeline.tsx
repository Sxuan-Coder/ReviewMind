import { cn } from '../lib/utils';
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
    <div className="timeline-card">
      <div className="section-label">Agent Workflow</div>

      {/* Progress bar */}
      {progress && (
        <div className="mt-4 mb-5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-gray-500">{progress.message}</span>
            <span className="text-xs font-mono text-cyan-400">{progress.percent}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-gray-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-emerald-400 transition-all duration-700 ease-out"
              style={{ width: `${progress.percent}%` }}
            />
          </div>
        </div>
      )}

      {/* Step list */}
      <div className="timeline-list">
        {STEP_DEFINITIONS.map((step) => {
          const status = stepStatus(step.key, currentStep, stepHistory);
          return (
            <div className="timeline-item" key={step.key}>
              <span
                className={cn(
                  'timeline-dot shrink-0',
                  status === 'active' && 'active animate-pulse-glow',
                  status === 'done' && 'bg-emerald-500/80 shadow-[0_0_12px_rgba(34,197,94,0.4)]',
                )}
              />
              <div className="flex-1 min-w-0">
                <span
                  className={cn(
                    'text-sm font-medium block truncate',
                    status === 'active' && 'text-cyan-300',
                    status === 'done' && 'text-gray-400',
                    status === 'pending' && 'text-gray-600',
                  )}
                >
                  {step.label}
                </span>
                <span className="text-xs text-gray-600 block truncate">{step.description}</span>
              </div>
              {status === 'done' && <span className="text-emerald-500 text-xs shrink-0">✓</span>}
              {status === 'active' && (
                <span className="flex items-center gap-1 shrink-0">
                  <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
