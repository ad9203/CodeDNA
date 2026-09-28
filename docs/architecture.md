# CodeDNA Architecture Specification

## 1. System Overview

CodeDNA is an event-driven AI code review platform engineered to accumulate and recall team-specific engineering context. It solves the critical limitation of current AI code reviewers: lack of persistent, team-specific memory.

```
       GitHub PR Event
             │
             ▼
  ┌────────────────────────┐
  │  FastAPI Webhook Gate  │  <-- HMAC-SHA256 verification
  └──────────┬─────────────┘
             │
             ▼
  ┌────────────────────────┐
  │ GitHub Diff Extractor  │  <-- Bounded diffs, path validation
  └──────────┬─────────────┘
             │
             ▼
  ┌────────────────────────┐
  │ Hindsight Memory Layer │  <-- Contextual recall (coding rules, past reviews)
  └──────────┬─────────────┘
             │
             ▼
  ┌────────────────────────┐
  │ Groq Structured Review │  <-- Strict JSON schema, evidence-driven
  └──────────┬─────────────┘
             │
      ┌──────┴──────┐
      ▼             ▼
┌───────────┐ ┌───────────┐
│  GitHub   │ │ PostgreSQL│
│ PR Review │ │ DB Audit  │
└─────┬─────┘ └─────┬─────┘
      │             │
      ▼             ▼
  Developer     Next.js
  Feedback      Dashboard
      │
      ▼
┌───────────┐
│ Hindsight │
│  Retain   │
└───────────┘
```

## 2. Key Components

### 2.1 Backend Services
- **FastAPI Core**: Webhook ingestion, correlation tracking, rate limiting, and dashboard REST APIs.
- **Diff Service**: Retrieves, parses, sanitizes, and normalizes GitHub pull request diffs. Bounded at 150k characters.
- **Hindsight Client Adapter**: Async client interfacing with Hindsight Cloud for contextual `recall` and feedback `retain`.
- **Groq Review Engine**: Calls Groq LLM (e.g. `openai/gpt-oss-120b`) enforcing strict Pydantic JSON schemas.
- **Security & Redaction Pipeline**: Multi-layer defense preventing prompt injection, secret leaks, and raw HTML injection.
- **Learning Service**: Ingests human review feedback to extract conventions and postmortem insights.

### 2.2 Frontend Application
- **Next.js 14 App Router**: High-performance SSR and streaming UI.
- **Tailwind CSS + shadcn/ui**: Modern dark-mode B2B developer tool design.
- **Memory Audit Panel**: Full transparency into what memories were recalled and their direct impact on generated findings.
