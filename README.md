# UniBot - AI-Powered University Course Chatbot

UniBot answers student questions using local university course materials with a RAG pipeline. The frontend keeps the chat simple: users only type a question. The backend detects course codes such as `CSE220`, `CSE 220`, `CSE-220`, or `HST103`, resolves them to the indexed Chroma metadata course name, and searches globally when no course is mentioned.

## Pipeline

- Stage 1 ingestion: reads raw course files into `storage/stage1/unstructured_elements.jsonl`.
- Stage 2 chunking: creates retrieval chunks in `storage/stage2/chunks.jsonl`.
- Stage 3 embedding/storage: embeds chunks with `sentence-transformers/all-MiniLM-L6-v2` into Chroma at `vector_store/chroma`, collection `course_knowledge`.
- Stage 4 retrieval test: verifies vector search from the command line.
- Stage 5 Groq RAG: retrieves chunks, applies fallback checks, and generates answers with Groq.
- Stage 6 backend/frontend: exposes `POST /api/chat` and displays answers plus sources.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd frontend
npm install
cd ..
```

Create `.env` from `.env.example` and add your Groq key:

```powershell
Copy-Item .env.example .env
```

For a fresh clone on another PC, install dependencies first, then either:

- Copy your existing `raw/` course files and rerun Stages 1-3 to recreate `storage/` and `vector_store/`.
- Or copy an already-built `vector_store/chroma/` folder locally if you do not want to rebuild embeddings.

These data folders are intentionally ignored by git because they are large/generated and may contain course materials.

Required environment variables:

```env
GROQ_API_KEY=""
GROQ_MODEL="llama-3.3-70b-versatile"
CHROMA_DIR="vector_store/chroma"
CHROMA_COLLECTION="course_knowledge"
EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"
RAG_TOP_K="4"
RAG_DISTANCE_THRESHOLD="0.90"
RAG_MAX_CONTEXT_CHARS="8000"
RAG_MAX_OUTPUT_TOKENS="700"
RAG_TEMPERATURE="0.1"
```

## Run

Start the backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Start the frontend:

```powershell
cd frontend
npm run dev
```

Open `http://localhost:3000`.

## API

The frontend sends only the question and optional session id:

```json
{
  "question": "What is an array in CSE220?",
  "session_id": "optional-session-id"
}
```

The backend also tolerates optional `course` and `category` fields for API clients, but the UI does not expose a course selector.

Windows curl example:

```cmd
curl -X POST http://127.0.0.1:8000/api/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"What is an array in CSE220?\"}"
```

## CLI Checks

```powershell
.\.venv\Scripts\python.exe -m src.stage4_retrieval_test --query "What is an array?" --course CSE220_Data_Structure --top-k 5

.\.venv\Scripts\python.exe -m src.stage5_rag_answer_groq --query "What is an array?" --course CSE220 --top-k 4 --distance-threshold 0.90

.\.venv\Scripts\python.exe -m src.stage5_rag_answer_groq --query "What is an array in CSE220?" --top-k 4 --distance-threshold 0.90

.\.venv\Scripts\python.exe -m src.stage5_rag_answer_groq --query "Who is the president of France?" --top-k 4 --distance-threshold 0.90
```

## Tests

Normal tests mock Chroma retrieval and Groq, so they do not require raw files, Stage 1/2 outputs, the vector store, or a real API call.

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Optional live checks should only be run when `RUN_LIVE_RAG_TESTS=1`, `GROQ_API_KEY` is set, and `vector_store/chroma` exists.

## Data Hygiene

Do not commit secrets or generated course data. `.gitignore` excludes `.env`, raw course files, `storage/`, `vector_store/`, virtualenvs, Python caches, and frontend build output.
