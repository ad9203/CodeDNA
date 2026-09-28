# CodeDNA 3-Minute Live Judging Demo Script

## 0:00–0:20 — The Problem
- **Narrative**: "Standard AI review tools evaluate code in total isolation. They don't know that last month your team agreed to never use raw SQL queries, or that a checkout outage was caused by unpooled DB connections. CodeDNA solves this with persistent memory."

## 0:20–0:50 — Scenario A: Baseline Review (Stateless)
- **Action**: Run PR #101 with empty memory.
- **Show**: Review output is technically accurate but generic. It fails to identify violation of custom service-layer validation rules.

## 0:50–1:20 — Inspect Recalled Memory
- **Action**: Switch to the CodeDNA Dashboard -> Memory Audit Panel.
- **Show**: Display seeded memories:
  - Team Rule #1: "Service layer validation required before repository calls"
  - Incident #12: "DB connection pool starvation under high checkout load"
  - Past rejection: "Avoid Optional in legacy payment interfaces"

## 1:20–2:00 — Scenario B: Context-Aware Review (With Hindsight)
- **Action**: Process PR #102 with Hindsight memory active.
- **Show**: Review explicitly cites Team Rule #1 and references Incident #12, warning the developer before merging.

## 2:00–2:30 — Scenario C: Developer Feedback Loop
- **Action**: Reviewer clicks "Team doesn't do this" on a suggestion or comments on GitHub.
- **Show**: Hindsight retain call occurs in real time with tag `feedback:rejected`.

## 2:30–3:00 — Future PR: Verified Behavioral Evolution
- **Action**: Submit new PR #103 with the same pattern.
- **Show**: Reviewer no longer repeats rejected advice, demonstrating continuous learning.
