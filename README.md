# Daraz Shopping Assistant — Conversational AI System

**Course:** CS 4063 — Natural Language Processing
**University:** FAST NUCES
**Assignment:** Local CPU-Optimised Conversational AI System

| Member | Roll No |
|---|---|
| Awwab Ahmad | 23i-0079 |
| Rayan Ahmad | 23i-0018 |
| Uwaid Muneer | 23i-2574 |

---

## Overview

A fully local, CPU-optimised conversational AI system built for Daraz.pk — Pakistan's largest online marketplace. The system runs a quantized open-weight LLM entirely on CPU, exposes a real-time WebSocket API, maintains conversation state across turns with SQLite persistence, and serves a React-based chat interface. No cloud APIs, no RAG, no external tools — all intelligence comes from prompt engineering and context window management.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          User Browser                           │
│                     React + Vite Frontend                       │
│   SessionSidebar │ ChatWindow │ MessageBubble │ InputBar        │
│              WebSocket + REST API  (utils/api.js)               │
└────────────────────────────┬────────────────────────────────────┘
                             │ ws://localhost:8000/ws/chat
                             │ http://localhost:8000/
┌────────────────────────────▼────────────────────────────────────┐
│                       FastAPI Backend                           │
│                                                                 │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────────┐  │
│  │  POST /chat  │  │  WS /ws/chat  │  │  Debug / Sessions   │  │
│  └──────┬───────┘  └──────┬────────┘  └─────────────────────┘  │
│         └─────────────────┘                                     │
│                      │                                          │
│  ┌───────────────────▼──────────────────────────────────────┐   │
│  │                  LLM Engine  (llm/engine.py)              │   │
│  │                                                           │   │
│  │   ┌─────────────────────────────────────────────────┐    │   │
│  │   │  stream()  ──► lifecycle guards                 │    │   │
│  │   │              ──► build_inference_payload()      │    │   │
│  │   │              ──► build_chatml_prompt()          │    │   │
│  │   │              ──► Llama() token generator        │    │   │
│  │   │              ──► extract_and_strip_state()      │    │   │
│  │   │              ──► _persist_turn()                │    │   │
│  │   │              ──► _update_lifecycle()            │    │   │
│  │   └─────────────────────────────────────────────────┘    │   │
│  │   generate()  wraps stream() for REST (non-streaming)     │   │
│  └───────────────────┬──────────────────────────────────────┘   │
│                      │                                          │
│  ┌───────────────────▼──────────────────────────────────────┐   │
│  │           Conversation Manager  (memory/context.py)       │   │
│  │                                                           │   │
│  │  active_chats{}  ◄──► SQLite  (memory/database.py)        │   │
│  │  - get_or_create_session()   loads from DB if not cached  │   │
│  │  - build_inference_payload() sliding window (last 10 msg) │   │
│  │  - extract_and_strip_state() <STATE> regex extraction     │   │
│  │  - is_conversation_resolved() Resolved: yes detection     │   │
│  │  - add_message_to_chat()     appends + persists to SQLite │   │
│  └───────────────────┬──────────────────────────────────────┘   │
│                      │                                          │
│  ┌───────────────────▼──────────────────────────────────────┐   │
│  │           Persistence Layer  (memory/database.py)         │   │
│  │                                                           │   │
│  │  SQLite  ──  data/sessions.db  (WAL mode)                 │   │
│  │  Tables: sessions, messages                               │   │
│  │  - save_session()    upsert session + replace messages    │   │
│  │  - load_session()    single session restore               │   │
│  │  - list_sessions()   sidebar history (title, preview)     │   │
│  │  - delete_session()  cascade delete                       │   │
│  │  - load_all_sessions_to_memory()  startup preload         │   │
│  └───────────────────┬──────────────────────────────────────┘   │
│                      │                                          │
│  ┌───────────────────▼──────────────────────────────────────┐   │
│  │              LLM Inference Layer                          │   │
│  │         llama-cpp-python  (CPU, 4 threads)                │   │
│  │      Qwen2.5-3B-Instruct-Q4_K_M.gguf  (~2GB)             │   │
│  │      ThreadPoolExecutor(max_workers=1) — async-safe       │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

**Frontend (`frontend/src/`)** — React + Vite chat interface. `SessionSidebar` displays previous chats loaded from the backend. `ChatWindow` + `MessageBubble` handle real-time streaming display. `useChat.js` manages WebSocket lifecycle. `InputBar` is disabled automatically when session `status` reaches `"ended"`.

**Backend API (`backend/app/api/routes.py`)** — FastAPI service exposing REST (`/chat`), WebSocket (`/ws/chat`), session history (`/sessions`), and debug endpoints. All inference runs inside a `ThreadPoolExecutor(max_workers=1)` to keep llama-cpp-python single-threaded while remaining async-compatible.

