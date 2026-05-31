# Case Study — API DX Scorecard

> A PRD-style writeup of the tool. Reading time: 5 minutes.

---

## TL;DR

**Problem:** PMs in API and Developer Experience orgs evaluate documentation anecdotally. There is no shared rubric, no scoreable artifact, and no way to measure improvement across a docs portfolio or against competitors.

**Solution:** A six-dimension weighted scorecard, delivered as a free public tool. Paste a URL or raw docs → get a weighted 0–100 score, evidence per dimension, and a prioritized fix list a PM could drop into a sprint.

**Why now:** LLMs make rubric-based document evaluation cheap enough to run on every endpoint, every release.

**Outcome (claim):** A Senior/Staff PM for API & DX can use this to set a measurable doc-quality baseline, prioritize the highest-leverage fixes, and track improvement over time — instead of relying on "Stripe is better" hand-waving.

---

## 1. The problem space

Developer experience drives API adoption. Public benchmarks (Postman 2024 State of the API, Twilio's own activation studies, Stripe's docs investment trajectory from 2014–present) point to a consistent finding:

> **Time-to-first-successful-call is the single best predictor of activation, retention, and expansion.**

Time-to-first-call is dominated by documentation quality, not API design. Yet PMs in API and DX orgs typically evaluate docs by feel:

- "These examples are rough."
- "Their auth flow is confusing."
- "Stripe is better."

These are correct observations, but they aren't measurable, comparable, or trackable. You cannot run a roadmap on them.

**Concrete pains this creates:**

1. **No baseline.** Teams don't know if their docs improved this quarter.
2. **No prioritization.** Every fix looks equally important, so the loudest internal voice wins.
3. **No competitive signal.** Teams can't quantify how far behind Stripe they are on a given surface.
4. **No portfolio view.** A docs team owning 200 endpoints has no triage tool — only complaints from sales.

## 2. Who this serves

Primary user: **PMs in API and Developer Experience roles** at companies whose product *is* the API (Plaid, Stripe, Twilio, GitHub, Cloudflare, Postman, Fivetran, dbt Labs, Confluent).

Secondary users:

- **Technical writers** who own documentation and need a triage tool.
- **DevRel** who need a competitive benchmark for "why our docs."
- **Engineering leads** evaluating their own API surface before launch.

## 3. The rubric — and why these six dimensions

I considered eleven candidate dimensions during design. The final six are the ones that (a) a developer evaluates within 60 seconds of landing on a page and (b) a PM can move with a sprint of work. The eliminated ones were collapsed into others or punted to roadmap.

| Dimension | Weight | Why this weight |
|---|---|---|
| **Clarity** | 20% | The first 30 seconds of a page determine whether the developer keeps reading. Highest leverage. |
| **Completeness** | 20% | An incomplete page forces the developer to leave (DM support, file an issue, churn). Tied for highest. |
| **Example Quality** | 20% | Copy-paste code is what 80%+ of developers reach for first. Equal weight justified. |
| **Error Handling** | 15% | First-class for retention and trust, but the volume of evidence per endpoint is smaller than the top three. |
| **Onboarding Friction** | 15% | Often documented elsewhere (a quickstart page), so per-endpoint signal is lower — but still required to surface here. |
| **Consistency** | 10% | Matters more across the surface than at one endpoint. Underweighted on purpose. |

The weights are encoded in `prompts.py` and easy to tune. A team using this internally would calibrate the weights against their own activation funnel.

### Dimensions I considered and dropped

- **Search experience** → cross-cutting, not per-endpoint.
- **Visual design** → too subjective and weakly correlated with developer success.
- **Versioning** → folded into Consistency.
- **Localization** → important for some companies, not the median case.
- **Interactive playground** → folded into Example Quality.

## 4. How the scoring works

The scorer is an LLM prompted to behave like a Senior Staff PM for DX at Stripe. The prompt:

