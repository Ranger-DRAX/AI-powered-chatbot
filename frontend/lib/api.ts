import { ChatRequest, ChatResponse } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Send a chat message to the FastAPI backend.
 * Throws an Error (with a user-friendly message) on network or API failure.
 */
export async function sendChatMessage(
  payload: ChatRequest
): Promise<ChatResponse> {
  let response: Response;

  try {
    response = await fetch(`${API_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error(
      "Unable to reach the UniBot server. Please make sure the backend is running."
    );
  }

  if (!response.ok) {
    const text = await response.text().catch(() => "Unknown error");
    throw new Error(
      `Server responded with ${response.status}: ${text}`
    );
  }

  const data: ChatResponse = await response.json();
  return data;
}
