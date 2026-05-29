import { FormEvent, useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { ProgressTimeline } from './components/ProgressTimeline';
import { RiskSummary } from './components/RiskSummary';
import { createReviewJob, getReviewReport } from './services/reviewApi';
import { useReviewStore } from './store/reviewStore';

export default function App() {
  const [prUrl, setPrUrl] = useState('');
  const { job, report, setJob, setReport } = useReviewStore();

  const createJobMutation = useMutation({
    mutationFn: createReviewJob,
    onSuccess: async (createdJob) => {
      setJob(createdJob);
      const nextReport = await getReviewReport(createdJob.job_id);
      setReport(nextReport);
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createJobMutation.mutate(prUrl);
  }

  return (
    <main className="app-shell">
      <section className="hero-panel">
        <div className="eyebrow">AI PR REVIEW ASSISTANT</div>
        <h1>ReviewMind</h1>
        <p>
          输入 GitHub Pull Request 链接，系统将按 DiffFilter、AST Context 与多 Agent
          工作流逐步生成结构化 Review 报告。
        </p>
        <form className="review-form" onSubmit={handleSubmit}>
          <input
            aria-label="GitHub PR URL"
            onChange={(event) => setPrUrl(event.target.value)}
            placeholder="https://github.com/owner/repo/pull/101"
            required
            type="url"
            value={prUrl}
          />
          <button disabled={createJobMutation.isPending} type="submit">
            {createJobMutation.isPending ? '创建中...' : '开始分析'}
          </button>
        </form>
        {createJobMutation.error ? <div className="error-text">创建任务失败，请检查后端服务。</div> : null}
      </section>

      <section className="dashboard-grid">
        <ProgressTimeline activeStep={job ? 'Report' : 'Fetch PR'} />
        <div className="report-card">
          <div className="section-label">Review Report</div>
          {report ? (
            <>
              <RiskSummary findingCount={report.findings.length} riskLevel={report.risk_level} />
              <p className="report-summary">{report.summary}</p>
              <pre className="comment-box">{report.review_comment}</pre>
            </>
          ) : (
            <p className="empty-state">提交 PR URL 后，这里会显示 Review 报告骨架。</p>
          )}
        </div>
      </section>
    </main>
  );
}