import { useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Copy, Check } from 'lucide-react';

interface ReviewCommentBoxProps {
  content: string;
}

export function ReviewCommentBox({ content }: ReviewCommentBoxProps) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const textarea = document.createElement('textarea');
      textarea.value = content;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-2">
        <h3 className="section-label">Review Comment</h3>
        <Button
          variant="outline"
          size="sm"
          onClick={handleCopy}
          className="border-zinc-800/60 bg-zinc-900/40 text-zinc-400 hover:text-zinc-200"
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          {copied ? '已复制' : '复制评论'}
        </Button>
      </div>
      <pre className="comment-box text-sm leading-relaxed font-sans">{content}</pre>
    </div>
  );
}