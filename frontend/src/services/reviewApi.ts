import type {
  ApiResponse,
  CreateJobResponse,
  JobDetailResponse,
  JobListResponse,
  PullRequestInfo,
} from '../types';
import {
  mockCreateJobResponse,
  mockJobCompleted,
  mockJobList,
  mockPrPreview,
  simulateDelay,
} from '../mock/data';

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
  useMock = false,
): Promise<CreateJobResponse> {
  if (useMock) {
    await simulateDelay(500);
    return { ...mockCreateJobResponse, job_id: `rev_${Date.now().toString(36)}` };
  }

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

export async function getJobDetail(
  jobId: string,
  useMock = false,
): Promise<JobDetailResponse> {
  if (useMock) {
    await simulateDelay(300);
    return { ...mockJobCompleted, job_id: jobId };
  }

  const response = await fetch(`${apiBaseUrl}/review/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error('获取 Review 报告失败');
  }

  const result: ApiResponse<JobDetailResponse> = await response.json();
  return result.data;
}

export async function getJobList(
  page = 1,
  pageSize = 10,
  useMock = false,
): Promise<JobListResponse> {
  if (useMock) {
    await simulateDelay(200);
    return mockJobList;
  }

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
  useMock = false,
): Promise<{ job_id: string; status: string }> {
  if (useMock) {
    await simulateDelay(200);
    return { job_id: jobId, status: 'cancelled' };
  }

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
  useMock = false,
): Promise<{ owner: string; repo: string; pull_number: number; html_url: string }> {
  if (useMock) {
    await simulateDelay(200);
    return {
      owner: 'octocat',
      repo: 'hello-world',
      pull_number: 42,
      html_url: prUrl,
    };
  }

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

export async function getPrPreview(
  prUrl: string,
  useMock = false,
): Promise<PullRequestInfo> {
  if (useMock) {
    await simulateDelay(500);
    return mockPrPreview;
  }

  const response = await fetch(`${apiBaseUrl}/github/pr-preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pr_url: prUrl }),
  });
  if (!response.ok) {
    throw new Error('PR 预览获取失败');
  }

  const result: ApiResponse<PullRequestInfo> = await response.json();
  return result.data;
}
