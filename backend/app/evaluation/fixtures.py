"""Synthetic pull request fixtures and seed memories for deterministic evaluation."""

from app.schemas.diff import ChangedFile, PRDiffContext, PullRequestMetadata

# -------------------------------------------------------------------------
# Seed Memories for Acme Commerce Platform
# -------------------------------------------------------------------------

SEED_MEMORIES = [
    {
        "text": "Team Architecture Rule: All service layer database operations must occur through repository abstractions. Direct ORM session calls in service classes are strictly forbidden.",
        "source_type": "team_rule",
        "tags": ["architecture", "repository_pattern", "service_layer"],
        "relevance": 0.95,
    },
    {
        "text": "Postmortem INC-402: Stripe charge operations must strictly attach deterministic idempotency keys before retrying on 5xx network timeout to avoid double-charging customers.",
        "source_type": "review_decision",
        "tags": ["security", "billing", "idempotency"],
        "relevance": 0.92,
    },
]

# -------------------------------------------------------------------------
# PR Fixture 1: Service Layer Payment Refactor (Violates Architecture Rule)
# -------------------------------------------------------------------------

PR_1_PAYMENT_METADATA = PullRequestMetadata(
    owner="acme-corp",
    repo="commerce-platform",
    number=142,
    title="feat(checkout): add direct database call in checkout service",
    body="Refactors checkout flow to record payment status directly in database.",
    head_sha="sha_pr1_head",
    base_sha="sha_pr1_base",
    author_login="junior-dev",
    html_url="https://github.com/acme-corp/commerce-platform/pull/142",
)

PR_1_DIFF = """diff --git a/services/payment_service.py b/services/payment_service.py
index 4a12..9f32 100644
--- a/services/payment_service.py
+++ b/services/payment_service.py
@@ -15,4 +15,7 @@ class PaymentService:
     async def process_charge(self, amount: int, order_id: str):
-        pass
+        # Direct database write bypassing repository
+        record = PaymentRecord(order_id=order_id, amount=amount, status="pending")
+        db.session.add(record)
+        await db.session.commit()
"""

PR_1_DIFF_CONTEXT = PRDiffContext(
    repo="acme-corp/commerce-platform",
    pr_number=142,
    title="feat(checkout): add direct database call in checkout service",
    base_sha="sha_pr1_base",
    head_sha="sha_pr1_head",
    files=[
        ChangedFile(
            path="services/payment_service.py",
            status="modified",
            additions=4,
            deletions=1,
            valid_lines=[17, 18, 19, 20],
            patch='@@ -15,4 +15,7 @@\n-        pass\n+        record = PaymentRecord(order_id=order_id, amount=amount, status="pending")\n+        db.session.add(record)\n+        await db.session.commit()\n',
        )
    ],
    total_files=1,
    total_additions=4,
    total_deletions=1,
    formatted_diff=PR_1_DIFF,
)

# -------------------------------------------------------------------------
# PR Fixture 2: Migration Script With Raw SQL (Subject to Rejection Loop)
# -------------------------------------------------------------------------

PR_2_MIGRATION_METADATA = PullRequestMetadata(
    owner="acme-corp",
    repo="commerce-platform",
    number=143,
    title="migration(invoices): add invoice indexing migration with raw sql",
    body="Adds raw DDL index statement for high-throughput invoice table.",
    head_sha="sha_pr2_head",
    base_sha="sha_pr2_base",
    author_login="backend-engineer",
    html_url="https://github.com/acme-corp/commerce-platform/pull/143",
)

PR_2_DIFF_CONTEXT = PRDiffContext(
    repo="acme-corp/commerce-platform",
    pr_number=143,
    title="migration(invoices): add invoice indexing migration with raw sql",
    base_sha="sha_pr2_base",
    head_sha="sha_pr2_head",
    files=[
        ChangedFile(
            path="migrations/0042_invoices.py",
            status="added",
            additions=8,
            deletions=0,
            valid_lines=[1, 2, 3, 4, 5],
            patch="@@ -0,0 +1,5 @@\n+CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invoices_user ON invoices(user_id);\n",
        )
    ],
    total_files=1,
    total_additions=8,
    total_deletions=0,
    formatted_diff="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_invoices_user ON invoices(user_id);",
)

# -------------------------------------------------------------------------
# PR Fixture 3: Subsequent Migration Script (After Feedback Evolution)
# -------------------------------------------------------------------------

PR_3_DIFF_CONTEXT = PRDiffContext(
    repo="acme-corp/commerce-platform",
    pr_number=144,
    title="migration(settlements): add settlement transactions table with raw sql",
    head_sha="sha_pr3_head",
    base_sha="sha_pr3_base",
    files=[
        ChangedFile(
            path="migrations/0043_settlements.py",
            status="added",
            additions=10,
            deletions=0,
            valid_lines=[1, 2, 3, 4, 5],
            patch="@@ -0,0 +1,5 @@\n+CREATE TABLE settlements (id UUID PRIMARY KEY, total BIGINT);\n",
        )
    ],
    total_files=1,
    total_additions=10,
    total_deletions=0,
    formatted_diff="CREATE TABLE settlements (id UUID PRIMARY KEY, total BIGINT);",
)
