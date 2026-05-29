import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useReviewStore } from '../store/reviewStore';
import { getJobDetail } from '../services/reviewApi';
import { RiskSummary } from '../components/RiskSummary';
import { FindingCard } from '../components/FindingCard';
import { FileChangeList } from '../components/FileChangeList';
import { ReviewCommentBox } from '../components/ReviewCommentBox';
import { NavHeader } from '../components/NavHeader';
import type { ChangedFile, Finding, JobDetailResponse } from '../types';
import { cn } from '../lib/utils';

type ReportTab = 'overview' | 'findings' | 'files' | 'symbols' | 'diff';

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

  // Diff state
  const [diffFile, setDiffFile] = useState<ChangedFile | null>(null);
  const [highlightLine, setHighlightLine] = useState<number | null>(null);
  const diffContainerRef = useRef<HTMLDivElement>(null);

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
        // Default diff file to the first one with code
        const firstWithDiff = data.report?.changed_files?.find(
          (f) => f.old_code || f.new_code || f.patch,
        );
        if (firstWithDiff) setDiffFile(firstWithDiff);
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

  /** Click a finding → jump to diff tab and highlight its line */
  function jumpToDiff(finding: Finding) {
    // Find the matching file
    const file = detail?.report?.changed_files?.find((f) => f.filename === finding.file);
    if (file) setDiffFile(file);
    setHighlightLine(finding.line);
    setActiveTab('diff');
    // Scroll to line after render
    setTimeout(() => {
      const el = diffContainerRef.current?.querySelector(`[data-line="${finding.line}"]`);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 200);
  }

  // Files with diff data
  const filesWithDiff = useMemo(
    () => detail?.report?.changed_files?.filter((f) => f.patch || f.old_code || f.new_code) ?? [],
    [detail],
  );

  // Render simple inline diff view
  function renderDiffView(file: ChangedFile | null) {
    if (!file) {
      return <p className="text-gray-500 text-center py-8">请选择一个文件查看 Diff</p>;
    }

    if (file.old_code && file.new_code) {
      return renderSideBySideDiff(file.old_code, file.new_code, file.filename);
    }

    if (file.patch) {
      return renderPatchView(file.patch);
    }

    return <p className="text-gray-500 text-center py-8">该文件暂无 Diff 数据</p>;
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
    { key: 'diff', label: 'Diff 视图' },
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
                    onJumpToDiff={() => jumpToDiff(f)}
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

          {/* Tab: Diff */}
          {activeTab === 'diff' && (
            <div className="animate-fade-in">
              {/* File selector */}
              {filesWithDiff.length > 1 && (
                <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-2">
                  {filesWithDiff.map((f) => (
                    <button
                      key={f.filename}
                      onClick={() => {
                        setDiffFile(f);
                        setHighlightLine(null);
                      }}
                      className={cn(
                        'shrink-0 rounded-lg border px-3 py-1.5 text-xs font-mono transition-colors',
                        diffFile?.filename === f.filename
                          ? 'border-cyan-500/40 bg-cyan-950/20 text-cyan-400'
                          : 'border-gray-700/20 text-gray-500 hover:text-gray-300',
                      )}
                    >
                      {f.filename.split('/').pop()}
                    </button>
                  ))}
                </div>
              )}

              <div ref={diffContainerRef} className="rounded-xl border border-gray-700/20 overflow-hidden">
                {renderDiffView(diffFile)}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============ Inline Diff Renderers ============

function renderSideBySideDiff(oldCode: string, newCode: string, filename: string) {
  const oldLines = oldCode.split('\n');
  const newLines = newCode.split('\n');
  const maxLines = Math.max(oldLines.length, newLines.length);

  // Simple LCS-based diff for line matching
  const diffRows = computeLineDiff(oldLines, newLines);

  const ext = filename.split('.').pop()?.toLowerCase() || '';
  const langClass = ext;

  return (
    <div className="overflow-auto max-h-[70vh]">
      <table className="w-full text-xs font-mono border-collapse">
        <thead>
          <tr className="bg-gray-900/80 text-gray-500 sticky top-0 z-10">
            <th className="w-12 px-2 py-1.5 text-right border-r border-gray-700/30">旧</th>
            <th className="px-3 py-1.5 text-left border-r border-gray-700/30">旧版本</th>
            <th className="w-12 px-2 py-1.5 text-right border-r border-gray-700/30">新</th>
            <th className="px-3 py-1.5 text-left">新版本</th>
          </tr>
        </thead>
        <tbody>
          {diffRows.map((row, i) => (
            <tr
              key={i}
              className={cn(
                'border-b border-gray-800/50',
                row.type === 'add' && 'bg-emerald-950/15',
                row.type === 'remove' && 'bg-red-950/15',
                row.type === 'equal' && '',
              )}
            >
              <td className="w-12 px-2 py-0.5 text-right text-gray-600 border-r border-gray-700/30 select-none">
                {row.type !== 'add' ? row.oldLine : ''}
              </td>
              <td
                className={cn(
                  'px-3 py-0.5 border-r border-gray-700/30 whitespace-pre-wrap',
                  row.type === 'remove' ? 'text-red-400/80 bg-red-950/10' : 'text-gray-400',
                )}
                data-line={row.oldLine}
              >
                {row.type === 'remove' && <span className="select-none mr-2 text-red-600">-</span>}
                {row.type !== 'add' ? row.content : ''}
              </td>
              <td className="w-12 px-2 py-0.5 text-right text-gray-600 border-r border-gray-700/30 select-none">
                {row.type !== 'remove' ? row.newLine : ''}
              </td>
              <td
                className={cn(
                  'px-3 py-0.5 whitespace-pre-wrap',
                  row.type === 'add' ? 'text-emerald-400/80 bg-emerald-950/10' : 'text-gray-300',
                )}
                data-line={row.newLine}
              >
                {row.type === 'add' && <span className="select-none mr-2 text-emerald-600">+</span>}
                {row.type !== 'remove' ? row.content : ''}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderPatchView(patch: string) {
  const lines = patch.split('\n');
  return (
    <div className="overflow-auto max-h-[70vh] p-3 font-mono text-xs">
      {lines.map((line, i) => {
        const isAdd = line.startsWith('+');
        const isDel = line.startsWith('-');
        const isHunk = line.startsWith('@@');
        return (
          <div
            key={i}
            className={cn(
              'whitespace-pre-wrap py-0.5',
              isAdd && 'text-emerald-400/80 bg-emerald-950/10',
              isDel && 'text-red-400/80 bg-red-950/10',
              isHunk && 'text-cyan-400/60',
              !isAdd && !isDel && !isHunk && 'text-gray-500',
            )}
          >
            {line}
          </div>
        );
      })}
    </div>
  );
}

// ============ Simple Line Diff ============

interface DiffRow {
  type: 'equal' | 'add' | 'remove';
  content: string;
  oldLine: number;
  newLine: number;
}

function computeLineDiff(oldLines: string[], newLines: string[]): DiffRow[] {
  const rows: DiffRow[] = [];
  // Simple approach: use LCS to match lines
  const lcs = longestCommonSubsequence(oldLines, newLines);

  let oi = 0;
  let ni = 0;
  let li = 0;

  while (oi < oldLines.length || ni < newLines.length) {
    if (li < lcs.length && oi < oldLines.length && oldLines[oi] === lcs[li]) {
      // Match: check if we need to catch up new side
      while (ni < newLines.length && newLines[ni] !== lcs[li]) {
        rows.push({ type: 'add', content: newLines[ni], oldLine: 0, newLine: ni + 1 });
        ni++;
      }
      rows.push({ type: 'equal', content: lcs[li], oldLine: oi + 1, newLine: ni + 1 });
      oi++;
      ni++;
      li++;
    } else if (li < lcs.length && ni < newLines.length && newLines[ni] === lcs[li]) {
      // Old has extra line (removed)
      rows.push({ type: 'remove', content: oldLines[oi], oldLine: oi + 1, newLine: 0 });
      oi++;
    } else if (oi < oldLines.length && li < lcs.length && oldLines[oi] !== lcs[li]) {
      rows.push({ type: 'remove', content: oldLines[oi], oldLine: oi + 1, newLine: 0 });
      oi++;
    } else if (ni < newLines.length) {
      rows.push({ type: 'add', content: newLines[ni], oldLine: 0, newLine: ni + 1 });
      ni++;
    } else {
      break;
    }
  }

  return rows;
}

function longestCommonSubsequence(a: string[], b: string[]): string[] {
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (a[i - 1] === b[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  const result: string[] = [];
  let i = m;
  let j = n;
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) {
      result.unshift(a[i - 1]);
      i--;
      j--;
    } else if (dp[i - 1][j] > dp[i][j - 1]) {
      i--;
    } else {
      j--;
    }
  }
  return result;
}
