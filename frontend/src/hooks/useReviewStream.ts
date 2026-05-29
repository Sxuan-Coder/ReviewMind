import { useEffect, useRef } from 'react';
import { useReviewStore } from '../store/reviewStore';
import { mockSSESequence } from '../mock/data';
import type {
  ProgressEvent,
  ChunkEvent,
  FindingEvent,
  Finding,
  WarningEvent,
  DoneEvent,
  ErrorEvent,
} from '../types';

export function useReviewStream(jobId: string | undefined, useMock: boolean) {
  const store = useReviewStore();
  const timerRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    if (!jobId) return;

    store.reset();
    store.setSSEStatus('connecting');
    store.setStartedAt(Date.now());

    if (useMock) {
      // Simulate SSE with mock data
      store.setSSEStatus('connected');

      let cumulativeDelay = 0;
      const timers: ReturnType<typeof setTimeout>[] = [];

      for (const event of mockSSESequence) {
        cumulativeDelay += event.delayMs;
        const timer = setTimeout(() => {
          handleMockEvent(event.event, event.data as any);
        }, cumulativeDelay);
        timers.push(timer);
      }

      timerRef.current = timers;

      return () => {
        timers.forEach(clearTimeout);
      };
    }

    // Real SSE connection
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
    const streamUrl = `${apiBaseUrl}/review/stream/${jobId}`;
    const eventSource = new EventSource(streamUrl);

    eventSource.addEventListener('progress', (e: MessageEvent) => {
      const data: ProgressEvent = JSON.parse(e.data);
      store.setProgress(data);
    });

    eventSource.addEventListener('finding', (e: MessageEvent) => {
      const data: FindingEvent = JSON.parse(e.data);
      store.addFinding(data as any);
    });

    eventSource.addEventListener('chunk', (e: MessageEvent) => {
      const data: ChunkEvent = JSON.parse(e.data);
      if (data.target === 'summary') {
        store.addSummaryChunk(data.content);
      } else {
        store.addReportChunk(data.content);
      }
    });

    eventSource.addEventListener('warning', (_e: MessageEvent) => {
      // Warnings are non-fatal, just log for now
    });

    eventSource.addEventListener('done', (e: MessageEvent) => {
      const data: DoneEvent = JSON.parse(e.data);
      store.setDurationMs(data.duration_ms);
      store.setJobStatus('completed');
      store.setSSEStatus('disconnected');
      eventSource.close();
    });

    eventSource.addEventListener('error', (e: MessageEvent) => {
      if (e.data) {
        try {
          const data: ErrorEvent = JSON.parse(e.data);
          console.error('SSE error:', data.message);
        } catch {
          // ignore parse errors
        }
      }
      store.setSSEStatus('error');
      eventSource.close();
    });

    eventSource.onopen = () => {
      store.setSSEStatus('connected');
    };

    eventSource.onerror = () => {
      // EventSource may reconnect automatically; only set error if not connected
      if (eventSource.readyState === EventSource.CLOSED) {
        store.setSSEStatus('error');
      }
    };

    return () => {
      eventSource.close();
    };
  }, [jobId, useMock]);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      timerRef.current.forEach(clearTimeout);
    };
  }, []);

  return store;
}

function handleMockEvent(
  eventType: string,
  data: ProgressEvent | ChunkEvent | FindingEvent | WarningEvent | DoneEvent | ErrorEvent,
) {
  const store = useReviewStore.getState();

  switch (eventType) {
    case 'progress':
      store.setProgress(data as ProgressEvent);
      break;
    case 'finding':
      store.addFinding(data as unknown as Finding);
      break;
    case 'chunk': {
      const chunk = data as ChunkEvent;
      if (chunk.target === 'summary') {
        store.addSummaryChunk(chunk.content);
      } else {
        store.addReportChunk(chunk.content);
      }
      break;
    }
    case 'warning':
      // Non-fatal, currently not stored
      break;
    case 'done': {
      const done = data as DoneEvent;
      store.setDurationMs(done.duration_ms);
      store.setJobStatus('completed');
      store.setSSEStatus('disconnected');
      break;
    }
    case 'error':
      console.error('SSE error:', (data as ErrorEvent).message);
      store.setSSEStatus('error');
      break;
  }
}
