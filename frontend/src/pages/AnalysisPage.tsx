import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2, Clock, AlertTriangle, Wifi, XCircle, CheckCircle2, Ban, ArrowLeft, FileText } from 'lucide-react';
import { useReviewStream } from '../hooks/useReviewStream';
import { useReviewStore } from '../store/reviewStore';
import { getJobDetail, cancelJob as cancelJobApi } from '../services/reviewApi';
import { ProgressTimeline } from '../components/ProgressTimeline';
import { FindingCard } from '../components/FindingCard';
import { NavHeader } from '../components/NavHeader';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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

  useEffect(() => {
    if (!jobId) return;
    getJobDetail(jobId, useMock)
      .then((d) => {
        if (d.pr) setPrInfo(d.pr);
      })
      .catch(() => {});
  }, [jobId, useMock]);

  useEffect(() => {
    if (!store.startedAt) return;
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - (store.startedAt ?? Date.now())) / 1000));
    }, 200);
    return () => clearInterval(timer);
  }, [store.startedAt]);

  useEffect(() => {
    if (store.jobStatus === 'completed' && jobId) {
      const fetchAndGo = async () => {
        try {
          const detail = await getJobDetail(jobId, useMock);
          store.setDetail(detail);
          navigate(`/report/${jobId}`);
        } catch (err) {
          console.error('获取报告失败:', err);
          store.setJobStatus('failed');
          store.setSSEStatus('error');
          // 不跳转，留在当前页面显示错误
        }
      };
      const t = setTimeout(fetchAndGo, 800);
      return () => clearTimeout(t);
    }
  }, [store.jobStatus, jobId, navigate, useMock]);

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

      {prInfo && (
        <Card className="report-card mb-5 py-0 gap-0">
          <CardContent className="p-5 flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-muted-foreground font-mono">
                  {prInfo.owner}/{prInfo.repo}#{prInfo.number}
                </span>
                <span className="text-xs text-zinc-600">by {prInfo.author}</span>
              </div>
              <h2 className="text-lg font-bold text-zinc-200 truncate">{prInfo.title}</h2>
              <div className="flex items-center gap-4 mt-1.5 text-xs text-muted-foreground">
                <span>{prInfo.base_branch} ← {prInfo.head_branch}</span>
                <span className="text-emerald-500">+{prInfo.additions}</span>
                <span className="text-red-500">-{prInfo.deletions}</span>
                <span>{prInfo.changed_files} 个文件</span>
              </div>
            </div>
            <a href={prInfo.html_url} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="sm" className="border-zinc-800/60 text-muted-foreground hover:text-zinc-200">
                查看 PR →
              </Button>
            </a>
          </CardContent>
        </Card>
      )}

      <div className="dashboard-grid">
        <div className="md:col-span-1">
          <ProgressTimeline progress={store.progress} stepHistory={store.stepHistory} />

          <Card className="timeline-card mt-4 py-0 gap-0">
            <CardContent className="p-6">
              <div className="section-label">分析状态</div>
              <div className="mt-3 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-500 flex items-center gap-1.5"><Clock className="size-3" /> 已耗时</span>
                  <span className="font-mono text-zinc-300">{elapsed}s</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-500 flex items-center gap-1.5"><AlertTriangle className="size-3" /> 已发现风险</span>
                  <span className="font-mono text-orange-400">{store.findings.length}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-zinc-500 flex items-center gap-1.5"><Wifi className="size-3" /> 连接状态</span>
                  <Badge
                    variant="outline"
                    className={`font-mono text-xs ${
                      store.sseStatus === 'connected'
                        ? 'text-emerald-400 border-emerald-500/20 bg-emerald-950/20'
                        : 'text-zinc-500'
                    }`}
                  >
                    {store.sseStatus}
                  </Badge>
                </div>
              </div>

              {isActive && (
                <Button
                  variant="outline"
                  onClick={handleCancel}
                  disabled={cancelling}
                  className="mt-4 w-full border-red-500/20 bg-red-950/20 text-red-400 hover:bg-red-950/40 hover:text-red-300"
                >
                  {cancelling ? <Loader2 className="size-3 animate-spin" /> : <XCircle className="size-3" />}
                  {cancelling ? '取消中...' : '取消分析'}
                </Button>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="md:col-span-3 report-card space-y-5">
          <div className="section-label">实时分析</div>

          <AnimatePresence>
            {summaryText && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-5"
              >
                <h3 className="text-sm font-semibold text-zinc-200 mb-2">PR 摘要</h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  {summaryText}
                  {store.progress && store.progress.step === 'SUMMARY_AGENT' && (
                    <span className="inline-block w-1.5 h-4 bg-zinc-400 ml-0.5 animate-pulse align-middle" />
                  )}
                </p>
              </motion.div>
            )}
          </AnimatePresence>

          {store.findings.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-orange-400 mb-3">
                已发现风险 ({store.findings.length})
              </h3>
              <div className="space-y-3">
                {store.findings.map((f) => (
                  <motion.div
                    key={f.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <FindingCard
                      finding={f}
                      expanded={expandedFindings.has(f.id)}
                      onToggle={() => toggleFinding(f.id)}
                    />
                  </motion.div>
                ))}
              </div>
            </div>
          )}

          {store.findings.length === 0 && !summaryText && isActive && (
            <div className="flex flex-col items-center justify-center p-12 text-zinc-500">
              <Loader2 className="size-10 text-zinc-600 animate-spin mb-4" />
              <p>AI 正在分析 PR 变更内容...</p>
              <p className="text-xs mt-2 text-zinc-700">这可能需要几十秒，请耐心等待</p>
            </div>
          )}

          {/* 实时文件列表 */}
          {store.fileList.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-5"
            >
              <h3 className="text-sm font-semibold text-zinc-200 mb-3">
                变更文件 ({store.fileList.length})
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-64 overflow-y-auto">
                {store.fileList.map((filename) => (
                  <div
                    key={filename}
                    className="flex items-center gap-2 px-3 py-1.5 rounded bg-zinc-950/40 border border-zinc-800/30 text-xs font-mono text-zinc-400"
                  >
                    <FileText className="size-3 text-zinc-600 shrink-0" />
                    <span className="truncate">{filename}</span>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          <AnimatePresence>
            {isDone && (
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="rounded-xl border border-emerald-500/20 bg-emerald-950/10 p-5 text-center"
              >
                <CheckCircle2 className="size-8 text-emerald-400 mx-auto mb-2" />
                <p className="text-emerald-400 font-bold">分析完成</p>
                <p className="text-sm text-zinc-500 mt-1">
                  共发现 {store.findings.length} 个风险，正在跳转到报告页...
                </p>
              </motion.div>
            )}
          </AnimatePresence>

          {isCancelled && (
            <div className="rounded-xl border border-yellow-500/20 bg-yellow-950/10 p-5 text-center">
              <Ban className="size-8 text-yellow-400 mx-auto mb-2" />
              <p className="text-yellow-400 font-bold">分析已取消</p>
              <Button
                variant="outline"
                onClick={() => navigate('/')}
                className="mt-3 border-zinc-800/60 bg-zinc-900/40 text-zinc-400 hover:text-zinc-200"
              >
                <ArrowLeft className="size-3" /> 返回首页
              </Button>
            </div>
          )}

          {isFailed && (
            <div className="rounded-xl border border-red-500/20 bg-red-950/10 p-5 text-center">
              <XCircle className="size-8 text-red-400 mx-auto mb-2" />
              <p className="text-red-400 font-bold">分析失败</p>
              <p className="text-sm text-zinc-500 mt-1">任务执行异常，请返回首页重试</p>
              <Button
                variant="outline"
                onClick={() => navigate('/')}
                className="mt-3 border-zinc-800/60 bg-zinc-900/40 text-zinc-400 hover:text-zinc-200"
              >
                <ArrowLeft className="size-3" /> 返回首页
              </Button>
            </div>
          )}

          {store.sseStatus === 'error' && (
            <div className="rounded-xl border border-red-500/20 bg-red-950/10 p-5 text-center">
              <XCircle className="size-8 text-red-400 mx-auto mb-2" />
              <p className="text-red-400 font-bold">SSE 连接异常</p>
              <p className="text-sm text-zinc-500 mt-1">
                无法实时获取分析进度，可能原因：
              </p>
              <ul className="text-xs text-zinc-600 mt-2 space-y-1 text-left max-w-xs mx-auto">
                <li>• 后端服务未启动或不可达</li>
                <li>• 网络连接不稳定</li>
                <li>• API 配置信息缺失（检查 GITHUB_TOKEN / LLM_API_KEY）</li>
              </ul>
              <div className="flex items-center justify-center gap-3 mt-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.location.reload()}
                  className="border-zinc-800/60 bg-zinc-900/40 text-zinc-400 hover:text-zinc-200"
                >
                  刷新页面
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate('/')}
                  className="border-zinc-800/60 bg-zinc-900/40 text-zinc-400 hover:text-zinc-200"
                >
                  <ArrowLeft className="size-3" /> 返回首页
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}