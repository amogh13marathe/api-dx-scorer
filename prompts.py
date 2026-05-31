"""
DX Scoring Rubric + Export Generators
--------------------------------------
Six weighted dimensions modeled on Stripe, Plaid, Twilio, GitHub.
Also contains helpers to generate Jira tickets and GitHub issues
from scorecard results.
"""

RUBRIC = [
    {
        "key": "clarity",
        "label": "Clarity",
        "weight": 0.20,
        "definition": (
            "Can a developer understand what this endpoint does, when to use it, "
            "and what it returns within 30 seconds of landing on the page?"
        ),
        "signals": [
            "One-sentence purpose stated up front",
            "Use case made concrete (not abstract)",
            "No undefined jargon or internal terms",
            "Verb/noun naming matches the action",
        ],
    },
    {
        "key": "completeness",
        "label": "Completeness",
        "weight": 0.20,
        "definition": (
            "Does the documentation contain every field, type, default, and "
            "response shape a developer needs to call this without guessing?"
        ),
        "signals": [
            "All request parameters listed with types",
            "Required vs optional clearly marked",
            "Defaults stated",
            "Full response schema with types",
            "All status codes enumerated",
        ],
    },
    {
        "key": "example_quality",
        "label": "Example Quality",
        "weight": 0.20,
        "definition": (
            "Can a developer copy a working example, paste it into their "
            "environment, and get a successful response on the first try?"
        ),
        "signals": [
            "Runnable code, not pseudo-code",
            "Realistic values (not 'string' or 'foo')",
            "At least curl + one SDK language",
            "Sample response payload included",
            "Edge-case examples (empty, error, pagination)",
        ],
    },
    {
        "key": "error_handling",
        "label": "Error Handling Docs",
        "weight": 0.15,
        "definition": (
            "Does the documentation tell developers what can go wrong, how "
            "errors are shaped, and how to recover?"
        ),
        "signals": [
            "Error codes enumerated with meanings",
            "Error response schema shown",
            "Retry / idempotency guidance",
            "Rate-limit behavior documented",
            "Common-mistake callouts",
        ],
    },
    {
        "key": "onboarding_friction",
        "label": "Onboarding Friction",
        "weight": 0.15,
        "definition": (
            "How many minutes until a brand-new developer makes a first "
            "successful authenticated call?"
        ),
        "signals": [
            "Auth setup is visible and concrete",
            "Quickstart / first-call section exists",
            "Sandbox or test credentials offered",
            "Prerequisites are surfaced, not buried",
            "No dead-end links",
        ],
    },
    {
        "key": "consistency",
        "label": "Consistency & Conventions",
        "weight": 0.10,
        "definition": (
            "Does this endpoint follow the conventions a developer would "
            "expect from a mature REST/GraphQL API?"
        ),
        "signals": [
            "HTTP verbs used as expected",
            "Naming consistent (snake_case vs camelCase)",
            "Pagination follows house style",
            "Versioning approach is clear",
            "Field naming aligns with sibling endpoints",
        ],
    },
]


def build_system_prompt() -> str:
    rubric_text = "\n\n".join(
        f"**{i+1}. {r['label']}** (weight: {int(r['weight']*100)}%)\n"
        f"Definition: {r['definition']}\n"
        f"Signals to look for:\n" + "\n".join(f"- {s}" for s in r["signals"])
        for i, r in enumerate(RUBRIC)
    )

    return f"""You are a Senior Staff Product Manager for Developer Experience at a top-tier API company (think Stripe, Plaid, Twilio). You have shipped public APIs used by millions of developers. You evaluate API documentation with the same rigor a hiring manager applies to a senior engineer's pull request: specific, evidence-based, and uncompromising.

You will receive API documentation (either pasted text or scraped from a URL). Score it against the following six-dimension rubric. For each dimension, return a score from 0-10, two sentences of evidence quoting or paraphrasing the docs, and one concrete improvement suggestion that a PM could put directly into a Jira ticket.

# RUBRIC

{rubric_text}

# SCORING ANCHORS

- **9-10**: Stripe-tier. A developer can integrate without leaving the page.
- **7-8**: Solid. Minor friction; mostly self-serve.
- **5-6**: Functional but rough. Developer will need to experiment or DM support.
- **3-4**: Significant gaps. Onboarding will require human help.
- **0-2**: Effectively undocumented for this dimension.

Do not grade on a curve. Most public API docs score 5-7. Stripe-tier is rare.

# OUTPUT FORMAT

Return ONLY valid JSON, no prose before or after, matching this exact schema:

{{
  "summary": "One-sentence headline assessment of the docs.",
  "stripe_bar_gap": "One sentence on what would be needed to reach Stripe-tier.",
  "scores": {{
    "clarity":            {{"score": 0-10, "evidence": "...", "fix": "..."}},
    "completeness":       {{"score": 0-10, "evidence": "...", "fix": "..."}},
    "example_quality":    {{"score": 0-10, "evidence": "...", "fix": "..."}},
    "error_handling":     {{"score": 0-10, "evidence": "...", "fix": "..."}},
    "onboarding_friction":{{"score": 0-10, "evidence": "...", "fix": "..."}},
    "consistency":        {{"score": 0-10, "evidence": "...", "fix": "..."}}
  }},
  "top_strengths": ["...", "...", "..."],
  "top_improvements": [
    {{"priority": "P0", "area": "...", "change": "...", "why_it_matters": "...", "before": "Short example of the current state (quote from docs or description of what's missing)", "after": "Short example of what it should look like after the fix"}},
    {{"priority": "P0", "area": "...", "change": "...", "why_it_matters": "...", "before": "...", "after": "..."}},
    {{"priority": "P1", "area": "...", "change": "...", "why_it_matters": "...", "before": "...", "after": "..."}},
    {{"priority": "P1", "area": "...", "change": "...", "why_it_matters": "...", "before": "...", "after": "..."}},
    {{"priority": "P2", "area": "...", "change": "...", "why_it_matters": "...", "before": "...", "after": "..."}}
  ]
}}

Be brutally honest. Generic praise is worthless. If you cannot find evidence for a signal, mark it as missing rather than inferring it exists."""


