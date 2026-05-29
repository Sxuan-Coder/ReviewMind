import { useNavigate } from 'react-router-dom';

interface NavHeaderProps {
  title?: string;
  showBack?: boolean;
}

export function NavHeader({ title, showBack = true }: NavHeaderProps) {
  const navigate = useNavigate();

  return (
    <header className="flex items-center justify-between py-5 px-0">
      <div className="flex items-center gap-4">
        {showBack && (
          <button
            onClick={() => navigate('/')}
            className="rounded-lg border border-gray-600/30 bg-white/[0.03] px-3 py-1.5 text-xs text-gray-400 hover:text-gray-200 hover:bg-white/[0.06] transition-colors"
          >
            ← 返回首页
          </button>
        )}
        <span
          className="text-lg font-bold text-cyan-400/90 tracking-tight cursor-pointer"
          onClick={() => navigate('/')}
        >
          ReviewMind
        </span>
      </div>
      {title && <span className="text-sm text-gray-500">{title}</span>}
    </header>
  );
}