**LLM Engine (`backend/app/llm/engine.py`)** — Single-pass streaming pipeline. `stream()` is the core method: it checks lifecycle guards, builds the prompt, runs token-by-token generation via `Llama()`, extracts the `<STATE>` tag from the completed response, persists the turn, and updates session lifecycle. `generate()` is a non-streaming wrapper that collects all tokens for the REST endpoint.

**Conversation Manager (`backend/app/memory/context.py`)** — In-memory session store (`active_chats` dict) backed by SQLite. On every request it attempts to load missing sessions from the database before creating a new one. After every mutation (message append, status change, turn increment) the session is synchronously persisted via `_persist()`.

**Persistence Layer (`backend/app/memory/database.py`)** — SQLite with WAL mode for concurrent reads. Two tables: `sessions` (metadata, state JSON, turn count, status) and `messages` (full history). Sessions are loaded back into memory on server startup via `init_sessions_from_db()`. Titles are auto-generated from the first user message (truncated to 50 chars).

**Core Config (`backend/app/core/config.py`)** — All tuneable constants, the base system prompt with four conversation phases, `build_system_prompt()` which injects known facts back into the prompt, and `build_chatml_prompt()` which formats the message list into the ChatML token format Qwen expects.

---

## Model Selection

| Property | Value |
|---|---|
| Model | Qwen2.5-3B-Instruct |
| Quantization | Q4_K_M |
| Format | GGUF |
| File size | ~2.0 GB |
| Context length (trained) | 32,768 tokens |
| Context length (used) | 2,048 tokens (`N_CTX = 2048`) |
| Inference threads | 4 (`N_THREADS = 4`) |
| Batch size | 1024 (`N_BATCH = 1024`) |
| Temperature | 0.7 |
| Top-P | 0.9 |
| Repeat penalty | 1.1 |
| Max output tokens | 512 (`MAX_TOKENS = 512`) |
| Inference backend | llama-cpp-python |
| Hardware | CPU only (AMD Ryzen 7, 8 cores) |

**Why Qwen2.5-3B-Instruct-Q4_K_M:**
- Smallest model with reliable instruction following and ChatML format support for a structured business chatbot
- Q4_K_M mixed-precision k-quants preserve quality better than Q4_0 at the same file size
- 2GB RAM footprint fits comfortably alongside the OS on an 8GB machine
- Qwen2.5 instruction-tuned variant respects the `<STATE>` tag format and system prompt constraints significantly more reliably than base models of the same size
- `MAX_TOKENS = 512` gives the model enough room to write a full reply plus the mandatory `<STATE>` tag without truncation

---

## Context Memory Management

The system uses a three-layer strategy to preserve facts across turns without any retrieval or external knowledge base.

**Layer 1 — Sliding Window (`SLIDING_WINDOW_SIZE = 10`):** Only the last 10 messages (5 full exchanges) are included in each inference call. Older messages are dropped. This keeps prompt size bounded and inference latency stable regardless of conversation length.

**Layer 2 — STATE Injection:** The model is instructed to append a structured tag to every response:

```
<STATE>Budget: [amount], Item: [product], Preferences: [facts], Resolved: [yes/no]</STATE>
```

This tag is intercepted in `extract_and_strip_state()` using a forgiving regex that handles truncated output:

```python
_STATE_PATTERN = re.compile(r"<STATE>\s*(.*?)(?:</STATE>|$)", re.DOTALL | re.IGNORECASE)
```

Parsed values are stored in `session["state"]`. Before each inference call, `build_system_prompt()` reads this dict and appends a `## Already Known About This User` block to the system prompt — so budget, item, and preferences survive sliding window trimming.

**Layer 3 — SQLite Persistence:** Every mutation (message, state update, status change) is written to `data/sessions.db` synchronously. On server restart, `init_sessions_from_db()` reloads all sessions into `active_chats`, so no conversation context is lost across reboots.

```
User message
    │
    ▼
Lifecycle guards (model loaded? session ended? turn limit hit?)
    │
    ▼
build_inference_payload()
  ├── system prompt  ◄── STATE-injected known facts
  ├── sliding window (last 10 messages from history)
  └── new user message
    │
    ▼
build_chatml_prompt()  →  <|im_start|>...<|im_end|> format
    │
    ▼
Llama() token stream  (ThreadPoolExecutor, async-safe)
    │
    ▼
extract_and_strip_state()
  ├── regex match → update session["state"]
  └── strip <STATE> + <think> tags → clean response
    │
    ▼
_persist_turn()  →  add_message_to_chat()  →  SQLite
    │
    ▼
_update_lifecycle()
  ├── Resolved: yes  →  status = "closing"
  └── turns >= MAX_TURNS  →  status = "ended"
    │
    ▼
Clean response → WebSocket stream → user
```

---

## Setup Instructions

### Prerequisites

