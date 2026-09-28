# CodeDNA 3-Minute Live Judging Demo Script

This script provides an exact, minute-by-minute execution guide for demonstrating CodeDNA to hackathon judges. It uses the deterministic evaluation fixtures and the Next.js dark-mode dashboard.

---

## 0:00–0:20 — The Problem Statement
- **Screen**: Next.js Dashboard (`http://localhost:3000`) overview.
- **Narrative**:
  > *"Traditional AI code review tools evaluate diffs in total amnesia. They know Python syntax, but they don't know your company's architectural decisions, postmortems, or team conventions. When an engineer submits code that violates an internal design rule, generic AI misses it completely. CodeDNA bridges this gap by combining Groq's high-speed structured inference with Hindsight's cross-PR persistent memory."*

---

## 0:20–0:50 — Scenario A: Baseline Stateless Review (Amnesia Mode)
- **Action**:
  - In the dashboard, click **"Run Evaluation Benchmark"** or select **"Scenario A (Stateless)"**.
  - Alternatively run via CLI: `python scripts/run_memory_evaluation.py`
- **Show PR #142**:
  - `feat(checkout): add direct database call in checkout service` (`services/payment_service.py`).
  - The developer wrote a direct `db.session.add()` call inside a service class, bypassing the repository abstraction.
- **Demonstrate**:
  - Stateless review produces generic variable-naming feedback (e.g., minor comment on `order_id`).
  - **Result**: Fails to detect the critical architectural violation because it has no memory of team rules.

---

## 0:50–1:20 — Inspect Recalled Memory in Memory Audit Panel
- **Action**:
  - Click on the **"Memory Audit"** tab or view the Memory Audit panel on the right.
- **Show Recalled Knowledge**:
  - **Memory Bank**: `codedna:acme-corp:commerce-platform` (Tenant isolated).
  - **Recalled Rule 1**: *"Team Architecture Rule: All service layer database operations must occur through repository abstractions. Direct ORM session calls in service classes are strictly forbidden."* (Relevance: 95%).
  - **Recalled Incident INC-402**: *"Stripe charge operations must strictly attach deterministic idempotency keys before retrying on 5xx network timeout."* (Relevance: 92%).
- **Key Point for Judges**:
  > *"Notice how CodeDNA dynamically synthesized an embedding recall query using changed file paths (`services/payment_service.py`) and architectural keywords, retrieving the exact conventions applicable to this PR."*

---

## 1:20–2:00 — Scenario B: Context-Aware Review (With Hindsight Memory)
- **Action**:
  - Switch to **"Scenario B (Memory-Aware)"** in the review run inspector.
- **Demonstrate**:
  - CodeDNA flags PR #142 with **CRITICAL** severity.
  - **Category**: `architecture`
  - **Exact Title**: *"Direct ORM session call violates repository architecture"*
  - **Rationale**: Directly cites the team's repository pattern convention and INC-402 idempotency invariant.
  - **Actionable Suggestion**: Provides replacement code utilizing `PaymentRepository.create_record()`.
- **Narrative**:
  > *"Because Hindsight provided organizational context, CodeDNA caught a production architecture violation before code ever merged."*

---

## 2:00–2:30 — Scenario C: Human Feedback Loop (Learning in Action)
- **Action**:
  - Inspect PR #143: Migration script adding invoice index with raw SQL (`migrations/0042_invoices.py`).
  - AI flagged raw SQL as a medium severity finding.
  - Click **"Reject / False Positive"** on the finding in the UI.
  - Select feedback reason: *"Team convention: Raw SQL DDL is explicitly allowed in migration scripts for lock safety and concurrency."*
  - Click **"Submit Feedback & Retain to Memory"**.
- **Show**:
  - Relational feedback status updates to `rejected`.
  - Backend asynchronously triggers `learning_service.process_feedback_outcome()` and stores a negative constraint rule in Hindsight with tag `feedback:rejected`.
- **Narrative**:
  > *"Human feedback is captured not just as a comment, but as a persistent negative constraint memory: 'Do NOT recommend avoiding raw SQL in migrations'."*

---

## 2:30–3:00 — Future PR: Verified Behavioral Evolution
- **Action**:
  - Inspect subsequent PR #144: `migration(settlements): add settlement transactions table with raw sql` (`migrations/0043_settlements.py`).
- **Demonstrate**:
  - CodeDNA recalls the negative constraint from Hindsight.
  - It suppresses the false positive: **0 findings generated**, clean review.
  - The review summary explicitly notes: *"Conventions applied: Raw SQL DDL is explicitly allowed in migration scripts per reviewer feedback."*
- **Closing Statement**:
  > *"CodeDNA creates a self-improving code review flywheel: every review teaches the system, and every subsequent PR benefits from the entire team's accumulated engineering wisdom."*

---

## Live Backup & One-Command Offline Run
If external Wi-Fi or API keys are unavailable during the live presentation, execute:
```bash
python scripts/run_memory_evaluation.py
```
This generates the full comparative report directly in `docs/memory-evaluation.md` and populates the dashboard with deterministic evaluation results.
