import { FormEvent, useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createReviewJob, getJobList, getPrPreview, parsePrUrl, getHealth } from '../services/reviewApi';
import { useReviewStore } from '../store/reviewStore';
import type { PullRequestInfo, JobListItem } from '../types';

export function HomePage() {
  const [prUrl, setPrUrl] = useState('');
  const [useMock, setUseMock] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ===== PR Preview =====
  const [preview, setPreview] = useState<PullRequestInfo | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  // ===== Health =====
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  // ===== History =====
  const [history, setHistory] = useState<JobListItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const navigate = useNavigate();
  const storeSetJob = useReviewStore((s) => s.setJob);
  const storeSetUseMock = useReviewStore((s) => s.setUseMock);

  // Health check on mount
  useEffect(() => {
    getHealth()
      .then((res) => {
        if (res?.data?.status === 'ok' || res?.status === 'ok') setBackendOnline(true);
        else setBackendOnline(false);
      })
      .catch(() => setBackendOnline(false));
  }, []);

  // PR preview
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
      // Fast URL parse for validation
      await parsePrUrl(prUrl.trim(), useMock);
      // Fetch full PR info
      const info = await getPrPreview(prUrl.trim(), useMock);
      setPreview(info);
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取 PR 信息失败');
    } finally {
      setPreviewLoading(false);
    }
  }, [prUrl, useMock]);

  // Start review
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!preview) {
      await handlePreview();
      return;
    }

    setLoading(true);
    try {
      storeSetUseMock(useMock);
      const job = await createReviewJob({ pr_url: prUrl.trim() }, useMock);
      storeSetJob(job);
      navigate(`/analysis/${job.job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建任务失败，请稍后重试');
    } finally {
      setLoading(false);
    }
  }

  // History
  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await getJobList(1, 5, useMock);
      setHistory(res.items);
    } catch {
      // silent
    } finally {
      setHistoryLoading(false);
    }
  }, [useMock]);

  // Dismiss preview when URL changes
  useEffect(() => {
    setPreview(null);
  }, [prUrl]);

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <div className="relative z-10">
          {/* Health indicator */}
          {backendOnline !== null && (
            <div className="flex items-center gap-2 mb-4">
              <span
                className={`inline-block w-2 h-2 rounded-full ${backendOnline ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.6)]' : 'bg-red-400'}`}
              />
              <span className="text-xs text-gray-500">
                {backendOnline ? '后端服务正常' : useMock ? 'Mock 模式（无需后端）' : '后端不可用'}
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
            <input
              aria-label="GitHub PR URL"
              onChange={(e) => setPrUrl(e.target.value)}
              placeholder="https://github.com/owner/repo/pull/101"
              required
              type="url"
              value={prUrl}
            />
            <label className="flex items-center space-x-2 text-sm bg-white/[0.04] px-3 py-2 rounded-lg border border-gray-600/20 cursor-pointer">
              <input
                type="checkbox"
                checked={useMock}
                onChange={(e) => setUseMock(e.target.checked)}
                className="rounded accent-cyan-500"
              />
              <span className="text-gray-400 text-xs whitespace-nowrap">Mock 模式</span>
            </label>
            <button disabled={loading || previewLoading} type="submit">
              {loading ? '正在创建...' : previewLoading ? '获取中...' : preview ? '开始分析' : '预览 PR'}
            </button>
          </form>

          {error && <div className="error-text">{error}</div>}

          {/* PR Preview Card */}
          {preview && (
            <div
              className="mt-6 rounded-2xl border border-cyan-500/20 bg-cyan-950/10 p-5 animate-slide-up"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs text-gray-500 font-mono">
                      {preview.owner}/{preview.repo}#{preview.number}
                    </span>
                    <span className="text-xs text-gray-600">by {preview.author}</span>
                  </div>
                  <h3 className="text-base font-bold text-gray-200 mb-2">{preview.title}</h3>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    <span>
                      {preview.base_branch} ← {preview.head_branch}
                    </span>
                    <span className="text-emerald-400/80">+{preview.additions}</span>
                    <span className="text-red-400/80">-{preview.deletions}</span>
                    <span>{preview.changed_files} 个文件变更</span>
                  </div>
                </div>
                <a
                  href={preview.html_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 rounded-lg border border-gray-600/30 px-3 py-1.5 text-xs text-gray-400 hover:text-gray-200 transition-colors"
                >
                  查看 PR →
                </a>
              </div>
              <p className="text-xs text-gray-500 mt-3">
                确认信息无误后，点击「开始分析」启动 AI Review
              </p>
            </div>
          )}
        </div>
      </section>

      <div className="mt-10 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Feature highlights */}
        <section className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-3 gap-5">
          {[
            { title: '多 Agent 审查', desc: 'Summary、Security、Performance、Test 四大 Agent 协同分析' },
            { title: 'AST 上下文增强', desc: '精确定位变更方法，不只是看 Diff 行' },
            { title: '结构化报告', desc: '风险等级、代码定位、修复建议、可复制 GitHub 评论' },
          ].map((item) => (
            <div
              key={item.title}
              className="rounded-2xl border border-gray-700/20 bg-white/[0.02] p-5 hover:bg-white/[0.04] transition-colors"
            >
              <h3 className="font-bold text-cyan-300/80 mb-2">{item.title}</h3>
              <p className="text-sm text-gray-500 leading-relaxed">{item.desc}</p>
            </div>
          ))}
        </section>

        {/* Recent jobs */}
        <section className="lg:col-span-1">
          <div className="rounded-2xl border border-gray-700/20 bg-white/[0.02] p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-bold text-cyan-300/80 text-sm">历史记录</h3>
              <button
                onClick={loadHistory}
                disabled={historyLoading}
                className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
              >
                {historyLoading ? '加载中...' : '刷新'}
              </button>
            </div>
            {history.length === 0 ? (
              <p className="text-xs text-gray-600 py-4 text-center">
                暂无记录，点击刷新加载
              </p>
            ) : (
              <div className="space-y-2">
                {history.map((item) => (
                  <button
                    key={item.job_id}
                    onClick={() => navigate(`/report/${item.job_id}`)}
                    className="w-full text-left rounded-lg border border-gray-700/20 bg-white/[0.01] px-3 py-2.5 hover:bg-white/[0.04] transition-colors"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs text-gray-300 truncate flex-1">{item.pr_title}</span>
                      <span
                        className={`shrink-0 rounded-full px-2 py-0.5 text-xs ${
                          item.status === 'completed'
                            ? 'bg-emerald-950/40 text-emerald-400'
                            : 'bg-yellow-950/40 text-yellow-400'
                        }`}
                      >
                        {item.status === 'completed' ? '完成' : item.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs text-gray-600">
                      <span>{item.risk_level}</span>
                      <span>{item.finding_count} 个风险</span>
                      <span>{new Date(item.created_at).toLocaleDateString('zh-CN')}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
