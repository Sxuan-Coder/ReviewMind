import type {
  ApiResponse,
  CreateJobResponse,
  JobDetailResponse,
  JobListResponse,
  MergeRequest,
  MergeResponse,
  PostCommentResponse,
  PullRequestInfo,
} from '../types';

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

// ============ Health ============
export async function getHealth() {
  const response = await fetch(`${apiBaseUrl}/health`);
  if (!response.ok) throw new Error('健康检查失败');
  return response.json();
}

// ============ Review Jobs ============
export interface CreateJobParams {
  pr_url: string;
  config?: {
    enable_ast?: boolean;
    enable_rag?: boolean;
    strict_mode?: boolean;
  };
}

export async function createReviewJob(
  params: CreateJobParams,
): Promise<CreateJobResponse> {
  const response = await fetch(`${apiBaseUrl}/review/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.message || '创建 Review 任务失败');
  }

  const result: ApiResponse<CreateJobResponse> = await response.json();
  return result.data;
}

export async function getJobDetail(jobId: string): Promise<JobDetailResponse> {
  const response = await fetch(`${apiBaseUrl}/review/jobs/${jobId}`);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error('Review job not found (可能已过期，请重新发起分析)');
    }
    const err = await response.json().catch(() => ({}));
    throw new Error(err.message || '获取 Review 报告失败');
  }

  const result: ApiResponse<JobDetailResponse> = await response.json();
  return result.data;
}

export async function getJobList(
  page = 1,
  pageSize = 10,
): Promise<JobListResponse> {
  const response = await fetch(
    `${apiBaseUrl}/review/jobs?page=${page}&page_size=${pageSize}`,
  );
  if (!response.ok) {
    throw new Error('获取任务列表失败');
  }

  const result: ApiResponse<JobListResponse> = await response.json();
  return result.data;
}

export async function cancelJob(
  jobId: string,
): Promise<{ job_id: string; status: string }> {
  const response = await fetch(`${apiBaseUrl}/review/jobs/${jobId}/cancel`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('取消任务失败');
  }

  const result = await response.json();
  return result.data;
}

// ============ GitHub Utils ============
export async function parsePrUrl(
  prUrl: string,
): Promise<{ owner: string; repo: string; pull_number: number; html_url: string }> {
  const response = await fetch(`${apiBaseUrl}/github/parse-pr-url`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pr_url: prUrl }),
  });
  if (!response.ok) {
    throw new Error('PR URL 解析失败');
  }

  const result = await response.json();
  return result.data;
}

export async function getPrPreview(prUrl: string): Promise<PullRequestInfo> {
  const response = await fetch(`${apiBaseUrl}/github/pr-preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pr_url: prUrl }),
  });
  if (!response.ok) {
    throw new Error('PR 预览获取失败');
  }

  const result: ApiResponse<{ pr: PullRequestInfo }> = await response.json();
  return result.data.pr;
}

export async function getPrPreviewFiles(
  prUrl: string,
): Promise<{ filename: string; patch?: string | null }[]> {
  const response = await fetch(`${apiBaseUrl}/github/pr-preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pr_url: prUrl }),
  });
  if (!response.ok) {
    throw new Error('PR 文件预览获取失败');
  }

  const result = await response.json();
  return result.data?.files ?? [];
}

// ============ Review Comment ============
export async function postReviewComment(
  jobId: string,
  commentBody?: string,
): Promise<PostCommentResponse> {
  const response = await fetch(`${apiBaseUrl}/review/jobs/${jobId}/comment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(commentBody ? { comment_body: commentBody } : {}),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.message || '评论发布失败');
  }
  const result: ApiResponse<PostCommentResponse> = await response.json();
  return result.data;
}

// ============ Merge PR ============
export async function mergePullRequest(
  jobId: string,
  options?: MergeRequest,
): Promise<MergeResponse> {
  const response = await fetch(`${apiBaseUrl}/review/jobs/${jobId}/merge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options || {}),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.message || 'PR 合并失败');
  }
  const result: ApiResponse<MergeResponse> = await response.json();
  return result.data;
}
