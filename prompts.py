"""
DX Scoring Rubric
-----------------
Six weighted dimensions modeled on the bar that best-in-class API companies
(Stripe, Plaid, Twilio, GitHub) hold themselves to. Each dimension is scored
0-10 with explicit evidence and an actionable fix.

Rubric design rationale:
- Clarity & Completeness are weighted highest (20% each) because they drive
  time-to-first-call, the single best predictor of activation.
- Examples are weighted equal to Completeness because copy-pasteable code
  is what a developer actually scans for first.
- Error Handling is treated as a first-class citizen — undocumented error
  modes are the #1 driver of support load and churn.
- Onboarding Friction captures the "is auth explained / is there a sandbox"
  question that determines whether a developer ever reaches the endpoint.
- Consistency is the smallest weight because it matters more across the
  surface area than at a single endpoint.
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
        [
            f"**{i+1}. {r['label']}** (weight: {int(r['weight']*100)}%)\n"
            f"Definition: {r['definition']}\n"
            f"Signals to look for:\n"
            + "\n".join([f"- {s}" for s in r["signals"]])
            for i, r in enumerate(RUBRIC)
        ]
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
    {{"priority": "P0", "area": "...", "change": "...", "why_it_matters": "..."}},
    {{"priority": "P0", "area": "...", "change": "...", "why_it_matters": "..."}},
    {{"priority": "P1", "area": "...", "change": "...", "why_it_matters": "..."}},
    {{"priority": "P1", "area": "...", "change": "...", "why_it_matters": "..."}},
    {{"priority": "P2", "area": "...", "change": "...", "why_it_matters": "..."}}
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
