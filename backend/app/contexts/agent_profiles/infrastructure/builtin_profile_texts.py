from __future__ import annotations

DEEP_RESEARCH_SKILL_MD = """---
name: deep-research
description: Perform keyless deep web research with the agent-client's available search, browser, extraction, and citation tools.
---

# Deep Research

Use this skill when a task needs comprehensive web research, current information, source comparison, citation-backed synthesis, or a long-form research report.

This built-in skill is intentionally keyless. It does not require `OPENAI_API_KEY`, `TAVILY_API_KEY`, or a long-running research MCP server. Use the agent-client's available search, browser, fetch, local-file, and citation tools directly.

Optional GPT Researcher MCP:

- The `gpt-researcher` MCP server remains available as an optional profile MCP item.
- Enable it only when the environment has the service keys required by GPT Researcher, normally `OPENAI_API_KEY` and `TAVILY_API_KEY` unless a different LLM/retriever configuration is supplied.
- If enabled and healthy, its tools can be used for automated source gathering and report drafting. If it times out or reports missing keys, continue with native tools and disclose that fallback.

Workflow:

1. Clarify the research question, audience, region, timeframe, and desired output format when missing.
2. Start with broad search to map sources, then run focused searches for each unresolved question.
3. Prefer primary, official, or otherwise authoritative sources; use secondary sources to discover leads, not as final proof when primary sources exist.
4. Open and inspect sources before relying on them. Capture publication/update dates when recency matters.
5. Cross-check important claims across multiple sources and call out contradictions.
6. Preserve source URLs and distinguish evidence from synthesis.
7. When producing a report, include key findings, supporting evidence, source limitations, and remaining unknowns.

Reference repositories:

- GPT Researcher: https://github.com/assafelovic/gpt-researcher
- GPT Researcher MCP: https://github.com/assafelovic/gptr-mcp
"""

TDD_SKILL_MD = """---
name: tdd
description: Use red-green-refactor discipline for bug fixes and development changes.
---

# Test-Driven Development

Use this skill when implementing or debugging behavior that can be validated with automated tests.

Workflow:

1. Write the smallest failing test or identify the existing failing test that captures the behavior.
2. Run it and confirm it fails for the expected reason.
3. Make the smallest production change that turns the test green.
4. Run the focused test again.
5. Refactor only after the behavior is green, and rerun the relevant tests.
6. Expand validation to nearby tests when the changed code is shared or user-facing.

Rules:

- Prefer regression tests that would have failed before the fix.
- Keep tests deterministic, focused, and readable.
- When a test cannot be added, explain the blocker and use the closest repeatable validation command.
- Do not overfit the implementation to a single test fixture; verify the underlying rule.
"""
