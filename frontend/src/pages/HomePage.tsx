import { FormEvent, useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Zap, Brain, FileText, GitPullRequest, Loader2, Search, ExternalLink, RefreshCw } from 'lucide-react';
import { createReviewJob, getJobList, getPrPreview, parsePrUrl, getHealth } from '../services/reviewApi';
import { useReviewStore } from '../store/reviewStore';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import type { PullRequestInfo, JobListItem } from '../types';

export function HomePage() {
  const [prUrl, setPrUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [preview, setPreview] = useState<PullRequestInfo | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  const [history, setHistory] = useState<JobListItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const navigate = useNavigate();
  const storeSetJob = useReviewStore((s) => s.setJob);

  useEffect(() => {
    getHealth()
      .then((res) => {
        if (res?.data?.status === 'ok' || res?.status === 'ok') setBackendOnline(true);
        else setBackendOnline(false);
      })
      .catch(() => setBackendOnline(false));
  }, []);

  const handlePreview = useCallback(async () => {
    setError(null);
    setPreview(null);
    if (!prUrl.trim()) {
      setError('请输入 GitHub PR URL');
      return;
    }
    if (!/^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/pull\/\d+/.test(prUrl.trim())) {
      setError('请输入有效的 GitHub PR URL');
      return;
    }
    setPreviewLoading(true);
    try {
      await parsePrUrl(prUrl.trim());
      const info = await getPrPreview(prUrl.trim());
      setPreview(info);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取 PR 信息失败');
    } finally {
      setPreviewLoading(false);
    }
  }, [prUrl]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!preview) {
      await handlePreview();
      return;
    }

    setLoading(true);
    try {
      const job = await createReviewJob({ pr_url: prUrl.trim() });
      storeSetJob(job);
      navigate(`/analysis/${job.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建任务失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  }

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await getJobList(1, 5);
      setHistory(res.items);
    } catch {
      // silent
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    setPreview(null);
  }, [prUrl]);

  const features = [
    { icon: Brain, title: '多 Agent 审查', desc: 'Summary、Security、Performance、Test 四大 Agent 协同分析' },
    { icon: Search, title: 'AST 上下文增强', desc: '精确定位变更方法，不只是看 Diff 行' },
    { icon: FileText, title: '结构化报告', desc: '风险等级、代码定位、修复建议、可复制 GitHub 评论' },
  ];

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <div className="relative z-10">
          {backendOnline !== null && (
            <div className="flex items-center gap-2 mb-4">
              <span
                className={`inline-block w-2 h-2 rounded-full ${backendOnline ? 'bg-zinc-400 shadow-[0_0_6px_rgba(161,161,170,0.4)]' : 'bg-red-400'}`}
              />
              <span className="text-xs text-muted-foreground">
                {backendOnline ? '后端服务正常' : '后端不可用'}
              </span>
            </div>
          )}

          <div className="eyebrow">AI PR Review Assistant</div>
          <h1>ReviewMind</h1>
          <p>
            输入 GitHub Pull Request 链接，系统自动拉取 Diff，
            通过 DiffFilter 降噪、AST 定位变更方法、LangGraph 编排多 Agent 审查，
            以 SSE 实时推送分析进度和风险发现，最终生成结构化 Review 报告与可复制的 GitHub 评论。
          </p>

          <form className="review-form" onSubmit={handleSubmit}>
            <Input
              aria-label="GitHub PR URL"
              onChange={(e) => setPrUrl(e.target.value)}
              placeholder="https://github.com/owner/repo/pull/101"
              required
              type="url"
              value={prUrl}
              className="flex-1 min-w-0 h-12 rounded-[10px] border-zinc-800/60 bg-zinc-950/70 text-foreground placeholder:text-muted-foreground/50 px-5 text-sm"
            />
            <Button
              disabled={loading || previewLoading}
              type="submit"
              className="h-12 rounded-[10px] px-6 bg-zinc-100 text-zinc-900 font-bold hover:bg-zinc-200 transition-colors border-0"
            >
              {loading ? (
                <><Loader2 className="size-4 animate-spin" /> 正在创建...</>
              ) : previewLoading ? (
                <><Loader2 className="size-4 animate-spin" /> 获取中...</>
              ) : preview ? (
                <><Zap className="size-4" /> 开始分析</>
              ) : (
                <><GitPullRequest className="size-4" /> 预览 PR</>
              )}
            </Button>
          </form>

          {error && <div className="error-text">{error}</div>}

          <AnimatePresence>
            {preview && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="mt-5 rounded-xl border border-zinc-800/60 bg-zinc-900/40 p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs text-muted-foreground font-mono">
                        {preview.owner}/{preview.repo}#{preview.number}
                      </span>
                      <span className="text-xs text-zinc-600">by {preview.author}</span>
                    </div>
                    <h3 className="text-base font-bold text-zinc-200 mb-2">{preview.title}</h3>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground">
                      <span>{preview.base_branch} ← {preview.head_branch}</span>
                      <span className="text-emerald-500">+{preview.additions}</span>
                      <span className="text-red-500">-{preview.deletions}</span>
                      <span>{preview.changed_files} 个文件变更</span>
                    </div>
                  </div>
                  <a href={preview.html_url} target="_blank" rel="noopener noreferrer" className="shrink-0">
                    <Button variant="outline" size="sm" className="border-zinc-800/60 text-muted-foreground hover:text-zinc-200">
                      <ExternalLink className="size-3" /> 查看 PR
                    </Button>
                  </a>
                </div>
                <p className="text-xs text-zinc-500 mt-3">确认信息无误后，点击「开始分析」启动 AI Review</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </section>

      <div className="mt-8 grid grid-cols-1 lg:grid-cols-3 gap-5">
        <section className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-3 gap-4">
          {features.map((item) => (
            <div
              key={item.title}
              className="rounded-lg border border-zinc-800/60 bg-zinc-900/40 p-5 hover:bg-zinc-800/30 transition-colors"
            >
              <item.icon className="size-5 text-zinc-400 mb-3" />
              <h3 className="font-semibold text-zinc-200 mb-2 text-sm">{item.title}</h3>
              <p className="text-xs text-zinc-500 leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </section>

        <section className="lg:col-span-1">
          <div className="rounded-lg border border-zinc-800/60 bg-zinc-900/40 overflow-hidden">
            <div className="flex flex-row items-center justify-between px-5 pt-5 pb-3">
              <span className="text-sm font-semibold text-zinc-200">历史记录</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={loadHistory}
                disabled={historyLoading}
                className="text-xs text-zinc-500 hover:text-zinc-200 h-7 px-2"
              >
                {historyLoading ? <Loader2 className="size-3 animate-spin" /> : <RefreshCw className="size-3" />}
                {historyLoading ? '加载中...' : '刷新'}
              </Button>
            </div>
            <div className="px-5 pb-5">
              {history.length === 0 ? (
                <p className="text-xs text-zinc-600 py-4 text-center">暂无记录，点击刷新加载</p>
              ) : (
                <div className="space-y-2">
                  {history.map((item) => (
                    <button
                      key={item.job_id}
                      onClick={() => navigate(`/report/${item.job_id}`)}
                      className="w-full text-left rounded-lg border border-zinc-800/40 bg-zinc-950/40 px-3 py-2.5 hover:bg-zinc-800/30 transition-colors"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs text-zinc-300 truncate flex-1">{item.pr_title}</span>
                        <Badge
                          variant="outline"
                          className={`shrink-0 text-xs ${
                            item.status === 'completed'
                              ? 'bg-emerald-950/30 text-emerald-400 border-emerald-500/20'
                              : 'bg-yellow-950/30 text-yellow-400 border-yellow-500/20'
                          }`}
                        >
                          {item.status === 'completed' ? '完成' : item.status}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-zinc-600">
                        <span>{item.risk_level}</span>
                        <span>{item.finding_count} 个风险</span>
                        <span>{new Date(item.created_at).toLocaleDateString('zh-CN')}</span>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}