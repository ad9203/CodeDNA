"""Unit tests for Groq review engine, structured outputs, prompt defenses, and finding validation."""

import pytest
from pydantic import ValidationError

from app.core.errors import ExternalServiceError
from app.integrations.groq_client import MockGroqClient, is_retryable_groq_error
from app.schemas.diff import ChangedFile, PRDiffContext
from app.schemas.memory import RecalledMemory
from app.schemas.review import ReviewFinding, ReviewResult
from app.services.review_service import SYSTEM_PROMPT, ReviewService


@pytest.fixture
def diff_context():
    return PRDiffContext(
        repo="acme/commerce",
        pr_number=42,
        title="Implement payment processing",
        base_sha="base_sha",
        head_sha="head_sha",
        files=[
            ChangedFile(
                path="services/payment.py",
                status="modified",
                additions=10,
                deletions=2,
                patch="@@ -10,3 +10,4 @@\n context\n+added line 11\n",
                language="python",
                valid_lines=[10, 11],
            )
        ],
        total_files=1,
        total_additions=10,
        total_deletions=2,
        formatted_diff="### File: services/payment.py\n```python\n+added line 11\n```",
    )


@pytest.fixture
def memories():
    return [
        RecalledMemory(
            memory_id="mem-1",
            text="Team standard: Validate all amounts are positive Decimals before charging.",
            source_type="team_rule",
            relevance=0.92,
        )
    ]


def test_prompt_builder_structure_and_memory_isolation(diff_context, memories):
    user_prompt = ReviewService.build_user_prompt(diff_context, memories)

    # 1. User prompt contains Section 1 (Memory), Section 2 (PR data), Section 3 (Instructions)
    assert "=== SECTION 1: TEAM MEMORY (UNTRUSTED CONTEXTUAL EVIDENCE) ===" in user_prompt
    assert "=== SECTION 2: CURRENT PULL REQUEST (UNTRUSTED CODE/DATA) ===" in user_prompt
    assert "=== SECTION 3: REVIEW TASK AND STRICT JSON SCHEMA ===" in user_prompt

    # 2. Team memory is inside Section 1, NOT inside SYSTEM_PROMPT
    assert "Validate all amounts are positive Decimals" in user_prompt
    assert "Validate all amounts are positive Decimals" not in SYSTEM_PROMPT

    # 3. System prompt explicitly defines untrusted boundaries and injection resistance
    assert "UNTRUSTED DATA BOUNDARY" in SYSTEM_PROMPT
    assert "PROMPT INJECTION RESISTANCE" in SYSTEM_PROMPT
    assert "NO INVENTED POLICIES OR APIS" in SYSTEM_PROMPT


def test_schema_valid_result_parsing():
    valid_data = {
        "summary": "Valid PR review summary.",
        "overall_risk": "medium",
        "findings": [
            {
                "severity": "high",
                "category": "team_convention",
                "confidence": 0.85,
                "path": "services/payment.py",
                "line": 11,
                "side": "RIGHT",
                "title": "Missing boundary validation",
                "message": "Amount must be strictly positive.",
                "rationale": "Team rule #1",
                "suggestion": "assert amount > 0",
            }
        ],
        "team_conventions_applied": ["Team rule #1"],
        "memory_influence_summary": ["Shaped validation finding"],
        "uncertainty_notes": [],
    }
    result = ReviewResult.model_validate(valid_data)
    assert result.overall_risk == "medium"
    assert len(result.findings) == 1
    assert result.findings[0].confidence == 0.85


def test_schema_rejects_unknown_fields():
    data_with_unknown = {
        "summary": "Summary",
        "overall_risk": "low",
        "findings": [],
        "team_conventions_applied": [],
        "memory_influence_summary": [],
        "uncertainty_notes": [],
        "hallucinated_admin_field": "exploit",  # Forbidden by extra="forbid"
    }
    with pytest.raises(ValidationError):
        ReviewResult.model_validate(data_with_unknown)


def test_schema_rejects_out_of_range_confidence():
    invalid_confidence_data = {
        "severity": "low",
        "category": "correctness",
        "confidence": 1.5,  # Out of range 0..1
        "path": "file.py",
        "title": "Title",
        "message": "Msg",
        "rationale": "Rat",
    }
    with pytest.raises(ValidationError):
        ReviewFinding.model_validate(invalid_confidence_data)


@pytest.mark.asyncio
async def test_review_service_generation_and_finding_line_validation(diff_context, memories):
    mock_groq = MockGroqClient()
    mock_groq.set_response(
        {
            "summary": "Reviewed payment refactor.",
            "overall_risk": "medium",
            "findings": [
                {
                    "severity": "high",
                    "category": "correctness",
                    "confidence": 0.9,
                    "path": "services/payment.py",
                    "line": 11,  # Line 11 is valid in diff_context.files[0].valid_lines
                    "side": "RIGHT",
                    "title": "Unchecked amount",
                    "message": "Ensure amount is not None.",
                    "rationale": "Required check",
                    "suggestion": None,
                },
                {
                    "severity": "medium",
                    "category": "other",
                    "confidence": 0.7,
                    "path": "services/payment.py",
                    "line": 9999,  # Line 9999 is NOT in changed hunk -> must be downgraded to None
                    "side": "RIGHT",
                    "title": "Out of range line finding",
                    "message": "Line does not exist in patch",
                    "rationale": "Line check",
                    "suggestion": None,
                },
                {
                    "severity": "low",
                    "category": "maintainability",
                    "confidence": 0.6,
                    "path": "services/hallucinated_file.py",  # File not in PR -> downgraded to line=None
                    "line": 5,
                    "side": "RIGHT",
                    "title": "Hallucinated file",
                    "message": "File not in PR",
                    "rationale": "Path check",
                    "suggestion": None,
                },
            ],
            "team_conventions_applied": [],
            "memory_influence_summary": [],
            "uncertainty_notes": [],
        }
    )

    service = ReviewService(client=mock_groq)
    result = await service.generate_review(diff_context, memories)

    assert result.summary == "Reviewed payment refactor."
    assert len(result.findings) == 3

    # Finding 1: Line 11 was in diff, remains line=11
    assert result.findings[0].line == 11

    # Finding 2: Line 9999 was outside diff hunks, downgraded to line=None
    assert result.findings[1].line is None

    # Finding 3: File was hallucinated, line downgraded to None
    assert result.findings[2].line is None


@pytest.mark.asyncio
async def test_malformed_json_raises_safe_external_error(diff_context, memories):
    mock_groq = MockGroqClient()

    async def mock_generate(*args, **kwargs):
        return '{"summary": "incomplete...'

    mock_groq.generate_review = mock_generate  # type: ignore

    service = ReviewService(client=mock_groq)
    with pytest.raises(ExternalServiceError) as exc_info:
        await service.generate_review(diff_context, memories)
    assert exc_info.value.service == "groq"
    assert "did not return valid JSON" in exc_info.value.message


def test_retryable_groq_error_predicate():
    class MockStatusError(Exception):
        def __init__(self, status_code):
            self.status_code = status_code

    # 429 rate limit is retryable
    assert is_retryable_groq_error(MockStatusError(429)) is True
    # 503 service unavailable is retryable
    assert is_retryable_groq_error(MockStatusError(503)) is True
    # TimeoutError is retryable
    assert is_retryable_groq_error(TimeoutError("Timeout")) is True
    # 400 Bad Request is NOT retryable
    assert is_retryable_groq_error(MockStatusError(400)) is False
    # 401 Unauthorized is NOT retryable
    assert is_retryable_groq_error(MockStatusError(401)) is False
