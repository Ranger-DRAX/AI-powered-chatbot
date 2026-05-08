"use client";

import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { ChatWindow } from "@/components/ChatWindow";
import { ChatInput } from "@/components/ChatInput";
import { Separator } from "@/components/ui/separator";
import { sendChatMessage } from "@/lib/api";
import { Message } from "@/types";
import { v4 as uuidv4 } from "uuid";

const SESSION_ID = uuidv4();

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  role: "bot",
  content:
    "Hi! I'm **UniBot**. Ask me anything about your university courses! (e.g. 'What is an array in CSE220?')",
  timestamp: new Date(0),
};

export default function HomePage() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMsg: Message = {
      id: uuidv4(),
      role: "user",
      content: text.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      const data = await sendChatMessage({
        question: text.trim(),
        session_id: SESSION_ID,
      });

      const botMsg: Message = {
        id: uuidv4(),
        role: "bot",
        content: data.answer,
        timestamp: new Date(),
        sources: data.sources,
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      const errMsg: Message = {
        id: uuidv4(),
        role: "error",
        content:
          err instanceof Error
            ? err.message
            : "Something went wrong. Please try again.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <Sidebar />

      {/* Main chat area */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Header bar */}
        <header className="flex items-center gap-3 px-5 py-3 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
          <h1 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            Chat
          </h1>
        </header>

        <Separator className="bg-zinc-200 dark:bg-zinc-800" />

        {/* Messages */}
        <ChatWindow messages={messages} isLoading={isLoading} />

        <Separator className="bg-zinc-200 dark:bg-zinc-800" />

        {/* Input */}
        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </div>
    </div>
  );
}
