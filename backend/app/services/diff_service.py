"""Diff extraction, normalization, path sanitization, and truncation service."""

import os
import re

from app.core.config import settings
from app.core.errors import SecurityValidationError
from app.core.logging import get_logger
from app.schemas.diff import ChangedFile, PRDiffContext, PullRequestMetadata

logger = get_logger("app.services.diff_service")

# File extensions recognized as binary
BINARY_EXTENSIONS: set[str] = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".jar",
    ".war",
    ".class",
    ".pyc",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".wasm",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp4",
    ".mp3",
    ".mov",
}

# Extension to language map
EXTENSION_LANGUAGE_MAP = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sql": "sql",
    ".sh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".md": "markdown",
    ".html": "html",
    ".css": "css",
}

HUNK_HEADER_REGEX = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


class DiffService:
    """Handles diff extraction, validation, line number tracking, and truncation."""

    @staticmethod
    def normalize_line_endings(content: str) -> str:
        """Converts CRLF and CR to standard LF."""
        return content.replace("\r\n", "\n").replace("\r", "\n")

    @staticmethod
    def sanitize_path(path: str) -> str:
        """Validates that a file path does not attempt path traversal or absolute file access."""
        normalized = DiffService.normalize_line_endings(path).strip()

        # Reject path traversal tricks
        if ".." in normalized or normalized.startswith("/") or normalized.startswith("\\"):
            raise SecurityValidationError(
                f"Path traversal detected in file path: {path}",
                details={"path": path},
            )

        if ":" in normalized:  # Windows drive letters e.g. C:\
            raise SecurityValidationError(
                f"Absolute drive letter detected in file path: {path}",
                details={"path": path},
            )

        return os.path.normpath(normalized).replace("\\", "/")

    @staticmethod
    def detect_language(path: str) -> str:
        """Infers programming language from file extension."""
        _, ext = os.path.splitext(path.lower())
        return EXTENSION_LANGUAGE_MAP.get(ext, "unknown")

    @staticmethod
    def is_binary_file(path: str) -> bool:
        """Checks if a file extension represents a binary format."""
        _, ext = os.path.splitext(path.lower())
        return ext in BINARY_EXTENSIONS

    @staticmethod
    def extract_valid_lines(patch: str | None) -> list[int]:
        """Parses unified diff patch hunks and extracts 1-based target line numbers

        that were added or modified (valid targets for GitHub inline comments).
        """
        if not patch:
            return []

        valid_lines: list[int] = []
        current_target_line = 0

        for line in patch.split("\n"):
            hunk_match = HUNK_HEADER_REGEX.match(line)
            if hunk_match:
                start_line = int(hunk_match.group(1))
                current_target_line = start_line
                continue

            if not line:
                continue

            char = line[0]
            if char == "+":
                # Line added or modified on target side
                valid_lines.append(current_target_line)
                current_target_line += 1
            elif char == " ":
                # Context line present on both sides
                valid_lines.append(current_target_line)
                current_target_line += 1
            elif char == "-":
                # Removed line (not on target side)
                pass

        return valid_lines

    @staticmethod
    def is_valid_inline_location(file: ChangedFile, line: int) -> bool:
        """Verifies whether a proposed line number exists in the changed diff target."""
        return line in file.valid_lines

    @classmethod
    def build_diff_context(
        cls,
        pr_metadata: PullRequestMetadata,
        files: list[ChangedFile],
        max_diff_chars: int | None = None,
    ) -> PRDiffContext:
        """Compiles, sanitizes, and bounds changed files into a structured diff context."""
        diff_limit = max_diff_chars or settings.max_diff_chars
        total_files = len(files)
        total_additions = sum(f.additions for f in files)
        total_deletions = sum(f.deletions for f in files)

        processed_files: list[ChangedFile] = []
        skipped_binary: list[str] = []
        unexamined_files: list[str] = []

        formatted_hunks: list[str] = []
        current_char_count = 0
        diff_truncated = False

        for f in files:
            # Step 1: Validate and sanitize path
            sanitized_path = cls.sanitize_path(f.path)

            # Step 2: Skip binary files
            if cls.is_binary_file(sanitized_path):
                skipped_binary.append(sanitized_path)
                continue

            lang = cls.detect_language(sanitized_path)
            normalized_patch = cls.normalize_line_endings(f.patch) if f.patch else None
            valid_lines = cls.extract_valid_lines(normalized_patch)

            changed_file = ChangedFile(
                path=sanitized_path,
                status=f.status,
                additions=f.additions,
                deletions=f.deletions,
                patch=normalized_patch,
                language=lang,
                is_binary=False,
                valid_lines=valid_lines,
            )

            # Step 3: Format file diff block
            file_header = f"### File: {sanitized_path} ({f.status}, +{f.additions}/-{f.deletions}, lang: {lang})\n"
            patch_content = normalized_patch or "[No patch content / empty diff]\n"
            file_block = f"{file_header}```{lang}\n{patch_content}\n```\n\n"

            # Step 4: Check diff character bound
            if current_char_count + len(file_block) > diff_limit:
                diff_truncated = True
                unexamined_files.append(sanitized_path)
            else:
                current_char_count += len(file_block)
                processed_files.append(changed_file)
                formatted_hunks.append(file_block)

        # Assemble final prompt diff string with explicit truncation notice if needed
        final_diff_str = "".join(formatted_hunks)
        if diff_truncated:
            truncation_notice = (
                f"\n> [!WARNING]\n"
                f"> **DIFF TRUNCATED**: Total changes exceeded {diff_limit} characters. "
                f"{len(unexamined_files)} files ({', '.join(unexamined_files[:5])}"
                f"{'...' if len(unexamined_files) > 5 else ''}) were omitted. "
                f"Review is partial for examined files only. Do NOT assume unexamined files are bug-free.\n\n"
            )
            final_diff_str = truncation_notice + final_diff_str

        return PRDiffContext(
            repo=f"{pr_metadata.owner}/{pr_metadata.repo}",
            pr_number=pr_metadata.number,
            title=pr_metadata.title,
            base_sha=pr_metadata.base_sha,
            head_sha=pr_metadata.head_sha,
            files=processed_files,
            total_files=total_files,
            total_additions=total_additions,
            total_deletions=total_deletions,
            diff_truncated=diff_truncated,
            skipped_binary_files=skipped_binary,
            unexamined_files=unexamined_files,
            formatted_diff=final_diff_str,
        )
