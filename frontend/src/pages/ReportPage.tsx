import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useReviewStore } from '../store/reviewStore';
import { getJobDetail } from '../services/reviewApi';
import { RiskSummary } from '../components/RiskSummary';
import { FindingCard } from '../components/FindingCard';
import { FileChangeList } from '../components/FileChangeList';
import { ReviewCommentBox } from '../components/ReviewCommentBox';
import { NavHeader } from '../components/NavHeader';
import type { JobDetailResponse } from '../types';
import { cn } from '../lib/utils';

type ReportTab = 'overview' | 'findings' | 'files' | 'symbols';

export function ReportPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const useMock = useReviewStore((s) => s.useMock);
  const storeDetail = useReviewStore((s) => s.detail);

  const [detail, setDetail] = useState<JobDetailResponse | null>(storeDetail);
  const [loading, setLoading] = useState(!detail);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ReportTab>('overview');
  const [expandedFindings, setExpandedFindings] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (detail) return;
    if (!jobId) {
      setError('缺少 Job ID');
      setLoading(false);
      return;
    }

    getJobDetail(jobId, useMock)
      .then((data) => {
        setDetail(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : '加载报告失败');
        setLoading(false);
      });
  }, [jobId, useMock, detail]);

  function toggleFinding(id: string) {
    setExpandedFindings((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  if (loading) {
    return (
      <div className="app-shell">
        <NavHeader />
        <div className="flex flex-col items-center justify-center p-24 text-gray-500">
          <div className="w-12 h-12 border-4 border-cyan-500/20 border-t-cyan-400 rounded-full animate-spin mb-4" />
          <p>正在加载报告...</p>
        </div>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="app-shell">
        <NavHeader />
        <div className="report-card p-12 text-center">
          <p className="text-red-400 text-lg mb-4">{error || '报告未找到'}</p>
          <button
            onClick={() => navigate('/')}
            className="rounded-lg border border-cyan-500/25 bg-cyan-950/30 px-4 py-2 text-sm text-cyan-400 hover:bg-cyan-950/50 transition-colors"
          >
            返回首页
          </button>
        </div>
      </div>
    );
  }

  const report = detail.report;
  const pr = detail.pr;

  const tabs: { key: ReportTab; label: string; count?: number }[] = [
    { key: 'overview', label: '概览' },
    { key: 'findings', label: '风险发现', count: report?.findings?.length ?? 0 },
    { key: 'files', label: '变更文件', count: report?.changed_files?.length ?? 0 },
    { key: 'symbols', label: '变更方法', count: report?.changed_symbols?.length ?? 0 },
  ];

  return (
    <div className="app-shell">
      <NavHeader />

      {/* PR Info Header */}
      {pr && (
        <div className="report-card mb-6 flex flex-wrap items-center justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs text-gray-500 font-mono">
                {pr.owner}/{pr.repo}#{pr.number}
              </span>
              <span className="text-xs text-gray-600">by {pr.author}</span>
            </div>
            <h2 className="text-xl font-bold text-gray-200 truncate">{pr.title}</h2>
            <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
              <span>
                {pr.base_branch} ← {pr.head_branch}
              </span>
              <span className="text-emerald-400/80">+{pr.additions}</span>
              <span className="text-red-400/80">-{pr.deletions}</span>
              <span>{pr.changed_files} 个文件</span>
            </div>
          </div>
          <a
            href={pr.html_url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 rounded-lg border border-gray-600/30 px-4 py-2 text-xs text-gray-400 hover:text-gray-200 hover:bg-white/[0.04] transition-colors"
          >
            查看 PR →
          </a>
        </div>
      )}

      <div className="dashboard-grid">
        {/* Left column: Risk summary */}
        <div className="md:col-span-1">
          <RiskSummary riskLevel={report?.risk_level} stats={report?.stats} />

          {/* Job meta */}
          <div className="timeline-card mt-5">
            <div className="section-label">任务信息</div>
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Job ID</span>
                <span className="font-mono text-gray-400">{detail.job_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">状态</span>
                <span className="text-emerald-400">{detail.status}</span>
              </div>
              {detail.created_at && (
                <div className="flex justify-between">
                  <span className="text-gray-500">创建时间</span>
                  <span className="font-mono text-gray-500 text-xs">
                    {new Date(detail.created_at).toLocaleString('zh-CN')}
                  </span>
                </div>
              )}
              {detail.completed_at && (
                <div className="flex justify-between">
                  <span className="text-gray-500">完成时间</span>
                  <span className="font-mono text-gray-500 text-xs">
                    {new Date(detail.completed_at).toLocaleString('zh-CN')}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right column: Report content */}
        <div className="md:col-span-3 report-card">
          {/* Tabs */}
          <div className="flex items-center gap-1 mb-6 border-b border-gray-700/30 pb-0 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={cn(
                  'px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors whitespace-nowrap',
                  activeTab === tab.key
                    ? 'text-cyan-400 border-b-2 border-cyan-400 -mb-[1px] bg-cyan-950/10'
                    : 'text-gray-500 hover:text-gray-300',
                )}
              >
                {tab.label}
                {tab.count !== undefined && (
                  <span className="ml-1.5 text-xs text-gray-600">({tab.count})</span>
                )}
              </button>
            ))}
          </div>

          {/* Tab: Overview */}
          {activeTab === 'overview' && report && (
            <div className="space-y-6 animate-fade-in">
              <div>
                <h3 className="section-label mb-3">PR 摘要</h3>
                <p className="report-summary">{report.summary}</p>
              </div>

              {report.changed_symbols && report.changed_symbols.length > 0 && (
                <div>
                  <h3 className="section-label mb-3">核心变更方法</h3>
                  <div className="space-y-2">
                    {report.changed_symbols.slice(0, 5).map((sym) => (
                      <div
                        key={sym.symbol}
                        className="rounded-lg bg-white/[0.02] border border-gray-700/20 px-4 py-3"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-mono text-purple-400">{sym.symbol}</span>
                          <span className="text-xs text-gray-600">{sym.language}</span>
                        </div>
                        <span className="text-xs text-gray-500 font-mono">
                          {sym.file} L{sym.start_line}-L{sym.end_line}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <ReviewCommentBox content={report.review_comment} />
            </div>
          )}

          {/* Tab: Findings */}
          {activeTab === 'findings' && report && (
            <div className="space-y-3 animate-fade-in">
              {report.findings.length === 0 ? (
                <p className="empty-state text-center py-8">未发现风险，PR 质量良好</p>
              ) : (
                report.findings.map((f) => (
                  <FindingCard
                    key={f.id}
                    finding={f}
                    expanded={expandedFindings.has(f.id)}
                    onToggle={() => toggleFinding(f.id)}
                  />
                ))
              )}
            </div>
          )}

          {/* Tab: Files */}
          {activeTab === 'files' && report && (
            <div className="animate-fade-in">
              <FileChangeList files={report.changed_files} />
            </div>
          )}

          {/* Tab: Symbols */}
          {activeTab === 'symbols' && report && (
            <div className="animate-fade-in">
              {report.changed_symbols.length === 0 ? (
                <p className="empty-state text-center py-8">暂无可识别的变更方法</p>
              ) : (
                <div className="space-y-3">
                  {report.changed_symbols.map((sym) => (
                    <div
                      key={`${sym.file}:${sym.symbol}`}
                      className="rounded-xl border border-gray-700/20 bg-white/[0.02] p-5"
                    >
                      <div className="flex items-center gap-3 mb-3">
                        <span className="text-sm font-bold text-purple-400">{sym.symbol}</span>
                        <span className="rounded bg-purple-950/30 px-2 py-0.5 text-xs text-purple-400/70">
                          {sym.language}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500 font-mono mb-2">
                        {sym.file} · L{sym.start_line}–L{sym.end_line}
                      </div>
                      {sym.changed_lines.length > 0 && (
                        <div className="flex items-center gap-1 flex-wrap">
                          <span className="text-xs text-gray-600 mr-1">变更行:</span>
                          {sym.changed_lines.map((line) => (
                            <span
                              key={line}
                              className="rounded bg-amber-950/30 px-1.5 py-0.5 text-xs font-mono text-amber-400/80"
                            >
                              L{line}
                            </span>
                          ))}
                        </div>
                      )}
                      {sym.code && (
                        <pre className="mt-3 rounded-lg bg-gray-950/70 border border-gray-700/30 p-3 text-xs font-mono text-gray-300 overflow-auto max-h-48">
                          {sym.code}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
