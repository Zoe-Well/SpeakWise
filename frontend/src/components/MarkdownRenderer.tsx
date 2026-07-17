/** AI 回答的 Markdown 渲染 — 按行缓冲：完整行进 ReactMarkdown，末行进 prose <p> */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import remarkMath from "remark-math";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";

interface Props {
  content: string;
  streaming?: boolean;
}

const PROSE = "prose prose-sm prose-zinc max-w-none" +
  " prose-headings:text-zinc-800 prose-headings:font-semibold" +
  " prose-p:text-zinc-700 prose-p:leading-relaxed" +
  " prose-a:text-indigo-600 prose-a:no-underline hover:prose-a:underline" +
  " prose-strong:text-zinc-800 prose-strong:font-semibold" +
  " prose-blockquote:border-l-indigo-400 prose-blockquote:bg-indigo-50/50" +
  " prose-blockquote:rounded-r-lg prose-blockquote:py-1 prose-blockquote:px-4" +
  " prose-blockquote:text-zinc-600 prose-blockquote:not-italic" +
  " prose-code:before:content-none prose-code:after:content-none" +
  " prose-code:bg-zinc-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded" +
  " prose-code:text-pink-600 prose-code:text-xs prose-code:font-normal" +
  " prose-pre:bg-zinc-900 prose-pre:border prose-pre:border-zinc-800" +
  " prose-pre:rounded-xl prose-pre:shadow-sm" +
  " prose-pre:[&>code]:bg-transparent prose-pre:[&>code]:text-zinc-100" +
  " prose-pre:[&>code]:text-xs prose-pre:[&>code]:p-0" +
  " prose-table:border-collapse prose-th:bg-zinc-50 prose-th:px-3 prose-th:py-2" +
  " prose-th:text-xs prose-th:font-semibold prose-td:px-3 prose-td:py-2 prose-td:text-sm" +
  " prose-img:rounded-xl prose-img:shadow-sm prose-li:text-zinc-700" +
  " [&_.katex-display]:my-3 [&_.katex]:text-sm";

export default function MarkdownRenderer({ content, streaming }: Props) {
  if (!content) return null;

  // ── Non-streaming: single ReactMarkdown ──
  if (!streaming) {
    return (
      <div className={PROSE}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkBreaks, remarkMath]}
          rehypePlugins={[rehypeHighlight, rehypeKatex]}
        >
          {content}
        </ReactMarkdown>
      </div>
    );
  }

  // ── Streaming: split at last \n ──
  const lastNL = content.lastIndexOf("\n");
  const complete = lastNL >= 0 ? content.slice(0, lastNL + 1) : "";
  const pending = lastNL >= 0 ? content.slice(lastNL + 1) : content;

  return (
    <div className={PROSE}>
      {/* Complete lines → ReactMarkdown (stable, no re-parse jitter for old lines) */}
      {complete && (
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkBreaks, remarkMath]}
          rehypePlugins={[rehypeHighlight, rehypeKatex]}
        >
          {complete}
        </ReactMarkdown>
      )}

      {/* Pending line → prose-styled <p>, same visual context as final */}
      {pending && (
        <p className="text-zinc-700 leading-relaxed whitespace-pre-wrap break-words">
          {pending}
        </p>
      )}

      {/* Blinking cursor */}
      <span className="inline-block w-2 h-4 bg-indigo-500 rounded-sm animate-pulse ml-0.5 align-text-bottom" />
    </div>
  );
}
