"use client";

import {
  useRef,
  useState,
  useCallback,
  KeyboardEvent,
  ChangeEvent,
} from "react";
import { Button } from "@/components/ui/button";
import { SendHorizonal, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

const MAX_CHARS = 1000;
const MAX_ROWS = 4;
const LINE_HEIGHT_PX = 24; // matches text-sm line-height
const BASE_HEIGHT_PX = 40;

interface ChatInputProps {
  onSend: (text: string) => void;
  isLoading: boolean;
}

export function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const charCount = value.length;
  const isEmpty = value.trim().length === 0;
  const isDisabled = isEmpty || isLoading;

  /** Auto-resize the textarea up to MAX_ROWS */
  const resize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const maxH = BASE_HEIGHT_PX + LINE_HEIGHT_PX * (MAX_ROWS - 1);
    el.style.height = `${Math.min(el.scrollHeight, maxH)}px`;
  }, []);

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    if (e.target.value.length <= MAX_CHARS) {
      setValue(e.target.value);
      resize();
    }
  };

  const handleSend = () => {
    if (isDisabled) return;
    onSend(value);
    setValue("");
    // Reset height
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const nearLimit = charCount >= MAX_CHARS * 0.9;

  return (
    <div className="px-4 py-3 bg-white dark:bg-zinc-900">
      <div
        className={cn(
          "flex items-end gap-2 rounded-2xl border px-3 py-2 transition-colors",
          "border-zinc-200 dark:border-zinc-700",
          "focus-within:border-indigo-400 dark:focus-within:border-indigo-600",
          "bg-zinc-50 dark:bg-zinc-800"
        )}
      >
        {/* Textarea */}
        <textarea
          id="chat-input"
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your course materials, e.g., What is an array in CSE220?"
          rows={1}
          disabled={isLoading}
          className={cn(
            "flex-1 resize-none bg-transparent text-sm leading-6 outline-none",
            "placeholder:text-zinc-400 dark:placeholder:text-zinc-500",
            "text-zinc-900 dark:text-zinc-100",
            "disabled:opacity-60"
          )}
          style={{ minHeight: `${BASE_HEIGHT_PX - 16}px` }}
          aria-label="Chat message input"
        />

        {/* Right side: char count + send button */}
        <div className="flex flex-col items-end gap-1 shrink-0">
          <span
            className={cn(
              "text-[10px] tabular-nums",
              nearLimit ? "text-amber-500" : "text-zinc-400 dark:text-zinc-500"
            )}
          >
            {charCount}/{MAX_CHARS}
          </span>
          <Button
            id="send-button"
            size="sm"
            disabled={isDisabled}
            onClick={handleSend}
            className={cn(
              "h-8 w-8 p-0 rounded-xl",
              "bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40",
              "transition-all duration-150"
            )}
            aria-label="Send message"
          >
            {isLoading ? (
              <Loader2 size={14} className="animate-spin text-white" />
            ) : (
              <SendHorizonal size={14} className="text-white" />
            )}
          </Button>
        </div>
      </div>

      <p className="mt-1.5 text-[10px] text-zinc-400 dark:text-zinc-500 text-center">
        UniBot may make mistakes. Always verify with your instructor.
      </p>
    </div>
  );
}
