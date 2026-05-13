---
title: API DX Scorecard
emoji: 🔌
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
---

# API DX Scorecard

**A PM tool that grades API documentation against the bar developers actually expect.**
Paste a URL or raw docs → get a weighted score across six DX dimensions, with evidence and a prioritized fix list a PM could drop into a sprint.

| | |
|---|---|
| **Live demo** | _Hugging Face Spaces link goes here after deploy_ |
| **Why it exists** | [Case study](./CASE_STUDY.md) |
| **Model** | Llama 3.3 70B via Groq (free) |
| **Stack** | Python · Gradio · Groq · BeautifulSoup |
| **Built by** | [Amogh Marathe](https://www.linkedin.com/in/amoghmarathe/) — Senior TPM |

---

## The problem

Developer experience is the #1 driver of API adoption, and API documentation is the surface where DX is won or lost. Yet most PMs in API/DX orgs evaluate docs anecdotally: "this feels rough," "Stripe is better." There's no shared rubric, no scoreable artifact, no way to compare endpoints across a portfolio or measure improvement over time.

That gap is what this tool closes.

## What it does

Input: a URL to public API documentation, or raw pasted docs.
Output: a weighted scorecard across six dimensions plus a prioritized improvement list.

The six dimensions (full rubric in [`prompts.py`](./prompts.py)):

| Dimension | Weight | Question it answers |
|---|---|---|
| **Clarity** | 20% | Can a developer understand this in 30 seconds? |
| **Completeness** | 20% | Are all fields, types, defaults, and responses documented? |
| **Example Quality** | 20% | Can a developer copy, paste, and get a 200 on the first try? |
| **Error Handling** | 15% | Are error codes, retries, and idempotency documented? |
| **Onboarding Friction** | 15% | How fast to first authenticated call? |
| **Consistency** | 10% | Does it follow conventions a developer expects? |

Each dimension gets a score from 0–10, two sentences of evidence quoted from the docs, and one concrete fix. The overall is a weighted 0–100 with a letter grade.

## Example output (Stripe's `POST /v1/charges`)

```
Overall: 92.5 / 100 · Grade: A

Clarity                ██████████████████░░  9/10
Completeness           ████████████████████  10/10
Example Quality        ██████████████████░░  9/10
Error Handling         ██████████████████░░  9/10
Onboarding Friction    ████████████████░░░░  8/10
Consistency            ████████████████████  10/10

Top improvements (P0):
1. Surface idempotency-key behavior above the parameter table, not below.
2. Add a "first-call" sandbox snippet at the top of the page.
```

## Why this rubric, these weights

Two short reads if you want the design rationale:
- [CASE_STUDY.md](./CASE_STUDY.md) — full PRD-style writeup: problem, framework, weight rationale, eval methodology, what I'd build next.
- [`prompts.py`](./prompts.py) — the actual scoring prompt and rubric, in code.

The short version: Clarity, Completeness, and Examples are weighted equally and highest (20% each) because they drive **time-to-first-call**, the single best predictor of developer activation in published research from Stripe, Twilio, and Postman. Error Handling and Onboarding sit at 15% — they are first-class but the volume of evidence is smaller per endpoint. Consistency is 10% because it matters more across the surface area than at a single endpoint.

## Run it locally

```bash
git clone <this repo>
cd api-dx-scorer
pip install -r requirements.txt
export GROQ_API_KEY=sk_...   # free at console.groq.com
python app.py
```

Opens at `http://localhost:7860`.

## Deploy to Hugging Face Spaces

1. Create a new Space at https://huggingface.co/new-space — pick **Gradio** SDK.
2. Push this folder to the Space's git remote (HF gives you the URL).
3. In the Space's **Settings → Variables and secrets**, add `GROQ_API_KEY` as a secret.
4. The Space rebuilds and the demo goes live.

Full step-by-step in [DEPLOY.md](./DEPLOY.md).

## Why I built this

I'm targeting Senior/Staff PM roles in API and Developer Experience (Plaid, Stripe, GitHub, Cloudflare, Twilio). The hiring bar for those roles is not "have you used an API" — it's "do you think about developer experience as a measurable system?"

This is the artifact form of that answer. The rubric, the weights, and the prioritization heuristics are the same ones I'd bring into a planning conversation on day one.

## Roadmap (what I'd build next)

- **Diff mode** — score the same endpoint over time, show what improved.
- **Portfolio scan** — point it at a whole docs site, get a heatmap.
- **Competitive benchmark** — score your endpoint vs. the top 3 competitors automatically.
- **Internal-mode** — replace public docs with internal OpenAPI specs; same rubric.
- **Slack/Linear integration** — fire a ticket per P0 finding directly into the docs team's backlog.

## License

MIT. Use it, fork it, ship it.

---

_Built by Amogh Marathe. If you're hiring for API/DX PM roles, [let's talk](https://www.linkedin.com/in/amoghmarathe/)._
