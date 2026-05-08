# UniBot — University Course Chatbot

An AI-powered chatbot that answers student questions about university courses. Built with **Next.js 16** (frontend) and **FastAPI** (backend). This is **Phase 1**: a fully working chat UI backed by a smart dummy response engine — no LLM yet.

---

## Features

- 🎓 Course-aware conversations (5 mock CSE courses)
- 💬 Real-time chat UI with animated message bubbles
- 🌙 Dark / Light mode toggle
- ⌨️ Auto-resizing input with character count
- 🔄 Typing indicator with bounce animation
- 📱 Keyword-based intelligent dummy responses
- ⚡ Sub-second simulated response latency

---

## Project Structure

```
university-chatbot/
├── frontend/     ← Next.js 16 + TypeScript + Tailwind + shadcn/ui
└── backend/      ← FastAPI + Uvicorn + Pydantic
```

---

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.10+

---

### 1. Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Copy env file
copy .env.example .env

# Start the server
uvicorn main:app --reload --port 8000
```

Backend will be available at: **http://localhost:8000**

Health check: **http://localhost:8000/health**

Interactive API docs: **http://localhost:8000/docs**

---

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy env file
copy .env.example .env.local

# Start the dev server
npm run dev
```

Frontend will be available at: **http://localhost:3000**

---

## API Documentation

| Endpoint       | Method | Description              |
|----------------|--------|--------------------------|
| `/health`      | GET    | Health check             |
| `/api/chat`    | POST   | Send a chat message      |

### POST `/api/chat`

**Request Body:**

```json
{
  "message": "What is a linked list?",
  "course": "CSE 203 — Data Structures",
  "session_id": "abc-123"
}
```

**Response:**

```json
{
  "reply": "Great question! In CSE 203 — Data Structures, ...",
  "confidence": 0.87,
  "source": "dummy_knowledge_base",
  "session_id": "abc-123"
}
```

---

## Roadmap

- **Phase 2**: Integrate a real LLM (OpenAI / Groq)
- **Phase 3**: Add vector database (Pinecone / Chroma) for course document retrieval
- **Phase 4**: File upload (PDFs, slides)
- **Phase 5**: Authentication + user history

---

## Tech Stack

| Layer     | Technology                          |
|-----------|-------------------------------------|
| Frontend  | Next.js 16, TypeScript, Tailwind CSS|
| UI        | shadcn/ui, Radix UI, Lucide Icons   |
| Themes    | next-themes                         |
| Backend   | FastAPI, Uvicorn                    |
| Validation| Pydantic v2                         |
