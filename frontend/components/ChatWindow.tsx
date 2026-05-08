"use client";

import { useEffect, useRef } from "react";
import { Message } from "@/types";
import { MessageBubble } from "@/components/MessageBubble";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Bot, MessageSquare } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

interface ChatWindowProps {
  messages: Message[];
  isLoading: boolean;
}

/** Animated typing indicator shown while waiting for bot response */
function TypingIndicator() {
  return (
    <div className="flex items-start gap-2.5 px-4">
      <Avatar className="w-7 h-7 shrink-0 mt-0.5 bg-indigo-100 dark:bg-indigo-900/40">
        <AvatarFallback className="bg-indigo-100 dark:bg-indigo-900/40">
          <Bot size={14} className="text-indigo-600 dark:text-indigo-400" />
        </AvatarFallback>
      </Avatar>
      <div className="rounded-xl rounded-tl-sm bg-zinc-100 dark:bg-zinc-800 px-4 py-3 flex items-center gap-1.5 shadow-sm">
        <span className="typing-dot w-1.5 h-1.5 rounded-full bg-zinc-400 dark:bg-zinc-500" />
        <span className="typing-dot w-1.5 h-1.5 rounded-full bg-zinc-400 dark:bg-zinc-500" />
        <span className="typing-dot w-1.5 h-1.5 rounded-full bg-zinc-400 dark:bg-zinc-500" />
      </div>
    </div>
  );
}

/** Empty-state placeholder when only the welcome message exists */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-16 text-center px-8 select-none">
      <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-50 dark:bg-indigo-950/30 border border-indigo-100 dark:border-indigo-900">
        <MessageSquare size={28} className="text-indigo-400" />
      </div>
      <div className="space-y-1.5">
        <p className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
          No messages yet
        </p>
        <p className="text-xs text-zinc-400 dark:text-zinc-500 max-w-xs">
          Select a course from the sidebar, then type your question below to get started.
        </p>
      </div>
    </div>
  );
}

export function ChatWindow({ messages, isLoading }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Show empty state only when there are no messages beyond the welcome message
  const hasConversation = messages.length > 1;

  return (
    <ScrollArea className="flex-1 min-h-0">
      <div className="flex flex-col gap-4 py-6">
        {/* Messages */}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* Typing indicator */}
        {isLoading && <TypingIndicator />}

        {/* Empty state hint */}
        {!hasConversation && !isLoading && <EmptyState />}

        {/* Scroll anchor */}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
