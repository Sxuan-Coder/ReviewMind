import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ExternalLink, ArrowLeft, Code, FileText, Shield, Diff, AlertTriangle, XCircle } from 'lucide-react';
import { useReviewStore } from '../store/reviewStore';
import { getJobDetail, getPrPreviewFiles } from '../services/reviewApi';
import { RiskSummary } from '../components/RiskSummary';
import { FindingCard } from '../components/FindingCard';
import { FileChangeList } from '../components/FileChangeList';
import { ReviewCommentBox } from '../components/ReviewCommentBox';
import { NavHeader } from '../components/NavHeader';
import { Skeleton } from '@/components/ui/skeleton';
import { NavHeader } from '../components/NavHeader';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import type { ChangedFile, Finding, JobDetailResponse } from '../types';
import { cn } from '../lib/utils';

// 报告页骨架屏：加载时展示占位，保持布局结构一致
function ReportSkeleton() {
  return (
    <div className="app-shell">
      <div className="report-card mb-5 p-5 space-y-3">
        <Skeleton className="h-3 w-48" />
        <Skeleton className="h-6 w-3/4" />
        <div className="flex gap-4">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
      <div className="dashboard-grid">
        <div className="space-y-4">
          <div className="report-card p-5 space-y-3">
            <Skeleton className="h-3 w-20" />
            <div className="grid grid-cols-3 gap-3">
              <Skeleton className="h-16 rounded-lg" />
              <Skeleton className="h-16 rounded-lg" />
              <Skeleton className="h-16 rounded-lg" />
            </div>
          </div>
          <div className="timeline-card p-6 space-y-2">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-2/3" />
          </div>
        </div>
        <div className="report-card p-6 space-y-6">
          <div className="flex gap-4 border-b border-zinc-800/40 pb-4">
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-8 w-20" />
            <Skeleton className="h-8 w-20" />
          </div>
          <div className="space-y-3">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </div>
        </div>
      </div>
    </div>
  );
}

