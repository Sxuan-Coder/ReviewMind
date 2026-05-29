import { useState } from 'react';

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
      // fallback
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
        <button
          onClick={handleCopy}
          className="rounded-lg border border-cyan-500/25 bg-cyan-950/30 px-4 py-1.5 text-xs font-medium text-cyan-400 hover:bg-cyan-950/50 transition-colors"
        >
          {copied ? '已复制 ✓' : '复制评论'}
        </button>
      </div>
      <pre className="comment-box text-sm leading-relaxed font-sans">{content}</pre>
    </div>
  );
}
