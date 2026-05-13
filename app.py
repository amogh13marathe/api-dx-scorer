"""
API DX Scorecard
----------------
A PM tool that grades API documentation against the bar developers
expect from best-in-class API companies (Stripe, Plaid, Twilio).

Built by Amogh Marathe.
https://github.com/<your-handle>/api-dx-scorer
"""

from __future__ import annotations

import json
import os
import re
import textwrap
from typing import Optional

import gradio as gr
import requests
from bs4 import BeautifulSoup
from groq import Groq

from prompts import RUBRIC, build_system_prompt, build_user_prompt

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------

MODEL = "llama-3.3-70b-versatile"
MAX_DOC_CHARS = 18_000  # keep well under context window after prompt overhead
REQUEST_TIMEOUT = 15

_groq_key = os.environ.get("GROQ_API_KEY")
_client: Optional[Groq] = Groq(api_key=_groq_key) if _groq_key else None


# ----------------------------------------------------------------------
# URL fetching
# ----------------------------------------------------------------------

def fetch_url(url: str) -> str:
    """Fetch a URL and return its main text content."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    # Strip noise
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()

    # Prefer main content if marked up
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)

    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


# ----------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------

def _truncate(text: str, max_chars: int = MAX_DOC_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.7)]
    tail = text[-int(max_chars * 0.25):]
    return f"{head}\n\n[... truncated for context window ...]\n\n{tail}"


def score_documentation(source_label: str, content: str) -> dict:
    """Call Groq, return parsed JSON scorecard."""
    if _client is None:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it as a Hugging Face Space secret "
            "or export it locally. Get a free key at https://console.groq.com."
        )

    content = _truncate(content)

    completion = _client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        max_tokens=2000,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": build_user_prompt(source_label, content)},
        ],
    )

    raw = completion.choices[0].message.content
    return json.loads(raw)


def compute_overall(scores: dict) -> tuple[float, str]:
    """Weighted overall score on 0-100 scale + letter grade."""
    weighted = 0.0
    for r in RUBRIC:
        weighted += float(scores[r["key"]]["score"]) * r["weight"] * 10
    grade = (
        "A" if weighted >= 90
        else "A-" if weighted >= 85
        else "B+" if weighted >= 80
        else "B" if weighted >= 75
        else "B-" if weighted >= 70
        else "C+" if weighted >= 65
        else "C" if weighted >= 60
        else "C-" if weighted >= 55
        else "D" if weighted >= 50
        else "F"
    )
    return weighted, grade


# ----------------------------------------------------------------------
# Output formatting
# ----------------------------------------------------------------------

def _bar(score: float, width: int = 20) -> str:
    filled = round(score / 10 * width)
    return "█" * filled + "░" * (width - filled)


def format_report(source: str, result: dict) -> str:
    scores = result["scores"]
    overall, grade = compute_overall(scores)

    lines = []
    lines.append(f"# DX Scorecard — {source}\n")
    lines.append(f"### Overall: **{overall:.1f} / 100**  ·  Grade: **{grade}**\n")
    lines.append(f"> {result.get('summary', '').strip()}\n")
    lines.append(f"**Stripe-bar gap:** {result.get('stripe_bar_gap', '').strip()}\n")
    lines.append("---\n")
    lines.append("## Scores by Dimension\n")
    lines.append("| Dimension | Score | Weight | Bar |")
    lines.append("|---|---|---|---|")
    for r in RUBRIC:
        s = scores[r["key"]]
        lines.append(
            f"| **{r['label']}** | {s['score']}/10 "
            f"| {int(r['weight']*100)}% | `{_bar(s['score'])}` |"
        )
    lines.append("\n## Evidence & Fixes\n")
    for r in RUBRIC:
        s = scores[r["key"]]
        lines.append(f"### {r['label']} — {s['score']}/10")
        lines.append(f"**Evidence:** {s['evidence']}\n")
        lines.append(f"**Suggested fix:** {s['fix']}\n")

    lines.append("---\n")
    lines.append("## Top Strengths\n")
    for s in result.get("top_strengths", []):
        lines.append(f"- {s}")
    lines.append("\n## Top Improvements (Prioritized)\n")
    lines.append("| Priority | Area | Change | Why It Matters |")
    lines.append("|---|---|---|---|")
    for imp in result.get("top_improvements", []):
        lines.append(
            f"| **{imp.get('priority','')}** "
            f"| {imp.get('area','')} "
            f"| {imp.get('change','')} "
            f"| {imp.get('why_it_matters','')} |"
        )

    return "\n".join(lines)


# ----------------------------------------------------------------------
# Gradio handlers
# ----------------------------------------------------------------------

def run_scorecard(input_type: str, url: str, pasted: str):
    try:
        if input_type == "URL":
            url = (url or "").strip()
            if not url:
                return "Please paste a URL to public API documentation.", ""
            content = fetch_url(url)
            source = url
        else:
            pasted = (pasted or "").strip()
            if not pasted:
                return "Please paste the endpoint documentation.", ""
            content = pasted
            source = "Pasted documentation"

        if len(content) < 200:
            return (
                "The content I received is too short to evaluate "
                f"({len(content)} chars). Paste more of the docs or use a "
                "different URL.",
                "",
            )

        result = score_documentation(source, content)
        report = format_report(source, result)
        return report, json.dumps(result, indent=2)
    except json.JSONDecodeError as e:
        return f"The model returned malformed JSON. Retry. ({e})", ""
    except requests.RequestException as e:
        return f"Could not fetch URL: {e}", ""
    except RuntimeError as e:
        return f"{e}", ""
    except Exception as e:  # surface anything else
        return f"Unexpected error: {type(e).__name__}: {e}", ""


# ----------------------------------------------------------------------
# UI
# ----------------------------------------------------------------------

EXAMPLE_URLS = [
    "https://docs.stripe.com/api/charges/create",
    "https://plaid.com/docs/api/products/transactions/",
    "https://docs.github.com/en/rest/issues/issues",
    "https://developers.cloudflare.com/api/operations/zone-create-zone",
]

EXAMPLE_PASTE = textwrap.dedent("""\
    POST /v1/transfers

    Creates a transfer.

    Parameters:
    - amount: integer
    - currency: string
    - destination: string

    Returns the transfer object.
