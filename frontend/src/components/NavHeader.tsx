import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface NavHeaderProps {
  title?: string;
  showBack?: boolean;
}

export function NavHeader({ title, showBack = true }: NavHeaderProps) {
  const navigate = useNavigate();

  return (
    <header className="flex items-center justify-between py-4 px-0 border-b border-zinc-800/60 mb-6">
      <div className="flex items-center gap-4">
        {showBack && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/')}
            className="border-zinc-800/60 bg-zinc-900/40 text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800/40"
          >
            <ArrowLeft className="size-3.5" />
            返回首页
          </Button>
        )}
        <span
          className="text-lg font-bold text-zinc-200 tracking-tight cursor-pointer hover:text-zinc-100 transition-colors"
          onClick={() => navigate('/')}
        >
          ReviewMind
        </span>
      </div>
      {title && <span className="text-xs text-zinc-600 font-mono">{title}</span>}
    </header>
  );
}