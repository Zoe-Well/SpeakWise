/** AI 回答的 Markdown 渲染 — 流式时尾部未闭合语法退避为纯文本 */

import { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";

interface Props {
  content: string;
  streaming?: boolean;
}

/* 闭合对：如果尾部有未闭合的标记，把最后一段不完整的 token 退回纯文本显示。
   规则：从尾部向前扫描，找到第一个"未闭合"的内联标记开始位置。
   支持的标记：** __ * _ ` ~~ */
const INLINE_PAIRS: [string, string][] = [
  ["**", "**"], ["__", "__"], ["*", "*"], ["_", "_"], ["`", "`"], ["~~", "~~"],
];

function splitAtUnclosedEnd(text: string): [string, string] {
  for (const [open, close] of INLINE_PAIRS) {
    let lastOpen = -1;
    let pos = 0;
    while (pos < text.length) {
      const oi = text.indexOf(open, pos);
      if (oi === -1) break;
      const ci = text.indexOf(close, oi + open.length);
      if (ci === -1) {
        lastOpen = oi;
        break;
      }
      pos = ci + close.length;
    }
    if (lastOpen >= 0) {
      return [text.slice(0, lastOpen), text.slice(lastOpen)];
    }
  }
  return [text, ""];
}

export default function MarkdownRenderer({ content, streaming }: Props) {
  if (!streaming || !content) {
    return <MdBlock>{content}</MdBlock>;
  }

  const [safe, pending] = splitAtUnclosedEnd(content);

  return (
    <div>
      {safe.trim() && <MdBlock>{safe}</MdBlock>}
      {pending && (
        <span className="text-sm whitespace-pre-wrap break-words text-zinc-700">{pending}</span>
      )}
      <span className="inline-block w-2 h-4 bg-indigo-500 rounded-sm animate-pulse ml-0.5 align-text-bottom" />
    </div>
  );
}

/* ── Pure markdown block ── */

function MdBlock({ children: content }: { children: string }) {
  return (
    <div
      className="prose prose-sm prose-zinc max-w-none
        prose-headings:text-zinc-800 prose-headings:font-semibold
        prose-p:text-zinc-700 prose-p:leading-relaxed
        prose-a:text-indigo-600 prose-a:no-underline hover:prose-a:underline
        prose-strong:text-zinc-800 prose-strong:font-semibold
        prose-blockquote:border-l-indigo-400 prose-blockquote:bg-indigo-50/50
        prose-blockquote:rounded-r-lg prose-blockquote:py-1 prose-blockquote:px-4
        prose-blockquote:text-zinc-600 prose-blockquote:not-italic
        prose-code:before:content-none prose-code:after:content-none
        prose-code:bg-zinc-100 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded
        prose-code:text-pink-600 prose-code:text-xs prose-code:font-normal
        prose-pre:bg-zinc-900 prose-pre:border prose-pre:border-zinc-800
        prose-pre:rounded-xl prose-pre:shadow-sm
        prose-pre:[&>code]:bg-transparent prose-pre:[&>code]:text-zinc-100
        prose-pre:[&>code]:text-xs prose-pre:[&>code]:p-0
        prose-table:border-collapse prose-th:bg-zinc-50 prose-th:px-3 prose-th:py-2
        prose-th:text-xs prose-th:font-semibold prose-td:px-3 prose-td:py-2 prose-td:text-sm
        prose-img:rounded-xl prose-img:shadow-sm
        prose-li:text-zinc-700
        [&_.katex-display]:my-3 [&_.katex]:text-sm"
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeHighlight, rehypeKatex]}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
