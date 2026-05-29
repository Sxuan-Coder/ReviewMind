const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type ReviewJobResponse = {
  job_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  stream_url: string;
};

export type ReviewReport = {
  job_id: string;
  status: string;
  summary: string;
  risk_level: string;
  findings: Array<{
    agent: string;
    file: string;
    line: number;
    level: string;
    type: string;
    confidence: number;
    description: string;
    suggestion: string;
  }>;
  review_comment: string;
};

export async function createReviewJob(prUrl: string): Promise<ReviewJobResponse> {
  const response = await fetch(`${apiBaseUrl}/review/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pr_url: prUrl }),
  });

  if (!response.ok) {
    throw new Error('创建 Review 任务失败');
  }

  return response.json();
}

export async function getReviewReport(jobId: string): Promise<ReviewReport> {
  const response = await fetch(`${apiBaseUrl}/review/jobs/${jobId}`);

  if (!response.ok) {
    throw new Error('获取 Review 报告失败');
  }

  return response.json();
}