export function ReportPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const storeDetail = useReviewStore((s) => s.detail);

  const [detail, setDetail] = useState<JobDetailResponse | null>(storeDetail);
  const [loading, setLoading] = useState(!detail);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [expandedFindings, setExpandedFindings] = useState<Set<string>>(new Set());

  const [diffFile, setDiffFile] = useState<ChangedFile | null>(null);
  const [diffPatchLoading, setDiffPatchLoading] = useState(false);
  const [diffPatchError, setDiffPatchError] = useState<string | null>(null);
  const [highlightLine, setHighlightLine] = useState<number | null>(null);
  const diffContainerRef = useRef<HTMLDivElement>(null);

  // 选择第一个有 diff 数据的文件
  const selectFirstDiffFile = (data: JobDetailResponse) => {
    const firstWithDiff = data.report?.changed_files?.find(
      (f) => f.old_code || f.new_code || f.patch,
    );
    if (firstWithDiff) setDiffFile(firstWithDiff);
  };

  useEffect(() => {
    // 如果已有 storeDetail 且包含完整数据，直接使用
    if (detail && detail.report) {
      setLoading(false);
      selectFirstDiffFile(detail);
      return;
    }
    if (!jobId) {
      setError('缺少 Job ID');
      setLoading(false);
      return;
    }

    getJobDetail(jobId)
      .then((data) => {
        setDetail(data);
        setLoading(false);
        selectFirstDiffFile(data);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : '加载报告失败');
        setLoading(false);
      });
  }, [jobId, detail]);

  function toggleFinding(id: string) {
    setExpandedFindings((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function jumpToDiff(finding: Finding) {
    const file = detail?.report?.changed_files?.find((f) => f.filename === finding.file);
    if (file) setDiffFile(file);
    setHighlightLine(finding.line);
    setActiveTab('diff');
    setTimeout(() => {
      const el = diffContainerRef.current?.querySelector(`[data-line="${finding.line}"]`);
      const scroller = el?.closest('[data-diff-scroll]') as HTMLElement | null;
      if (el instanceof HTMLElement && scroller) {
        scroller.scrollTop = Math.max(
          el.offsetTop - scroller.clientHeight / 2 + el.clientHeight / 2,
          0,
        );
      }
    }, 200);
  }

  const filesWithDiff = useMemo(
    () => detail?.report?.changed_files?.filter((f) => f.patch || f.old_code || f.new_code) ?? [],
    [detail],
  );

  useEffect(() => {
    if (!detail?.pr?.html_url || !detail.report?.changed_files.length) return;
    if (detail.report.changed_files.some((file) => file.patch || file.old_code || file.new_code)) return;

    let cancelled = false;
    setDiffPatchLoading(true);
    setDiffPatchError(null);

    getPrPreviewFiles(detail.pr.html_url)
      .then((files) => {
        if (cancelled) return;
        const patchByFilename = new Map(files.map((file) => [file.filename, file.patch]));
        setDetail((current) => {
          if (!current?.report) return current;
          return {
            ...current,
            report: {
              ...current.report,
              changed_files: current.report.changed_files.map((file) => ({
                ...file,
                patch: file.patch ?? patchByFilename.get(file.filename) ?? undefined,
              })),
            },
          };
        });
      })
      .catch((err) => {
        if (!cancelled) {
          setDiffPatchError(err instanceof Error ? err.message : 'Diff 数据补齐失败');
        }
      })
      .finally(() => {
        if (!cancelled) setDiffPatchLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [detail?.pr?.html_url, detail?.report?.changed_files]);

  useEffect(() => {
    if (filesWithDiff.length === 0) {
      if (diffFile) setDiffFile(null);
      return;
    }

    const selectedExists = filesWithDiff.some((f) => f.filename === diffFile?.filename);
    if (!diffFile || !selectedExists) {
      setDiffFile(filesWithDiff[0]);
    }
  }, [diffFile, filesWithDiff]);

  function renderDiffView(file: ChangedFile | null) {
    if (!file) {
      return <p className="text-zinc-600 text-center py-8">请选择一个文件查看 Diff</p>;
    }

    if (file.old_code && file.new_code) {
      return renderSideBySideDiff(file.old_code, file.new_code, file.filename);
    }

    if (file.patch) {
      return renderPatchView(file.patch);
    }

    return <p className="text-zinc-600 text-center py-8">该文件暂无 Diff 数据</p>;
  }

  if (loading) {
    return (
      <div className="app-shell">
        <NavHeader />
        <ReportSkeleton />
      </div>
    );
  }

  if (error || !detail) {
    const isNotFound = error?.includes('not found') || error?.includes('404');
    return (
      <div className="app-shell">
        <NavHeader />
        <Card className="report-card py-0 gap-0">
          <CardContent className="p-12 text-center space-y-4">
            {isNotFound ? (
              <>
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-amber-950/30 border border-amber-500/20 mb-2">
                  <AlertTriangle className="size-6 text-amber-400" />
                </div>
                <p className="text-amber-400 text-lg font-bold">任务已过期</p>
                <p className="text-sm text-zinc-500 max-w-md mx-auto">
                  该 Review 任务的数据已从内存中清除（通常因后端服务重启导致）。
                  <br />
                  请重新发起一次分析。
                </p>
              </>
            ) : (
              <>
                <XCircle className="size-10 text-red-400 mx-auto mb-2" />
                <p className="text-red-400 text-lg">{error || '报告未找到'}</p>
              </>
            )}
            <Button
              variant="outline"
              onClick={() => navigate('/')}
              className="border-zinc-800/60 bg-zinc-900/40 text-zinc-400 hover:text-zinc-200"
            >
              <ArrowLeft className="size-3" /> 返回首页
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const report = detail.report;
  const pr = detail.pr;

  return (
    <div className="app-shell">
      <NavHeader />

      {pr && (
        <Card className="report-card mb-5 py-0 gap-0">
          <CardContent className="p-5 flex flex-wrap items-center justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs text-muted-foreground font-mono">
                  {pr.owner}/{pr.repo}#{pr.number}
                </span>
                <span className="text-xs text-zinc-600">by {pr.author}</span>
              </div>
              <h2 className="text-xl font-bold text-zinc-200 truncate">{pr.title}</h2>
              <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                <span>{pr.base_branch} ← {pr.head_branch}</span>
                <span className="text-emerald-500">+{pr.additions}</span>
                <span className="text-red-500">-{pr.deletions}</span>
                <span>{pr.changed_files} 个文件</span>
              </div>
            </div>
            <a href={pr.html_url} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="sm" className="border-zinc-800/60 text-muted-foreground hover:text-zinc-200">
                <ExternalLink className="size-3" /> 查看 PR
              </Button>
            </a>
          </CardContent>
        </Card>
      )}

      <div className="dashboard-grid">
        <div className="min-w-0">
          <RiskSummary riskLevel={report?.risk_level} stats={report?.stats} />

          <Card className="timeline-card mt-4 py-0 gap-0">
            <CardContent className="p-6">
              <div className="section-label">任务信息</div>
              <div className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-zinc-500">Job ID</span>
                  <span className="font-mono text-zinc-500">{detail.job_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-500">状态</span>
                  <Badge variant="outline" className="text-emerald-400 border-emerald-500/20 bg-emerald-950/20">
                    {detail.status}
                  </Badge>
                </div>
                {detail.created_at && (
                  <div className="flex justify-between">
                    <span className="text-zinc-500">创建时间</span>
                    <span className="font-mono text-zinc-600 text-xs">
                      {new Date(detail.created_at).toLocaleString('zh-CN')}
                    </span>
                  </div>
                )}
                {detail.completed_at && (
                  <div className="flex justify-between">
                    <span className="text-zinc-500">完成时间</span>
                    <span className="font-mono text-zinc-600 text-xs">
                      {new Date(detail.completed_at).toLocaleString('zh-CN')}
                    </span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="report-card min-w-0">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col">
            <TabsList variant="line" className="border-b border-zinc-800/40 w-full max-w-full justify-start h-auto p-0 mb-6 gap-0 overflow-x-auto">
              {[
                { key: 'overview', label: '概览', icon: FileText },
                { key: 'findings', label: '风险发现', icon: Shield, count: report?.findings?.length ?? 0 },
                { key: 'files', label: '变更文件', icon: FileText, count: report?.changed_files?.length ?? 0 },
                { key: 'symbols', label: '变更方法', icon: Code, count: report?.changed_symbols?.length ?? 0 },
                { key: 'diff', label: 'Diff 视图', icon: Diff },
              ].map((tab) => (
                <TabsTrigger
                  key={tab.key}
                  value={tab.key}
                  className="px-4 py-2.5 text-sm font-medium whitespace-nowrap rounded-none data-[state=active]:text-zinc-200 text-zinc-500"
                >
                  {tab.label}
                  {tab.count !== undefined && tab.count > 0 && (
                    <Badge variant="outline" className="ml-1.5 text-xs text-zinc-600 border-zinc-800/40 bg-transparent">
                      {tab.count}
                    </Badge>
                  )}
                </TabsTrigger>
              ))}
            </TabsList>

            <TabsContent value="overview" className="mt-0">
              {report && (
                <div className="space-y-6">
                  <div>
                    <h3 className="section-label mb-3">PR 摘要</h3>
                    <p className="report-summary">{report.summary}</p>
                  </div>

                  {report.changed_symbols && report.changed_symbols.length > 0 && (
                    <div>
                      <h3 className="section-label mb-3">核心变更方法</h3>
                      <div className="space-y-2">
                        {report.changed_symbols.slice(0, 5).map((sym) => (
                          <Card key={sym.symbol} className="bg-zinc-900/40 border-zinc-800/60 py-0 gap-0">
                            <CardContent className="px-4 py-3">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="text-xs font-mono text-purple-400">{sym.symbol}</span>
                                <Badge variant="outline" className="text-xs text-zinc-600 border-zinc-800/40">
                                  {sym.language}
                                </Badge>
                              </div>
                              <span className="text-xs text-zinc-600 font-mono">
                                {sym.file} L{sym.start_line}-L{sym.end_line}
                              </span>
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    </div>
                  )}

                  <ReviewCommentBox content={report.review_comment} />
                </div>
              )}
            </TabsContent>

            <TabsContent value="findings" className="mt-0">
              {report && (
                <div className="space-y-3">
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
            </TabsContent>

            <TabsContent value="files" className="mt-0">
              {report && <FileChangeList files={report.changed_files} />}
            </TabsContent>

            <TabsContent value="symbols" className="mt-0">
              {report && (
                <div>
                  {report.changed_symbols.length === 0 ? (
                    <p className="empty-state text-center py-8">暂无可识别的变更方法</p>
                  ) : (
                    <div className="space-y-3">
                      {report.changed_symbols.map((sym) => (
                        <Card key={`${sym.file}:${sym.symbol}`} className="bg-zinc-900/40 border-zinc-800/60 py-0 gap-0">
                          <CardContent className="p-5">
                            <div className="flex items-center gap-3 mb-3">
                              <span className="text-sm font-bold text-purple-400">{sym.symbol}</span>
                              <Badge variant="outline" className="bg-purple-950/30 text-purple-400/70 border-purple-500/20">
                                {sym.language}
                              </Badge>
                            </div>
                            <div className="text-xs text-zinc-600 font-mono mb-2">
                              {sym.file} · L{sym.start_line}–L{sym.end_line}
                            </div>
                            {sym.changed_lines.length > 0 && (
                              <div className="flex items-center gap-1 flex-wrap">
                                <span className="text-xs text-zinc-600 mr-1">变更行:</span>
                                {sym.changed_lines.map((line) => (
                                  <Badge key={line} variant="outline" className="bg-amber-950/30 text-amber-400/80 border-amber-500/20 font-mono text-xs">
                                    L{line}
                                  </Badge>
                                ))}
                              </div>
                            )}
                            {sym.code && (
                              <pre className="mt-3 rounded-lg bg-zinc-950/70 border border-zinc-800/40 p-3 text-xs font-mono text-zinc-300 overflow-auto max-h-48">
                                {sym.code}
                              </pre>
                            )}
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </TabsContent>

            <TabsContent value="diff" className="mt-0">
              {diffPatchLoading && (
                <p className="text-xs text-zinc-500 mb-3">正在补齐 Diff 数据...</p>
              )}
              {diffPatchError && (
                <p className="text-xs text-amber-400 mb-3">{diffPatchError}</p>
              )}
              {filesWithDiff.length > 1 && (
                <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-2">
                  {filesWithDiff.map((f) => (
                    <Button
                      key={f.filename}
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setDiffFile(f);
                        setHighlightLine(null);
                      }}
                      className={cn(
                        'shrink-0 font-mono text-xs',
                        diffFile?.filename === f.filename
                          ? 'border-zinc-600 bg-zinc-800/40 text-zinc-200'
                          : 'border-zinc-800/40 text-zinc-600 hover:text-zinc-300',
                      )}
                    >
                      {f.filename.split('/').pop()}
                    </Button>
                  ))}
                </div>
              )}

              {filesWithDiff.length === 0 && (
                <p className="text-zinc-600 text-center py-8">该 PR 暂无 Diff 数据</p>
              )}

              <div ref={diffContainerRef} className="rounded-xl border border-zinc-800/40 overflow-hidden">
                {renderDiffView(diffFile)}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}

// ============ Inline Diff Renderers ============

function renderSideBySideDiff(oldCode: string, newCode: string, filename: string) {
  const oldLines = oldCode.split('\n');
  const newLines = newCode.split('\n');

  const diffRows = computeLineDiff(oldLines, newLines);

  return (
    <div data-diff-scroll className="overflow-auto max-h-[70vh]">
      <table className="w-full text-xs font-mono border-collapse">
        <thead>
          <tr className="bg-zinc-900/80 text-zinc-500 sticky top-0 z-10">
            <th className="w-12 px-2 py-1.5 text-right border-r border-zinc-800/40">旧</th>
            <th className="px-3 py-1.5 text-left border-r border-zinc-800/40">旧版本</th>
            <th className="w-12 px-2 py-1.5 text-right border-r border-zinc-800/40">新</th>
            <th className="px-3 py-1.5 text-left">新版本</th>
          </tr>
        </thead>
        <tbody>
          {diffRows.map((row, i) => (
            <tr
              key={i}
              className={cn(
                'border-b border-zinc-900/50',
                row.type === 'add' && 'bg-emerald-950/10',
                row.type === 'remove' && 'bg-red-950/10',
              )}
            >
              <td className="w-12 px-2 py-0.5 text-right text-zinc-700 border-r border-zinc-800/40 select-none">
                {row.type !== 'add' ? row.oldLine : ''}
              </td>
              <td
                className={cn(
                  'px-3 py-0.5 border-r border-zinc-800/40 whitespace-pre-wrap',
                  row.type === 'remove' ? 'text-red-400/80 bg-red-950/10' : 'text-zinc-500',
                )}
                data-line={row.oldLine}
              >
                {row.type === 'remove' && <span className="select-none mr-2 text-red-600">-</span>}
                {row.type !== 'add' ? row.content : ''}
              </td>
              <td className="w-12 px-2 py-0.5 text-right text-zinc-700 border-r border-zinc-800/40 select-none">
                {row.type !== 'remove' ? row.newLine : ''}
              </td>
              <td
                className={cn(
                  'px-3 py-0.5 whitespace-pre-wrap',
                  row.type === 'add' ? 'text-emerald-400/80 bg-emerald-950/10' : 'text-zinc-300',
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
    <div data-diff-scroll className="overflow-auto max-h-[70vh] p-3 font-mono text-xs leading-5">
      {lines.map((line, i) => {
        const isAdd = line.startsWith('+') && !line.startsWith('+++');
        const isDel = line.startsWith('-') && !line.startsWith('---');
        const isHunk = line.startsWith('@@');
        const isEmpty = line.length === 0;
        return (
          <div
            key={i}
            data-line={i + 1}
            className={cn(
              'whitespace-pre py-px',
              isAdd && 'text-emerald-400/80 bg-emerald-950/20',
              isDel && 'text-red-400/80 bg-red-950/20',
              isHunk && 'text-sky-400/80 bg-sky-950/10',
              !isAdd && !isDel && !isHunk && !isEmpty && 'text-zinc-400',
              isEmpty && 'h-4',
            )}
          >
            {line || ' '}
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
  const lcs = longestCommonSubsequence(oldLines, newLines);

  let oi = 0;
  let ni = 0;
  let li = 0;

  while (oi < oldLines.length || ni < newLines.length) {
    if (li < lcs.length && oi < oldLines.length && oldLines[oi] === lcs[li]) {
      while (ni < newLines.length && newLines[ni] !== lcs[li]) {
        rows.push({ type: 'add', content: newLines[ni], oldLine: 0, newLine: ni + 1 });
        ni++;
      }
      rows.push({ type: 'equal', content: lcs[li], oldLine: oi + 1, newLine: ni + 1 });
      oi++;
      ni++;
      li++;
    } else if (li < lcs.length && ni < newLines.length && newLines[ni] === lcs[li]) {
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