""")

DESCRIPTION = """\
**API DX Scorecard** grades public API documentation against a six-dimension
rubric modeled on the bar set by Stripe, Plaid, Twilio, and GitHub.

Paste a URL or the raw documentation. Get back a weighted score, evidence for
each dimension, and a prioritized list of fixes a PM could drop directly into
a sprint.

Built by **[Amogh Marathe](https://www.linkedin.com/in/amoghmarathe/)** as a
PM artifact for API & Developer Experience roles.
[Code on GitHub](https://github.com/) · [Case study](https://github.com/)
"""

with gr.Blocks(title="API DX Scorecard", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🔌 API DX Scorecard")
    gr.Markdown(DESCRIPTION)

    with gr.Row():
        with gr.Column(scale=1):
            input_type = gr.Radio(
                ["URL", "Paste docs"],
                value="URL",
                label="Input type",
            )
            url_box = gr.Textbox(
                label="API docs URL",
                placeholder="https://docs.stripe.com/api/charges/create",
                lines=1,
            )
            paste_box = gr.Textbox(
                label="Paste API docs",
                placeholder="POST /v1/transfers ...",
                lines=10,
                visible=False,
            )
            run_btn = gr.Button("Score it", variant="primary")

            gr.Examples(
                examples=[[u] for u in EXAMPLE_URLS],
                inputs=[url_box],
                label="Try a real API",
            )

        with gr.Column(scale=2):
            report_out = gr.Markdown(label="Scorecard")
            with gr.Accordion("Raw JSON (for engineers)", open=False):
                json_out = gr.Code(label="", language="json")

    def _toggle(t):
        return (
            gr.update(visible=(t == "URL")),
            gr.update(visible=(t == "Paste docs")),
        )

    input_type.change(_toggle, inputs=input_type, outputs=[url_box, paste_box])
    run_btn.click(
        run_scorecard,
        inputs=[input_type, url_box, paste_box],
        outputs=[report_out, json_out],
    )

    gr.Markdown(
        "---\n"
        "_The model is Llama 3.3 70B via Groq. Scores are directional, not "
        "absolute. The rubric and weights are open in `prompts.py`._"
    )


if __name__ == "__main__":
    demo.launch()
