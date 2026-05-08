// ── Message types ────────────────────────────────────────────────────────────
export type MessageRole = "user" | "bot" | "error";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
}

// ── Course ───────────────────────────────────────────────────────────────────
export interface Course {
  code: string;   // e.g. "CSE 101"
  name: string;   // e.g. "Introduction to Programming"
}

// ── API shapes ───────────────────────────────────────────────────────────────
export interface ChatRequest {
  message: string;
  course: string;
  session_id: string;
}

export interface ChatResponse {
  reply: string;
  confidence: number;
  source: string;
  session_id: string;
}