1. Defines the rubric, weights, and 0–10 scoring anchors with explicit calibration ("Stripe-tier is rare").
2. Forces structured JSON output (Groq's JSON mode) so the result is parseable and stable.
3. Requires evidence per dimension — the model must quote or paraphrase the docs, not assert generic praise.
4. Demands one actionable fix per dimension, written so a PM could put it directly into a Jira ticket.

The Python layer (`app.py`):

- Fetches the URL, strips nav/header/footer/scripts via BeautifulSoup, extracts main content.
- Truncates to ~18K chars to stay inside the context window with prompt overhead.
- Calls Groq with temperature 0.2 (low variance, still allows some judgment).
- Computes the weighted overall and letter grade in code (deterministic — does not trust the model with arithmetic).
- Renders Markdown for humans + raw JSON for engineers.

## 5. Tradeoffs and limitations

**Tradeoff: directional, not absolute.** A single model run is one opinion. Production use would need to ensemble across 3+ model calls and report a confidence band. I deferred this to keep the demo cheap and fast.

**Tradeoff: per-endpoint, not portfolio.** Real PM value comes from scoring 200 endpoints and producing a heatmap. The single-endpoint demo is the wedge; portfolio scanning is the next milestone.

**Limitation: scraping is best-effort.** Some docs sites (Stripe, Plaid) are JS-rendered or behind smart routing. The current scraper handles 80%+ of public docs cleanly. Paste-docs mode is the fallback.

**Limitation: the model can be wrong.** Evidence quoting mitigates this — a reviewer can spot-check the citation against the docs. It does not eliminate the risk.

## 6. Eval methodology (how I'd validate this in production)

In a real PM role, I would not ship this tool without:

1. **Golden set.** Score 25 endpoints across Stripe, Plaid, Twilio, GitHub, and Cloudflare. Have two senior PMs independently rank them. Measure Spearman correlation between human ranking and tool ranking. Target > 0.7.
2. **Calibration test.** Inject deliberately bad docs (remove all examples, strip error codes) and verify the relevant dimensions score < 4.
3. **Inter-run consistency.** Run the same input 10 times. Measure overall-score variance. Target σ < 4 points.
4. **Human-in-the-loop.** The first 100 production runs go through a docs lead before any score is published anywhere. Sentiment is captured. The rubric is refined from that feedback.

These are not yet implemented in this demo. They are the next checkpoints.

## 7. What I'd ship next

**Quarter 1 (90 days):**
- **Portfolio scan.** Crawl a docs site, score every endpoint, produce a heatmap.
- **Diff mode.** Score the same endpoint over time, surface what improved or regressed.
- **Confidence intervals.** Ensemble across 3 runs.

**Quarter 2:**
- **Competitive benchmark.** Point at your endpoint and the top 3 competitors. Get the gap report.
- **Internal mode.** Replace public-docs scraping with OpenAPI spec ingestion. Score pre-launch.

**Quarter 3:**
- **Linear / Jira integration.** Fire one ticket per P0 finding directly into the docs team's backlog.
- **CI integration.** Block a docs PR if the score drops by > 5 points on the changed endpoint.

## 8. What this artifact demonstrates

This is the part recruiters care about. If I were the hiring manager, I would expect a candidate for a Senior/Staff API & DX PM role to demonstrate:

- **A measurable mental model for DX**, not just qualitative taste. → The rubric and weights are the proof.
- **Comfort going from idea → code → public deployment** without an engineer holding their hand. → This demo, built and shipped in an afternoon, is the proof.
- **A bias toward systems**, not features. → The roadmap (portfolio, diff, competitive benchmark) is the proof.
- **Brutally honest evaluation**, not advocacy. → The scoring anchors ("most public docs are 5–7") are the proof.

If those are the qualities you're hiring for, the [LinkedIn link](https://www.linkedin.com/in/amoghmarathe/) is at the top of the README.

---

_Built by Amogh Marathe — Senior TPM targeting Staff / Senior Staff PM roles in API & Developer Experience._
