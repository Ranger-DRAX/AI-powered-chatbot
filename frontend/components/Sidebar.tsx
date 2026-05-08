"use client";

import { GraduationCap, Moon, Sun, BookOpen } from "lucide-react";
import { useTheme } from "next-themes";
import { Course } from "@/types";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const COURSES: Course[] = [
  { code: "CSE 220", name: "Data Structure" },
  { code: "CSE 221", name: "Algorithm" },
  { code: "CSE 340", name: "Computer Architecture" },
  { code: "CSE 341", name: "Microprocessors" },
  { code: "CSE 420", name: "Compiler" },
  { code: "CSE 422", name: "Artificial Intelligence" },
  { code: "CSE 423", name: "Computer Graphics" },
  { code: "CSE 440", name: "NLP" },
  { code: "CSE 470", name: "System Design and Analysis" },
  { code: "CSE 471", name: "Software Engineering" },
  { code: "HST 103", name: "History of Bangladesh" },
];

interface SidebarProps {
  selectedCourse: Course | null;
  onSelectCourse: (course: Course) => void;
}

export function Sidebar({ selectedCourse, onSelectCourse }: SidebarProps) {
  const { theme, setTheme } = useTheme();

  return (
    <aside
      className="flex flex-col w-[240px] shrink-0 border-r border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 h-full"
      aria-label="Course sidebar"
    >
      {/* ── Brand ─────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-600 text-white shrink-0">
          <GraduationCap size={16} strokeWidth={2.5} />
        </div>
        <span className="text-base font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
          UniBot
        </span>
      </div>

      <Separator className="bg-zinc-100 dark:bg-zinc-800" />

      {/* ── Courses list ──────────────────────────────────────────────── */}
      <nav className="flex flex-col gap-0.5 px-2 py-3 flex-1 overflow-y-auto">
        <p className="px-2 pb-2 text-[10px] font-semibold uppercase tracking-widest text-zinc-400 dark:text-zinc-500">
          Courses
        </p>

        {COURSES.map((course) => {
          const isActive =
            selectedCourse?.code === course.code;

          return (
            <button
              key={course.code}
              id={`course-${course.code.replace(" ", "-")}`}
              onClick={() => onSelectCourse(course)}
              className={cn(
                "flex items-start gap-2.5 w-full rounded-lg px-2.5 py-2 text-left transition-colors duration-150",
                isActive
                  ? "bg-indigo-50 dark:bg-indigo-950/50 text-indigo-700 dark:text-indigo-300"
                  : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-100"
              )}
              aria-current={isActive ? "true" : undefined}
            >
              <BookOpen
                size={14}
                className={cn(
                  "mt-0.5 shrink-0",
                  isActive
                    ? "text-indigo-500"
                    : "text-zinc-400 dark:text-zinc-500"
                )}
              />
              <span className="flex flex-col gap-0.5">
                <span
                  className={cn(
                    "text-xs font-semibold",
                    isActive
                      ? "text-indigo-700 dark:text-indigo-300"
                      : "text-zinc-700 dark:text-zinc-300"
                  )}
                >
                  {course.code}
                </span>
                <span className="text-[11px] leading-tight text-zinc-500 dark:text-zinc-500">
                  {course.name}
                </span>
              </span>
            </button>
          );
        })}
      </nav>

      <Separator className="bg-zinc-100 dark:bg-zinc-800" />

      {/* ── Theme toggle ──────────────────────────────────────────────── */}
      <div className="px-3 py-3">
        <TooltipProvider delayDuration={300}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                id="theme-toggle"
                variant="ghost"
                size="sm"
                className="w-full justify-start gap-2 text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100"
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              >
                {theme === "dark" ? (
                  <Sun size={14} />
                ) : (
                  <Moon size={14} />
                )}
                <span className="text-xs">
                  {theme === "dark" ? "Light mode" : "Dark mode"}
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
