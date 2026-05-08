export type MessageRole = "user" | "bot" | "error";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  sources?: Source[];
}

export interface Source {
  course: string;
  category: string;
  file_name: string;
  source_path: string;
  page_start: string;
  page_end: string;
  distance: number | null;
  chunk_id: string;
}

export interface ChatRequest {
  question: string;
  session_id?: string;
  course?: string | null;
  category?: string | null;
}

export interface ChatResponse {
  answer: string;
  status: "answered" | "fallback" | "error" | string;
  question: string;
  detected_course_code?: string | null;
  resolved_course?: string | null;
  category?: string | null;
  retrieval_mode: "course_filtered" | "global" | string;
  retrieved_chunks: number;
  best_distance: number | null;
  sources: Source[];
}
