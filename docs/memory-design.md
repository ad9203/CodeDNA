# CodeDNA Memory Layer Architecture & Hindsight Strategy

## 1. Multi-Tenant Memory Banks

Every repository is partitioned to ensure cross-tenant data isolation:

```text
Bank ID Strategy:
Development / Single-Tenant: codedna:{owner}:{repo}
Multi-Tenant / Enterprise:    codedna:{tenant_id}:{owner}:{repo}
```

## 2. Memory Types & Ontology

Memories retained in Hindsight are grouped into 5 distinct categories:

1. **`team_rule`**: Explicit coding standards, linter overrides, error-handling conventions.
   - *Example*: "Service-layer methods must validate domain boundaries before invoking repositories."
2. **`review_decision`**: Explicitly approved or rejected PR suggestions.
   - *Example*: "Rejected using Optional in user-service compatibility layer."
3. **`architecture_pattern`**: High-level system structure, database conventions, caching guidelines.
   - *Example*: "Orders service requires optimistic locking for balance updates."
4. **`incident_context`**: Postmortems and bug histories tied to specific paths or symbols.
   - *Example*: "INC-12: checkout timeout caused by unpooled DB connections in payment service."
5. **`learning_outcome`**: Synthesized rules derived from developer feedback.
   - *Example*: "Do not suggest adding Redis caching to inventory endpoints because reads require strict consistency."

## 3. Query Construction for Recall

Before sending the diff to Groq, a structured query is compiled:

```text
Repository: {repo}
Changed files: {paths}
Architecture hints: {symbols}
PR Title & Summary: {pr_title}

Question:
Which team coding standards, prior review decisions, architectural preferences,
and relevant bugs/incidents apply to this change? Prefer concrete evidence from
this repository's history.
```

## 4. Graceful Degradation

If Hindsight is unreachable or times out:
1. Review run is marked `status=degraded`.
2. Groq is invoked with `memories=[]`.
3. Reviewer comments state: "Memory unavailable — review continued statelessly".
4. The system never halts PR review due to temporary memory latency.
