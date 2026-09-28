# CodeDNA — Memory-Driven AI Code Review Agent

> **CodeDNA is a code reviewer that remembers what your team actually believes.**

CodeDNA bridges GitHub Pull Request reviews with persistent team memory powered by **Hindsight** and **Groq** structured outputs. Instead of generic, context-free AI advice, CodeDNA continuously accumulates your team's coding conventions, past review approvals/rejections, architectural patterns, and incident postmortems.

---

## 🌟 Key Capabilities

- **Context-Aware Pull Request Review**: Reviews diffs against historical team memory recalled in real-time from Hindsight.
- **Bi-Directional Learning Loop**: Human review feedback (e.g. "team doesn't do this", "accepted pattern") is retained back into Hindsight to improve future reviews.
- **Observable Memory Audit**: Real-time SaaS dashboard revealing what Hindsight recalled, why it was relevant, and how it shaped the Groq review output.
- **Multi-Layer Security**: Strict GitHub HMAC webhook validation, prompt injection shields, secret redaction, and bounded input sanitization.
- **Graceful Degradation**: Continues statelessly if memory or external services encounter temporary latency or outages.

---

## 🏗️ Repository Architecture

```text
CodeDNA/
├── frontend/             # Next.js 14 App Router, React 18, Tailwind CSS, shadcn/ui
├── backend/              # FastAPI, SQLAlchemy 2.x, Pydantic v2, Groq SDK, Hindsight Client
├── docs/                 # Architecture, threat model, demo script, and evaluation specs
├── Makefile              # Local development and test commands
└── docker-compose.yml    # Containerized local setup
```

---

## 🚀 Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+ (20+ recommended)
- npm 9+
- Git

### 1. Environment Setup

Copy example environment files:
```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

### 2. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Visit the dashboard at `http://localhost:3000`.

---

## 🧪 Testing

```bash
# Run backend tests
backend/.venv/Scripts/pytest -q

# Run frontend checks
cd frontend
npm run lint
npm run typecheck
npm run build
```

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.