def build_user_prompt(source: str, content: str) -> str:
    return f"""Source: {source}

Documentation content:
---
{content}
---

Score this documentation against the rubric and return the JSON object."""


# ──────────────────────────────────────────────
# Export helpers
# ──────────────────────────────────────────────

def _overall(result: dict) -> float:
    return sum(
        float(result["scores"][r["key"]]["score"]) * r["weight"] * 10
        for r in RUBRIC
    )


def build_jira_ticket(source: str, result: dict) -> str:
    overall = _overall(result)
    scores = result["scores"]
    improvements = result.get("top_improvements", [])

    lines = [
        f"h2. API DX Audit — {source}",
        f"",
        f"*Overall score:* {overall:.1f}/100",
        f"*Summary:* {result.get('summary', '')}",
        f"*Stripe-bar gap:* {result.get('stripe_bar_gap', '')}",
        f"",
        f"h3. Dimension Scores",
        f"||Dimension||Score||",
    ]
    for r in RUBRIC:
        s = scores[r["key"]]
        lines.append(f"| {r['label']} | {s['score']}/10 |")

    lines += ["", "h3. Prioritized Improvements", "||Priority||Area||Change||Why It Matters||"]
    for imp in improvements:
        lines.append(f"| {imp.get('priority','')} | {imp.get('area','')} | {imp.get('change','')} | {imp.get('why_it_matters','')} |")

    lines += ["", "h3. Evidence & Fixes"]
    for r in RUBRIC:
        s = scores[r["key"]]
        lines += [
            f"h4. {r['label']} — {s['score']}/10",
            f"*Evidence:* {s['evidence']}",
            f"*Fix:* {s['fix']}",
            "",
        ]

    lines += [
        "----",
        f"_Generated by API DX Scorecard · https://huggingface.co/spaces/amogh-pm/api-dx-scorer_",
    ]
    return "\n".join(lines)


def build_github_issue(source: str, result: dict) -> str:
    overall = _overall(result)
    scores = result["scores"]
    improvements = result.get("top_improvements", [])

    grade_map = {
        90: "A", 85: "A−", 80: "B+", 75: "B",
        70: "B−", 65: "C+", 60: "C", 55: "C−", 50: "D",
    }
    grade = "F"
    for threshold in sorted(grade_map.keys(), reverse=True):
        if overall >= threshold:
            grade = grade_map[threshold]
            break

    lines = [
        f"## API DX Audit: {source}",
        f"",
        f"> **Score: {overall:.1f}/100 · Grade: {grade}**",
        f"> {result.get('summary', '')}",
        f"",
        f"**Stripe-bar gap:** {result.get('stripe_bar_gap', '')}",
        f"",
        f"### Dimension Scores",
        f"",
        f"| Dimension | Score | Weight |",
        f"|---|---|---|",
    ]
    for r in RUBRIC:
        s = scores[r["key"]]
        lines.append(f"| {r['label']} | {s['score']}/10 | {int(r['weight']*100)}% |")

    lines += [
        "",
        "### Prioritized Improvements",
        "",
        "| Priority | Area | Change | Why It Matters |",
        "|---|---|---|---|",
    ]
    for imp in improvements:
        lines.append(f"| **{imp.get('priority','')}** | {imp.get('area','')} | {imp.get('change','')} | {imp.get('why_it_matters','')} |")

    lines += ["", "### Evidence & Fixes", ""]
    for r in RUBRIC:
        s = scores[r["key"]]
        lines += [
            f"<details>",
            f"<summary><b>{r['label']} — {s['score']}/10</b></summary>",
            f"",
            f"**Evidence:** {s['evidence']}",
            f"",
            f"**Fix:** {s['fix']}",
            f"",
            f"</details>",
            "",
        ]

    lines += [
        "---",
        f"*Generated by [API DX Scorecard](https://huggingface.co/spaces/amogh-pm/api-dx-scorer)*",
    ]
    return "\n".join(lines)
