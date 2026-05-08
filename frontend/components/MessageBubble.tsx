"use client";

import { Message } from "@/types";
import { cn } from "@/lib/utils";
import { Bot, AlertCircle } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

interface MessageBubbleProps {
  message: Message;
}

/**
 * Renders inline markdown-lite: **bold** and `code` and ```code block```.
 */
function parseMarkdown(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  // Split on code blocks first
  const codeBlockRegex = /```([\s\S]*?)```/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = codeBlockRegex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(...parseInline(text.slice(lastIndex, match.index)));
    }
    parts.push(
      <pre
        key={`cb-${match.index}`}
        className="my-2 rounded-lg bg-zinc-900 dark:bg-zinc-950 px-4 py-3 text-xs text-zinc-100 overflow-x-auto"
      >
        <code>{match[1].trim()}</code>
      </pre>
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(...parseInline(text.slice(lastIndex)));
  }

  return parts;
}

function parseInline(text: string): React.ReactNode[] {
  const result: React.ReactNode[] = [];
  const inlineRegex = /(\*\*(.+?)\*\*|`(.+?)`)/g;
  let last = 0;
  let m: RegExpExecArray | null;

  while ((m = inlineRegex.exec(text)) !== null) {
    if (m.index > last) {
      result.push(
        <span key={`t-${last}`}>{text.slice(last, m.index)}</span>
      );
    }
    if (m[2]) {
      result.push(<strong key={`b-${m.index}`}>{m[2]}</strong>);
    } else if (m[3]) {
      result.push(
        <code
          key={`c-${m.index}`}
          className="rounded bg-zinc-200 dark:bg-zinc-700 px-1 py-0.5 text-[11px] font-mono"
        >
          {m[3]}
        </code>
      );
    }
    last = m.index + m[0].length;
  }

  if (last < text.length) {
    result.push(<span key={`t-${last}`}>{text.slice(last)}</span>);
  }

  return result;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isError = message.role === "error";

  if (isUser) {
    return (
      <div className="message-bubble flex justify-end gap-2 px-4">
        <div className="max-w-[72%] flex flex-col items-end gap-1">
          <div className="rounded-xl rounded-tr-sm bg-indigo-600 text-white px-4 py-2.5 text-sm leading-relaxed shadow-sm">
            {message.content}
          </div>
          <span className="text-[10px] text-zinc-400 dark:text-zinc-500 pr-1">
            {formatTime(message.timestamp)}
          </span>
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="message-bubble flex items-start gap-2.5 px-4">
        <div className="flex items-center justify-center w-7 h-7 rounded-full bg-red-100 dark:bg-red-900/30 shrink-0 mt-0.5">
          <AlertCircle size={14} className="text-red-500" />
        </div>
        <div className="max-w-[72%] flex flex-col gap-1">
          <div className="rounded-xl rounded-tl-sm bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-2.5 text-sm leading-relaxed">
            {message.content}
          </div>
          <span className="text-[10px] text-zinc-400 dark:text-zinc-500 pl-1">
            {formatTime(message.timestamp)}
          </span>
        </div>
      </div>
    );
  }

  // Bot message
  return (
    <div className="message-bubble flex items-start gap-2.5 px-4">
      <Avatar className="w-7 h-7 shrink-0 mt-0.5 bg-indigo-100 dark:bg-indigo-900/40">
        <AvatarFallback className="bg-indigo-100 dark:bg-indigo-900/40">
          <Bot size={14} className="text-indigo-600 dark:text-indigo-400" />
        </AvatarFallback>
      </Avatar>
      <div className="max-w-[72%] flex flex-col gap-1">
        <div className="rounded-xl rounded-tl-sm bg-zinc-100 dark:bg-zinc-800 px-4 py-2.5 text-sm leading-relaxed text-zinc-800 dark:text-zinc-200 shadow-sm">
          {parseMarkdown(message.content)}
        </div>
        <span className="text-[10px] text-zinc-400 dark:text-zinc-500 pl-1">
          {formatTime(message.timestamp)}
        </span>
      </div>
    </div>
  );
}
