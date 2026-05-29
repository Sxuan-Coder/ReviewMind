import { create } from 'zustand';

import type { ReviewJobResponse, ReviewReport } from '../services/reviewApi';

type ReviewState = {
  job: ReviewJobResponse | null;
  report: ReviewReport | null;
  setJob: (job: ReviewJobResponse) => void;
  setReport: (report: ReviewReport) => void;
};

export const useReviewStore = create<ReviewState>((set) => ({
  job: null,
  report: null,
  setJob: (job) => set({ job }),
  setReport: (report) => set({ report }),
}));