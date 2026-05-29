import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useReviewStream } from '../hooks/useReviewStream';
import { useReviewStore } from '../store/reviewStore';
import { getJobDetail, cancelJob as cancelJobApi } from '../services/reviewApi';
import { ProgressTimeline } from '../components/ProgressTimeline';
import { FindingCard } from '../components/FindingCard';
import { NavHeader } from '../components/NavHeader';
import type { PullRequestInfo } from '../types';

export function AnalysisPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const useMock = useReviewStore((s) => s.useMock);
  const store = useReviewStream(jobId, useMock);

  const [expandedFindings, setExpandedFindings] = useState<Set<string>>(new Set());
  const [elapsed, setElapsed] = useState(0);
  const [cancelling, setCancelling] = useState(false);
  const [prInfo, setPrInfo] = useState<PullRequestInfo | null>(null);

  // Fetch PR info on mount
  useEffect(() => {
    if (!jobId) return;
    getJobDetail(jobId, useMock)
      .then((d) => {
        if (d.pr) setPrInfo(d.pr);
      })
      .catch(() => {});
  }, [jobId, useMock]);

  // Elapsed timer
  useEffect(() => {
    if (!store.startedAt) return;
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - (store.startedAt ?? Date.now())) / 1000));
    }, 200);
    return () => clearInterval(timer);
  }, [store.startedAt]);

  // Navigate to report when done
  useEffect(() => {
    if (store.jobStatus === 'completed' && jobId) {
      const fetchAndGo = async () => {
        try {
          const detail = await getJobDetail(jobId, useMock);
          store.setDetail(detail);
        } catch {
          // ignore
        }
        navigate(`/report/${jobId}`);
      };
      const t = setTimeout(fetchAndGo, 800);
      return () => clearTimeout(t);
    }
  }, [store.jobStatus, jobId, navigate, useMock]);

  // Cancel
  const handleCancel = useCallback(async () => {
    if (!jobId || cancelling) return;
    setCancelling(true);
    try {
      await cancelJobApi(jobId, useMock);
      store.setJobStatus('cancelled');
      store.setSSEStatus('disconnected');
    } catch {
      setCancelling(false);
    }
  }, [jobId, useMock, cancelling]);

  function toggleFinding(id: string) {
    setExpandedFindings((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const summaryText = store.summaryChunks.join('');
  const isActive = store.jobStatus === 'running' || store.jobStatus === 'pending';
  const isDone = store.jobStatus === 'completed';
  const isCancelled = store.jobStatus === 'cancelled';
  const isFailed = store.jobStatus === 'failed';

  return (
    <div className="app-shell">
      <NavHeader title={`Job: ${jobId}`} />

      {/* PR Info Header */}
      {prInfo && (
        <div className="report-card mb-6 flex flex-wrap items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs text-gray-500 font-mono">
                {prInfo.owner}/{prInfo.repo}#{prInfo.number}
              </span>
              <span className="text-xs text-gray-600">by {prInfo.author}</span>
            </div>
            <h2 className="text-lg font-bold text-gray-200 truncate">{prInfo.title}</h2>
            <div className="flex items-center gap-4 mt-1.5 text-xs text-gray-500">
              <span>
                {prInfo.base_branch} ← {prInfo.head_branch}
              </span>
              <span className="text-emerald-400/80">+{prInfo.additions}</span>
              <span className="text-red-400/80">-{prInfo.deletions}</span>
              <span>{prInfo.changed_files} 个文件</span>
            </div>
          </div>
          <a
            href={prInfo.html_url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 rounded-lg border border-gray-600/30 px-4 py-2 text-xs text-gray-400 hover:text-gray-200 transition-colors"
          >
            查看 PR →
          </a>
        </div>
      )}

      <div className="dashboard-grid">
        {/* Left column: Timeline */}
        <div className="md:col-span-1">
          <ProgressTimeline progress={store.progress} stepHistory={store.stepHistory} />

          {/* Status card */}
          <div className="timeline-card mt-5">
            <div className="section-label">分析状态</div>
            <div className="mt-3 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">已耗时</span>
                <span className="font-mono text-cyan-400">{elapsed}s</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">已发现风险</span>
                <span className="font-mono text-orange-400">{store.findings.length}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">连接状态</span>
                <span
                  className={`font-mono ${store.sseStatus === 'connected' ? 'text-emerald-400' : 'text-gray-500'}`}
                >
                  {store.sseStatus}
                </span>
              </div>
            </div>

            {/* Cancel button */}
            {isActive && (
              <button
                onClick={handleCancel}
                disabled={cancelling}
                className="mt-4 w-full rounded-lg border border-red-500/25 bg-red-950/20 px-3 py-2 text-xs text-red-400 hover:bg-red-950/40 transition-colors disabled:opacity-50"
              >
                {cancelling ? '取消中...' : '取消分析'}
              </button>
            )}
          </div>
        </div>

        {/* Right column: Live content */}
        <div className="md:col-span-3 report-card space-y-5">
          <div className="section-label">实时分析</div>

          {/* Streaming summary */}
          {summaryText && (
            <div className="rounded-xl border border-cyan-500/15 bg-cyan-950/10 p-5">
              <h3 className="text-sm font-bold text-cyan-400 mb-2">PR 摘要</h3>
              <p className="text-sm text-gray-300 leading-relaxed">
                {summaryText}
                {store.progress && store.progress.step === 'SUMMARY_AGENT' && (
                  <span className="inline-block w-1.5 h-4 bg-cyan-400 ml-0.5 animate-pulse align-middle" />
                )}
              </p>
            </div>
          )}

          {/* Live findings */}
          {store.findings.length > 0 && (
            <div>
              <h3 className="text-sm font-bold text-orange-400 mb-3">
                已发现风险 ({store.findings.length})
              </h3>
              <div className="space-y-3">
                {store.findings.map((f) => (
                  <FindingCard
                    key={f.id}
                    finding={f}
                    expanded={expandedFindings.has(f.id)}
                    onToggle={() => toggleFinding(f.id)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Loading placeholder */}
          {store.findings.length === 0 && !summaryText && isActive && (
            <div className="flex flex-col items-center justify-center p-12 text-gray-500">
              <div className="w-12 h-12 border-4 border-cyan-500/20 border-t-cyan-400 rounded-full animate-spin mb-4" />
              <p>AI 正在分析 PR 变更内容...</p>
              <p className="text-xs mt-2 text-gray-600">这可能需要几十秒，请耐心等待</p>
            </div>
          )}

          {/* Done state */}
          {isDone && (
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/10 p-5 text-center">
              <p className="text-emerald-400 font-bold">分析完成</p>
              <p className="text-sm text-gray-400 mt-1">
                共发现 {store.findings.length} 个风险，正在跳转到报告页...
              </p>
            </div>
          )}

          {/* Cancelled state */}
          {isCancelled && (
            <div className="rounded-xl border border-yellow-500/20 bg-yellow-950/10 p-5 text-center">
              <p className="text-yellow-400 font-bold">分析已取消</p>
              <button
                onClick={() => navigate('/')}
                className="mt-3 rounded-lg border border-cyan-500/25 bg-cyan-950/30 px-4 py-2 text-sm text-cyan-400 hover:bg-cyan-950/50 transition-colors"
              >
                返回首页
              </button>
            </div>
          )}

          {/* Failed state */}
          {isFailed && (
            <div className="rounded-xl border border-red-500/20 bg-red-950/10 p-5 text-center">
              <p className="text-red-400 font-bold">分析失败</p>
              <p className="text-sm text-gray-400 mt-1">任务执行异常，请返回首页重试</p>
              <button
                onClick={() => navigate('/')}
                className="mt-3 rounded-lg border border-cyan-500/25 bg-cyan-950/30 px-4 py-2 text-sm text-cyan-400 hover:bg-cyan-950/50 transition-colors"
              >
                返回首页
              </button>
            </div>
          )}

          {/* Error state */}
          {store.sseStatus === 'error' && (
            <div className="rounded-xl border border-red-500/20 bg-red-950/10 p-5 text-center">
              <p className="text-red-400 font-bold">连接异常</p>
              <p className="text-sm text-gray-400 mt-1">SSE 连接中断，请刷新页面重试</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
