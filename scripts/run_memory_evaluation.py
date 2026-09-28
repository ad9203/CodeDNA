#!/usr/bin/env python3
"""CLI script to execute the CodeDNA Memory Evaluation Harness across Scenarios A, B, and C."""

import asyncio
import os
import sys
from pathlib import Path

# Add backend directory to Python sys.path
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
sys.path.insert(0, str(backend_dir))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.evaluation.runner import MemoryEvaluationRunner


async def main():
    print("=" * 70)
    print("[*] CodeDNA Memory Evaluation Harness")
    print("Testing Hindsight Memory Impact: Stateless vs Memory vs Feedback Evolution")
    print("=" * 70)

    runner = MemoryEvaluationRunner()
    report_path = root_dir / "docs" / "memory-evaluation.md"

    results = await runner.run_full_evaluation(output_path=report_path)

    print("\n--- RESULTS SUMMARY ---")
    for key in ["scenario_a", "scenario_b", "scenario_c"]:
        sc = results[key]
        print(f"\n[Scenario] {sc['scenario']}")
        print(f"   Memories Recalled: {sc['memories_recalled']}")
        print(f"   Findings Count:    {sc['findings_count']}")
        print(f"   Assessment:        {sc['assessment']}")

    print("\n" + "=" * 70)
    print(f"[+] Full Evaluation Report generated at: {report_path}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
