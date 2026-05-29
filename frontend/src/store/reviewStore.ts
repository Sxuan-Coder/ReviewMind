import { create } from 'zustand';
import type {
  CreateJobResponse,
  JobDetailResponse,
  ReviewProgress,
  Finding,
  StepType,
  JobStatus,
} from '../types';

export type SSEConnectionStatus = 'idle' | 'connecting' | 'connected' | 'disconnected' | 'error';

interface ReviewState {
  // Job
  job: CreateJobResponse | null;
  jobStatus: JobStatus | null;

  // Progress
  progress: ReviewProgress | null;
  stepHistory: StepType[];

  // Live findings from SSE
  findings: Finding[];

  // Chunks
  summaryChunks: string[];
  reportChunks: string[];

  // Final report
  detail: JobDetailResponse | null;

  // SSE connection
  sseStatus: SSEConnectionStatus;

  // Timing
  startedAt: number | null;
  durationMs: number | null;

  // Mock mode
  useMock: boolean;

  // Actions
  setJob: (job: CreateJobResponse) => void;
  setJobStatus: (status: JobStatus) => void;
  setProgress: (progress: ReviewProgress) => void;
  addStep: (step: StepType) => void;
  addFinding: (finding: Finding) => void;
  addSummaryChunk: (content: string) => void;
  addReportChunk: (content: string) => void;
  setDetail: (detail: JobDetailResponse) => void;
  setSSEStatus: (status: SSEConnectionStatus) => void;
  setStartedAt: (ts: number) => void;
  setDurationMs: (ms: number) => void;
  setUseMock: (useMock: boolean) => void;
  reset: () => void;
}

const initialState = {
  job: null,
  jobStatus: null,
  progress: null,
  stepHistory: [] as StepType[],
  findings: [] as Finding[],
  summaryChunks: [] as string[],
  reportChunks: [] as string[],
  detail: null,
  sseStatus: 'idle' as SSEConnectionStatus,
  startedAt: null,
  durationMs: null,
  useMock: false,
};

export const useReviewStore = create<ReviewState>((set) => ({
  ...initialState,

  setJob: (job) => set({ job, jobStatus: job.status }),
  setJobStatus: (status) => set({ jobStatus: status }),
  setProgress: (progress) =>
    set((state) => {
      const stepHistory = state.stepHistory.includes(progress.step)
        ? state.stepHistory
        : [...state.stepHistory, progress.step];
      return { progress, stepHistory };
    }),
  addStep: (step) =>
    set((state) => {
      if (state.stepHistory.includes(step)) return state;
      return { stepHistory: [...state.stepHistory, step] };
    }),
  addFinding: (finding) =>
    set((state) => {
      if (state.findings.some((f) => f.id === finding.id)) return state;
      return { findings: [...state.findings, finding] };
    }),
  addSummaryChunk: (content) =>
    set((state) => ({ summaryChunks: [...state.summaryChunks, content] })),
  addReportChunk: (content) =>
    set((state) => ({ reportChunks: [...state.reportChunks, content] })),
  setDetail: (detail) => set({ detail, jobStatus: detail.status }),
  setSSEStatus: (sseStatus) => set({ sseStatus }),
  setStartedAt: (ts) => set({ startedAt: ts }),
  setDurationMs: (ms) => set({ durationMs: ms }),
  setUseMock: (useMock) => set({ useMock }),
  reset: () => set(initialState),
}));
