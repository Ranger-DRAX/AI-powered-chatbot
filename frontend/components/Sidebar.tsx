"use client";

import { useEffect, useState } from "react";
import { GraduationCap, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

export function Sidebar() {
  const [mounted, setMounted] = useState(false);
  const { resolvedTheme, setTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <aside
      className="flex flex-col w-[240px] shrink-0 border-r border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 h-full"
      aria-label="Course sidebar"
    >
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-600 text-white shrink-0">
          <GraduationCap size={16} strokeWidth={2.5} />
        </div>
        <span className="text-base font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
          UniBot
        </span>
      </div>

      <Separator className="bg-zinc-100 dark:bg-zinc-800" />

      {/* App description */}
      <div className="flex flex-col gap-2 px-4 py-4 flex-1">
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Welcome to UniBot! You can ask questions about your university courses. Simply type your question and I will automatically figure out what course you are referring to.
          </p>
      </div>

      <Separator className="bg-zinc-100 dark:bg-zinc-800" />

      {/* Theme toggle */}
      <div className="px-3 py-3">
        <TooltipProvider delayDuration={300}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                id="theme-toggle"
                variant="ghost"
                size="sm"
                className="w-full justify-start gap-2 text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
                onClick={() => setTheme(isDark ? "light" : "dark")}
                disabled={!mounted}
              >
                {mounted && isDark ? (
                  <Sun size={14} />
                ) : (
                  <Moon size={14} />
                )}
                <span className="text-xs">
                  {mounted && isDark ? "Light mode" : "Dark mode"}
                </span>
              </Button>
            </TooltipTrigger>
            <TooltipContent side="right">
              Toggle theme
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </aside>
  );
}
