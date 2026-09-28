# CodeDNA — Memory-Driven AI Code Review Agent

> **CodeDNA is a code reviewer that remembers what your team actually believes.**

CodeDNA bridges GitHub Pull Request reviews with persistent organizational memory powered by **Hindsight** and **Groq** structured outputs. Instead of generic, context-free AI advice, CodeDNA continuously accumulates your team's coding conventions, architectural patterns, past review approvals/rejections, and incident postmortems.

```text
Pull Request -> Contextual Review -> Developer Feedback -> Persistent Memory -> Better Future Review
```

---

## 🏗️ System Architecture

```text
                 GitHub
                   |
             Webhook / PR
                   |
                   v
         ┌──────────────────┐
         │ FastAPI Backend  │
         └─────────┬────────┘
                   |
          ┌────────┴────────┐
          v                 v
     GitHub Client      Hindsight
   (PyGithub / HTTP)   Recall / Retain
          |                 |
          └────────┬────────┘
                   v
               Groq LLM
       (openai/gpt-oss-120b)
                   |
                   v
           Structured Review
                   |
          ┌────────┴────────┐
          v                 v
       GitHub            Postgres / SQLite
       Review             Audit / Runs
                            |
                            v
                     Next.js 14 UI
```

---

## 🌟 Key Capabilities

1. **Context-Aware Pull Request Review**: Recalls team rules and incident postmortems in real-time from Hindsight using partitioned bank IDs (`codedna:{owner}:{repo}`).
2. **Bi-Directional Learning Loop**: Captures human reviewer feedback (accepted, rejected, modified) and dynamically retains negative constraint memories to eliminate recurring false-positive advice.
3. **Observable Memory Audit UI**: Dark-mode SaaS dashboard with real-time transparency showing recalled memories, relevance scores, and direct memory influence on findings.
4. **Multi-Layer Defense Pipeline**:
   - **Layer A**: Regex secret redaction (GitHub tokens, AWS keys, JWTs, private keys)
   - **Layer B**: Prompt injection scanning and mitigation
   - **Layer C**: Immutable GitHub review publishing template
   - **Layer D**: Constant-time HMAC-SHA256 webhook signature verification
   - **Layer E**: Strict CORS origin enforcement and error sanitization
   - **Layer F**: Bleach HTML tag stripping and markdown link sanitization
5. **Resilient Degradation**: Automatically degrades to stateless review mode on memory service latency without crashing or blocking reviews.

---

## 📁 Repository Structure

```text
CodeDNA/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes: health, webhook, feedback, dashboard
│   │   ├── core/           # Configuration, logging, errors, security
│   │   ├── db/             # SQLAlchemy models, repositories, session
│   │   ├── evaluation/     # Synthetic fixtures and evaluation runner
│   │   ├── integrations/   # PyGitHub, Groq, Hindsight client adapters
│   │   ├── schemas/        # Pydantic v2 domain schemas (extra="forbid")
│   │   ├── security/       # Defense pipeline: redactor, sanitizer, injection scanner
│   │   ├── services/       # Orchestration, diff, memory, review, publishing, learning
│   │   └── workers/        # Asynchronous background tasks
│   ├── alembic/            # Database migrations
│   └── tests/              # 95 unit, security, integration, and harness tests
├── frontend/
│   ├── app/                # Next.js 14 App Router pages (dark-mode SaaS UI)
│   ├── components/         # Dashboard widgets, stats cards, PR table, inspection modal
│   └── lib/                # API client, TypeScript definitions, constants
├── docs/
│   ├── architecture.md     # Detailed architectural blueprint
│   ├── connection-guide.md # Step-by-step external service setup (Section 20)
│   ├── demo-script.md      # Minute-by-minute 3-minute judging script (Section 24)
│   ├── memory-design.md    # Hindsight memory partitioning and retention schema
│   ├── memory-evaluation.md# Benchmark report across Scenarios A, B, and C
│   └── threat-model.md     # STRIDE threat model & 6-layer defense pipeline
├── scripts/
│   ├── verify_connections.py     # Mandatory 9-step connection verification CLI
│   └── run_memory_evaluation.py  # Memory benchmark CLI runner
├── Makefile                # Unified development and testing targets
└── docker-compose.yml      # Local containerized PostgreSQL and backend
```

---

## 🚀 Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+ (20+ recommended)
- Git

### 1. Installation
```bash
# Clone repository
git clone https://github.com/your-org/CodeDNA.git
cd CodeDNA

# Install backend and frontend dependencies
make install
```

### 2. Environment Configuration
```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

### 3. Run the Mandatory 9-Step Verification Suite
```bash
# Verifies health, database, Hindsight, Groq, GitHub, HMAC, sandbox diff, CORS, and review loop:
make verify
```

### 4. Run Memory Evaluation Benchmark
```bash
# Evaluates Scenario A (Stateless), Scenario B (Memory), Scenario C (Learning Loop):
make evaluate
```

### 5. Start Development Servers
```bash
# Terminal 1: Backend
make run-backend

# Terminal 2: Frontend
make run-frontend
```

Open `http://localhost:3000` to view the CodeDNA Dashboard.

---

## 🧪 Automated Testing Matrix

| Test Suite | Command | Coverage |
| :--- | :--- | :--- |
| **Backend Unit & Integration** | `pytest backend/tests -v` | 95 tests passing (smoke, config, persistence, diff, webhook, memory, groq, security, publishing, feedback, dashboard, harness, connections) |
| **Backend Static Typecheck** | `mypy backend/app` | 100% clean, strict typing |
| **Backend Lint & Format** | `ruff check backend && ruff format --check backend` | Clean, 0 warnings |
| **Frontend Static Typecheck** | `cd frontend && npm run typecheck` | Clean, 0 errors |
| **Frontend ESLint** | `cd frontend && npm run lint` | Clean, 0 warnings/errors |
| **Frontend Production Build**| `cd frontend && npm run build` | 100% optimized static build |
| **9-Step Connection Audit** | `python scripts/verify_connections.py` | All 9 verification steps passed |

---

## 📊 Live Judge Demo in 3 Minutes

Follow the step-by-step guide in [`docs/demo-script.md`](docs/demo-script.md):

1. **0:00–0:20 (The Problem)**: Show how traditional AI reviewers miss company-specific design patterns.
2. **0:20–0:50 (Scenario A)**: Run PR #142 in stateless mode — fails to catch direct database write in service layer.
3. **0:50–1:20 (Memory Audit)**: Open Memory Audit panel to reveal recalled team rules from Hindsight.
4. **1:20–2:00 (Scenario B)**: Run PR #142 with memory — catches architectural violation as CRITICAL with exact suggestion.
5. **2:00–2:30 (Scenario C)**: Developer rejects raw SQL suggestion in PR #143; negative constraint is retained in Hindsight.
6. **2:30–3:00 (Future PR)**: Subsequent PR #144 recalls constraint and suppresses the false positive (0 findings).

---

## 📜 Documentation Links

- [External Services Connection Guide](docs/connection-guide.md)
- [3-Minute Live Demo Script](docs/demo-script.md)
- [Memory Evaluation Benchmark Report](docs/memory-evaluation.md)
- [System Architecture Blueprint](docs/architecture.md)
- [Memory Design Specification](docs/memory-design.md)
- [Security Threat Model](docs/threat-model.md)
- [Module Implementation Status](MODULE_STATUS.md)

---

## ⚖️ License

MIT License. See [LICENSE](LICENSE) for details.