- Docker and Docker Compose installed
- Git
- ~4GB free RAM
- ~3GB free disk space

### Step 1: Clone the Repository

```bash
git clone <your-github-repo-url>
cd Service_based_conversational_ai_NLP
```

### Step 2: Download the Model

```bash
pip install huggingface_hub
python -c "
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='Qwen/Qwen2.5-3B-Instruct-GGUF',
    filename='qwen2.5-3b-instruct-q4_k_m.gguf',
    local_dir='./models'
)
print('Done!')
"
```

### Step 3: Build and Run

```bash
docker compose up --build
```

### Step 4: Access the System

| Service | URL |
|---|---|
| Frontend chat UI | http://localhost:3000 |
| Backend Swagger UI | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |
| Postman collection | `Postman_Collection.json` (root of repo) |

### Step 5: Warmup (recommended)

```bash
curl -X POST http://localhost:8000/debug/warmup
```

First inference takes ~6815 ms due to KV cache initialisation. Warmup before benchmarking or demoing to reach steady-state latency.

---

## API Reference

### POST `/chat`
Non-streaming REST endpoint. Internally calls `engine.generate()` which wraps `stream()` and collects all tokens before returning.

**Request:**
```json
{
  "session_id": "abc-123",
  "message": "I need a phone under 30000 PKR"
}
```

**Response:**
```json
{
  "session_id": "abc-123",
  "response": "For a phone under 30,000 PKR, consider the Xiaomi Redmi Note series...",
  "latency_ms": 3438.09,
  "status": "active",
  "turns_used": 1,
  "turns_max": 15
}
```

> `turns_max` is **15** (`MAX_TURNS = 15` in `config.py`).

---

### WebSocket `/ws/chat`
Streaming endpoint. Each token is yielded individually as it is generated. The final frame carries full metadata.

**Send:**
```json
{"session_id": "abc-123", "message": "I need earbuds under 3000 PKR"}
```

**Receive (per token):**
```json
{"token": "For", "done": false}
```

**Receive (final frame):**
```json
{
  "token": "",
  "done": true,
  "full_response": "For earbuds under 3000 PKR...",
  "latency_ms": 3241.2,
  "session_id": "abc-123",
  "status": "active",
  "turns_used": 1,
  "turns_max": 15
}
```

**Receive (cancelled — client disconnects mid-stream):**
```json
{"token": "", "done": true, "cancelled": true, "session_id": "abc-123", "status": "active"}
```

The partial response is saved to history even on cancellation.

---

### POST `/reset`
Clears the in-memory session. The old session remains in SQLite for history viewing; the client should generate a new UUID for the next conversation.

```json
{"session_id": "abc-123"}
```

---

### GET `/session/welcome/{session_id}`
Returns the welcome message for new sessions. Called by the frontend on chat open. Does not consume a turn.

**Response:**
```json
{
  "session_id": "abc-123",
  "response": "Hi! I'm Daraz Assistant 🛍️ ...",
  "latency_ms": 0.0,
  "status": "active",
  "turns_used": 0,
  "turns_max": 15
}
```

---

### GET `/sessions`
Returns all sessions ordered by most recently updated. Used by `SessionSidebar` to populate the chat history panel.

**Response (per entry):**
```json
{
  "session_id": "abc-123",
  "title": "I need a phone under 30000 PKR...",
  "status": "active",
  "turns": 3,
  "message_count": 6,
  "created_at": "2025-01-01T10:00:00+00:00",
  "updated_at": "2025-01-01T10:05:00+00:00",
  "preview": "Great choice! The Redmi Note 13 is available..."
}
```

---

### DELETE `/sessions/{session_id}`
Permanently deletes a session and all its messages from SQLite (cascade delete).

---

### POST `/benchmark?runs=5`
Runs N inference calls and returns latency statistics. Use to generate benchmark numbers.

---

### POST `/debug/warmup`
Triggers a dummy inference call to initialise the KV cache. Call once after server start before demoing.

---

## Performance Benchmarks

> Tested on AMD Ryzen 7 (8 cores), 8GB RAM, CPU-only inference, 4 inference threads (`N_THREADS = 4`).

### Inference Latency

| Metric | Value |
|---|---|
| Average latency | 3438.09 ms |
| Minimum latency | 3102.45 ms |
| Maximum latency | 4201.33 ms |
| P50 latency | 3380.60 ms |
| P95 latency | 3837.89 ms |
| Cold start (first inference) | 6815.94 ms |

*Generated via `POST /benchmark?runs=10`. Cold start is a one-time cost on server boot.*

### Stress Test Results (Locust)

| Metric | Value |
|---|---|
| Concurrent users tested | 10 |
| Requests per second | ~2.9 |
| Average response time | 3438 ms |
| Failure rate | 0% |

*Generated via `locust -f backend/test/locust.py --host=http://localhost:8000`.*

