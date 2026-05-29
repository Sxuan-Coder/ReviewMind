import { FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createReviewJob } from '../services/reviewApi';
import { useReviewStore } from '../store/reviewStore';

export function HomePage() {
  const [prUrl, setPrUrl] = useState('');
  const [useMock, setUseMock] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const storeSetJob = useReviewStore((s) => s.setJob);
  const storeSetUseMock = useReviewStore((s) => s.setUseMock);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!prUrl.trim()) {
      setError('请输入 GitHub PR URL');
      return;
    }

    // Basic URL validation
    if (!/^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/pull\/\d+/.test(prUrl.trim())) {
      setError('请输入有效的 GitHub PR URL，例如 https://github.com/owner/repo/pull/101');
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

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <div className="relative z-10">
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
            <button disabled={loading} type="submit">
              {loading ? '正在创建...' : '开始分析'}
            </button>
          </form>

          {error && <div className="error-text">{error}</div>}
        </div>
      </section>

      {/* Feature highlights */}
      <section className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-5">
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
    </main>
  );
}
