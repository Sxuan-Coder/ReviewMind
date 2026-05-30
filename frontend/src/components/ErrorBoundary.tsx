import { Component, type ReactNode } from 'react';

interface Props { children: ReactNode }
interface State { hasError: boolean; error: Error | null }

// 全局错误边界：捕获子组件渲染异常，展示友好错误页
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ErrorBoundary] 捕获异常:', error, info.componentStack);
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="app-shell flex flex-col items-center justify-center min-h-screen">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-red-950/30 border border-red-500/20 mb-4">
          <span className="text-2xl">⚠️</span>
        </div>
        <h2 className="text-xl font-bold text-zinc-200 mb-2">页面出现异常</h2>
        <p className="text-sm text-zinc-500 max-w-md text-center mb-6">
          {this.state.error?.message || '未知错误'}
        </p>
        <a
          href="/"
          className="px-4 py-2 rounded-lg border border-zinc-800/60 bg-zinc-900/40 text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          ← 返回首页
        </a>
      </div>
    );
  }
}