# Daraz Shopping Assistant — Conversational AI System

**Course:** CS 4063 — Natural Language Processing
**University:** FAST NUCES
**Assignment:** Local CPU-Optimised Conversational AI System

| Member | Roll No |
|---|---|
| Awwab Ahmad | 23i-0079 |
| Rayan Ahmad | 23i-0018 |
| Uwaid Muneer| 23i-2574 |

---

## Overview

A fully local, CPU-optimised conversational AI system built for Daraz.pk — Pakistan's largest online marketplace. The system runs a quantized open-weight LLM entirely on CPU, exposes a real-time WebSocket API, maintains conversation state across turns, and serves a React-based chat interface. No cloud APIs, no RAG, no external tools — all intelligence comes from prompt engineering and context window management.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Browser                         │
│                   React + Vite Frontend                     │
│              WebSocket + REST API Integration               │
└──────────────────────────┬──────────────────────────────────┘
                           │ ws://localhost:8000/ws/chat
                           │ http://localhost:8000/chat
┌──────────────────────────▼──────────────────────────────────┐
│                     FastAPI Backend                         │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  REST /chat │  │  WS /ws/chat │  │  Debug Endpoints │   │
│  └──────┬──────┘  └──────┬───────┘  └──────────────────┘   │
│         └────────────────┘                                  │
│                    │                                        │
│  ┌─────────────────▼────────────────────────────────────┐   │
│  │                  LLM Engine (engine.py)               │   │
│  │                                                       │   │
│  │  Stage 1: Intent Classifier  (max_tokens=5, temp=0)  │   │
│  │       ↓ shopping              ↓ off_topic             │   │
│  │  Stage 2: Full Response    Refusal Message            │   │
│  └─────────────────┬─────────────────────────────────────┘  │
│                    │                                        │
│  ┌─────────────────▼─────────────────────────────────────┐  │
│  │            Conversation Manager                        │  │
│  │                                                        │  │
│  │  context.py          │  config.py                      │  │
│  │  - Session store     │  - System prompt builder        │  │
│  │  - Sliding window    │  - ChatML formatter             │  │
│  │  - STATE extraction  │  - Inference constants          │  │
│  │  - Lifecycle mgmt    │                                 │  │
│  └─────────────────┬─────────────────────────────────────┘  │
│                    │                                        │
│  ┌─────────────────▼─────────────────────────────────────┐  │
│  │              LLM Inference Layer                       │  │
│  │         llama-cpp-python (CPU, 4 threads)              │  │
│  │      Qwen2.5-3B-Instruct-Q4_K_M.gguf (~2GB)           │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

**Frontend (`frontend/`)** — React + Vite chat interface. Connects via WebSocket for real-time streaming responses. Handles session management, message history display, and UI state based on backend `status` field.

**Backend API (`backend/app/api/routes.py`)** — FastAPI service exposing REST (`/chat`) and WebSocket (`/ws/chat`) endpoints. Async request handling via Python's event loop. All inference runs in a `ThreadPoolExecutor` to avoid blocking concurrent requests.

**LLM Engine (`backend/app/llm/engine.py`)** — Two-stage inference pipeline. Stage 1 classifies intent using the same model at `max_tokens=5, temperature=0` — extremely fast (~0.5s). Stage 2 runs full response generation only for on-topic shopping messages.

**Conversation Manager (`backend/app/memory/context.py`)** — In-memory session store with sliding window context trimming. Extracts structured facts (budget, item, preferences) from hidden `<STATE>` tags in model output and injects them back into the system prompt on every turn — ensuring critical facts never fall out of context.

**Core Config (`backend/app/core/config.py`)** — System prompt definitions, ChatML builder, and all tuneable inference constants.

---

## Model Selection

| Property | Value |
|---|---|
| Model | Qwen2.5-3B-Instruct |
| Quantization | Q4_K_M |
| Format | GGUF |
| File size | ~2.0 GB |
| Context length (trained) | 32,768 tokens |
| Context length (used) | 2,048 tokens |
| Inference backend | llama-cpp-python |
| Hardware | CPU only (Intel i5 8th Gen, 4 cores) |

**Why Qwen2.5-3B-Instruct-Q4_K_M:**
- Smallest model with reliable instruction following for a business chatbot
- Q4_K_M quantization preserves quality better than Q4_0 via mixed-precision k-quants
- 2GB RAM footprint fits comfortably alongside the OS on an 8GB laptop
- Qwen2.5 instruction-tuned variant follows system prompt rules significantly better than base models of the same size

---

## Context Memory Management

The system uses a two-layer memory strategy to filter signal from noise:

**Layer 1 — Sliding Window:** Only the last 6 messages (3 turns) are included in each inference call. Older messages are dropped. This prevents context overflow and keeps inference fast.

**Layer 2 — STATE Injection:** The model is instructed to append a hidden `<STATE>Budget: X, Item: Y, Preferences: Z, Resolved: yes/no</STATE>` tag to every response. This tag is intercepted in Python, parsed, and stored in the session dict. Before each inference call, extracted facts are injected back into the system prompt — so budget, item, and preferences are never lost even when old messages are trimmed by the sliding window.