### Context Memory Accuracy

| Test | Result |
|---|---|
| Budget retained across 10 turns | ✅ Pass |
| Item retained after topic change | ✅ Pass |
| Preferences not re-asked after STATE injection | ✅ Pass |
| Off-topic refusal (medical query) | ✅ Pass |
| Off-topic refusal (selling request) | ✅ Pass |
| Session isolation (concurrent users) | ✅ Pass |
| Session restored from SQLite after restart | ✅ Pass |

---

## Failure Handling

| Failure Type | Code Location | Handling |
|---|---|---|
| Model file not found | `engine._load_model()` | `self.model = None`; every subsequent request returns a graceful "temporarily unavailable" message |
| Session already ended | `engine._check_lifecycle_guards()` | Returns `status: "ended"` message immediately, skips inference |
| Turn limit reached (`turns >= MAX_TURNS`) | `engine._check_lifecycle_guards()` | Farewell message sent, `status` set to `"ended"`, frontend `InputBar` disables |
| Client disconnects mid-stream | `engine.stream()` — `asyncio.CancelledError` | Partial response stripped of `<STATE>` and saved to history; cancellation frame sent |
| Inference exception | `engine.stream()` — bare `Exception` | Logged, error frame returned with `status: "error"`, connection kept alive |
| Invalid JSON over WebSocket | `routes.py` | Error message returned, connection kept alive |
| SQLite write failure | `database._persist()` | Logged as error; in-memory session continues unaffected — data loss risk is isolated to persistence only |
| `<STATE>` tag absent or truncated | `context.extract_and_strip_state()` | Forgiving regex (`(?:</STATE>|$)`) matches partial tags; warning logged; prior state retained |
| Concurrent inference requests | `ThreadPoolExecutor(max_workers=1)` | Requests queue behind the single worker; no race condition on the model object |

---

## Project Structure

```
Service_based_conversational_ai_NLP/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py          # REST + WebSocket endpoints
│   │   ├── core/
│   │   │   └── config.py          # System prompt, ChatML builder, constants
│   │   ├── llm/
│   │   │   └── engine.py          # Streaming LLM pipeline, lifecycle guards
│   │   ├── memory/
│   │   │   ├── context.py         # Session store, sliding window, STATE extraction
│   │   │   └── database.py        # SQLite CRUD (sessions + messages tables)
│   │   └── main.py                # FastAPI app, startup hooks (init_sessions_from_db)
│   ├── test/
│   │   └── locust.py              # Stress testing
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── SessionSidebar.jsx # Chat history panel (calls GET /sessions)
│   │   │   ├── ChatWindow.jsx     # Message display
│   │   │   ├── MessageBubble.jsx  # Individual message rendering
│   │   │   ├── InputBar.jsx       # Disabled on status = "ended"
│   │   │   └── ...
│   │   ├── hooks/
│   │   │   └── useChat.js         # WebSocket lifecycle management
│   │   └── utils/
│   │       └── api.js             # REST + WS helpers
│   ├── Dockerfile
│   └── package.json
├── data/
│   └── sessions.db                # SQLite database (auto-created)
├── models/
│   └── qwen2.5-3b-instruct-q4_k_m.gguf   # Model file (not in git)
├── Postman_Collection.json        # API test collection
├── docker-compose.yml
└── README.md
```

---

## Known Limitations

- **Single model instance:** `ThreadPoolExecutor(max_workers=1)` serialises all inference. Concurrent users queue — the second user waits while the first user's response generates. Observed throughput under load is ~2.9 req/s. For horizontal scaling, replace with a model server (e.g. llama.cpp server, vLLM).
- **Cold start overhead:** First inference after server boot takes ~6.8 seconds due to KV cache initialisation. Use `POST /debug/warmup` before demos.
- **In-memory primary store:** `active_chats` is process-local. For multi-instance deployment, replace with Redis: `r.hset(session_id, mapping=session_data)`.
- **CPU-only inference:** Steady-state latency is 3–4 seconds per response with 4 threads on a Ryzen 7. A GPU would reduce this to under 1 second.
- **Context window cap:** `N_CTX = 2048` (model supports 32,768) to stay within RAM budget. Responses exceeding this will be truncated. `MAX_TOKENS = 512` is reserved for output, leaving ~1,500 tokens for prompt + history.
- **3B parameter limit:** Occasional instruction-following failures on ambiguous or multi-part requests. The `<STATE>` tag may be malformed or omitted — the forgiving regex in `extract_and_strip_state()` handles partial tags, and prior state is retained on miss.
- **No authentication:** Session IDs are client-generated UUIDs with no auth layer. Not suitable for public deployment without adding middleware.
- **No RAG or live inventory:** Per assignment constraints, all product knowledge is from the model's training data. Specific Daraz listings, prices, and availability cannot be verified in real time.