```
User message → Classifier → [off_topic: refusal] or [shopping: ↓]
                                                          ↓
                                        Sliding window (last 6 msgs)
                                                +
                                        STATE-injected system prompt
                                                +
                                        New user message
                                                ↓
                                        LLM inference
                                                ↓
                                        Strip <STATE> tag
                                        Update session state
                                                ↓
                                        Clean response → user
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

### Step 5: Warmup (recommended)

```bash
curl -X POST http://localhost:8000/debug/warmup
```

First inference is always slower due to KV cache initialisation. Warmup before benchmarking or demoing.

---

## API Reference

### POST `/chat`
Standard REST chat endpoint.

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
  "latency_ms": 4823.5,
  "status": "active",
  "turns_used": 1,
  "turns_max": 10
}
```

### WebSocket `/ws/chat`
Streaming endpoint for real-time token output.

**Send:**
```json
{"session_id": "abc-123", "message": "I need earbuds under 3000 PKR"}
```

**Receive (per token):**
```json
{"token": "For", "done": false}
```

**Receive (final):**
```json
{
  "token": "",
  "done": true,
  "full_response": "For earbuds under 3000 PKR...",
  "latency_ms": 3241.2,
  "status": "active",
  "turns_used": 1,
  "turns_max": 10
}
```

### POST `/reset`
Clears session history and state.
```json
{"session_id": "abc-123"}
```

### GET `/session/welcome/{session_id}`
Returns welcome message for new sessions.

### POST `/benchmark?runs=5`
Runs N inference calls and returns latency statistics.

---

## Performance Benchmarks

> Tested on Intel Core i5 8th Gen (4 cores, 8 threads), 8GB RAM, CPU-only inference.

### Inference Latency

| Metric | Value |
|---|---|
| Average latency | ___ ms |
| Minimum latency | ___ ms |
| Maximum latency | ___ ms |
| P50 latency | ___ ms |
| P95 latency | ___ ms |
| Tokens per second | ___ tok/s |

*Run `POST /benchmark?runs=10` to generate these values and fill them in.*

### Stress Test Results (Locust)

| Metric | Value |
|---|---|
| Concurrent users tested | ___ |
| Requests per second | ___ |
| Average response time | ___ ms |
| Failure rate | ___ % |

*Run `locust -f backend/tests/locustfile.py --host=http://localhost:8000` to generate.*

### Context Memory Accuracy

| Test | Result |
|---|---|
| Budget retained across 10 turns | ✅ Pass |
| Item retained after topic change | ✅ Pass |
| Off-topic refusal (medical) | ✅ Pass |
| Off-topic refusal (selling) | ✅ Pass |
| Shopping follow-up classification | ✅ Pass |
| Session isolation (concurrent users) | ✅ Pass |

---

## Failure Handling

| Failure Type | Handling |
|---|---|
| Model file not found | Server starts, returns graceful error message |
| Inference error | Caught, logged, returns "Please try again" |
| Client disconnects mid-stream | `CancelledError` caught, partial response saved to history |
| Session turn limit reached | Farewell message sent, session locked, frontend input disabled |
| Invalid JSON over WebSocket | Error message returned, connection kept alive |
| Off-topic message | Intent classifier intercepts before LLM, refusal returned instantly |

---

## Project Structure

```
Service_based_conversational_ai_NLP/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py          # REST + WebSocket endpoints
│   │   ├── core/
│   │   │   └── config.py          # System prompts, constants
│   │   ├── llm/
│   │   │   └── engine.py          # Two-stage LLM pipeline
│   │   ├── memory/
│   │   │   └── context.py         # Session management, sliding window
│   │   └── main.py                # FastAPI app entry point
│   ├── tests/
│   │   └── locustfile.py          # Stress testing
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                      # React + Vite chat interface
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── models/
│   └── .gitkeep                   # Model files go here (not in git)
├── docker-compose.yml
└── README.md
```

---

## Known Limitations

- **Single model instance:** Only one inference runs at a time due to llama-cpp-python not being thread-safe. Concurrent users queue — the second user waits while the first user's response generates.
- **In-memory sessions:** All session data is lost on server restart. Sessions are not persisted to disk or database.
- **CPU-only inference:** Latency is 3–8 seconds per response on a 4-core i5. A GPU would reduce this to under 1 second.
- **Context window cap:** We cap `n_ctx` at 2048 tokens (model supports 32768) to stay within RAM budget. Very long responses may be truncated.
- **3B parameter limit:** Small model size means occasional instruction-following failures, especially for ambiguous or multi-part requests.
- **No authentication:** Session IDs are client-generated UUIDs with no authentication layer. Not suitable for public deployment without adding auth middleware.
- **Tools and RAG disallowed:** Per assignment constraints, no retrieval or tool use. All product knowledge comes from the model's training data — specific product availability and pricing on Daraz.pk cannot be verified.