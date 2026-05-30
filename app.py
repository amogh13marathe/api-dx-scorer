"""
API DX Scorecard — v2
---------------------
Grades API documentation against a six-dimension rubric modeled on
Stripe, Plaid, Twilio, and GitHub. Now with side-by-side comparison,
visual score display, and one-click export to Jira / GitHub issue.

Built by Amogh Marathe.
https://github.com/amogh13marathe/api-dx-scorer
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

from prompts import RUBRIC, build_system_prompt, build_user_prompt, build_jira_ticket, build_github_issue

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

MODEL = "llama-3.3-70b-versatile"
MAX_DOC_CHARS = 18_000
REQUEST_TIMEOUT = 15

_groq_key = os.environ.get("GROQ_API_KEY")
_client: Optional[Groq] = Groq(api_key=_groq_key) if _groq_key else None


# ──────────────────────────────────────────────
# Fetching
# ──────────────────────────────────────────────

def fetch_url(url: str) -> str:
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
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


# ──────────────────────────────────────────────
# Scoring
# ──────────────────────────────────────────────

def _truncate(text: str, max_chars: int = MAX_DOC_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.7)]
    tail = text[-int(max_chars * 0.25):]
    return f"{head}\n\n[... truncated ...]\n\n{tail}"


def score_documentation(source_label: str, content: str) -> dict:
    if _client is None:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it as a HuggingFace Space secret "
            "(Settings → Variables and secrets). Get a free key at https://console.groq.com."
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
    return json.loads(completion.choices[0].message.content)


def compute_overall(scores: dict) -> tuple[float, str]:
    weighted = sum(
        float(scores[r["key"]]["score"]) * r["weight"] * 10
        for r in RUBRIC
    )
    grade = (
        "A" if weighted >= 90 else
        "A−" if weighted >= 85 else
        "B+" if weighted >= 80 else
        "B"  if weighted >= 75 else
        "B−" if weighted >= 70 else
        "C+" if weighted >= 65 else
        "C"  if weighted >= 60 else
        "C−" if weighted >= 55 else
        "D"  if weighted >= 50 else "F"
    )
    return weighted, grade


# ──────────────────────────────────────────────
# HTML rendering
# ──────────────────────────────────────────────

GRADE_COLOR = {
    "A": "#22c55e", "A−": "#4ade80",
    "B+": "#86efac", "B": "#fbbf24", "B−": "#f59e0b",
    "C+": "#f97316", "C": "#ef4444", "C−": "#dc2626",
    "D": "#991b1b", "F": "#7f1d1d",
}

def score_color(s: float) -> str:
    if s >= 8: return "#22c55e"
    if s >= 6: return "#fbbf24"
    if s >= 4: return "#f97316"
    return "#ef4444"

def render_bar(score: float) -> str:
    pct = score / 10 * 100
    color = score_color(score)
    return (
        f'<div style="background:#e5e7eb;border-radius:4px;height:10px;width:100%;">'
        f'<div style="background:{color};width:{pct:.0f}%;height:10px;border-radius:4px;"></div>'
        f'</div>'
    )

def render_scorecard_html(source: str, result: dict) -> str:
    scores = result["scores"]
    overall, grade = compute_overall(scores)
    grade_col = GRADE_COLOR.get(grade, "#6b7280")

    rows = ""
    for r in RUBRIC:
        s = scores[r["key"]]
        sc = float(s["score"])
        col = score_color(sc)
        rows += f"""
        <tr>
          <td style="padding:10px 8px;font-weight:600;">{r['label']}</td>
          <td style="padding:10px 8px;text-align:center;">
            <span style="color:{col};font-weight:700;font-size:1.1em;">{sc:.0f}</span>
            <span style="color:#9ca3af;">/10</span>
          </td>
          <td style="padding:10px 8px;width:160px;">{render_bar(sc)}</td>
          <td style="padding:10px 8px;color:#6b7280;font-size:0.85em;">{int(r['weight']*100)}%</td>
        </tr>
        <tr>
          <td colspan="4" style="padding:2px 8px 12px 8px;font-size:0.82em;color:#4b5563;border-bottom:1px solid #f3f4f6;">
            <b>Evidence:</b> {s['evidence']}<br>
            <b>Fix:</b> {s['fix']}
          </td>
        </tr>"""

    strengths_html = "".join(f'<li style="margin:4px 0;">{s}</li>' for s in result.get("top_strengths", []))

    improvements_html = ""
    for imp in result.get("top_improvements", []):
        p = imp.get("priority", "")
        p_color = "#ef4444" if p == "P0" else "#f59e0b" if p == "P1" else "#6b7280"
        improvements_html += f"""
        <tr>
          <td style="padding:8px;"><span style="color:{p_color};font-weight:700;">{p}</span></td>
          <td style="padding:8px;">{imp.get('area','')}</td>
          <td style="padding:8px;">{imp.get('change','')}</td>
          <td style="padding:8px;color:#6b7280;font-size:0.85em;">{imp.get('why_it_matters','')}</td>
        </tr>"""

    source_display = source if len(source) < 60 else source[:57] + "..."

    return f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:800px;">

  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:20px 24px;margin-bottom:20px;display:flex;align-items:center;gap:24px;">
    <div style="text-align:center;min-width:90px;">
      <div style="font-size:3em;font-weight:800;color:{grade_col};line-height:1;">{grade}</div>
      <div style="font-size:0.75em;color:#9ca3af;margin-top:2px;">Grade</div>
    </div>
    <div>
      <div style="font-size:1.5em;font-weight:700;color:#1e293b;">{overall:.1f} <span style="font-size:0.6em;color:#9ca3af;">/ 100</span></div>
      <div style="font-size:0.85em;color:#64748b;margin-top:4px;word-break:break-all;">{source_display}</div>
      <div style="font-size:0.82em;color:#94a3b8;margin-top:6px;font-style:italic;">{result.get('summary','')}</div>
    </div>
  </div>

  <div style="background:#fff3cd;border:1px solid #ffc107;border-radius:8px;padding:12px 16px;margin-bottom:20px;font-size:0.85em;">
    <b>Stripe-bar gap:</b> {result.get('stripe_bar_gap','')}
  </div>

  <table style="width:100%;border-collapse:collapse;margin-bottom:24px;">
    <thead>
      <tr style="background:#f1f5f9;">
        <th style="padding:10px 8px;text-align:left;font-size:0.8em;color:#64748b;text-transform:uppercase;letter-spacing:.05em;">Dimension</th>
        <th style="padding:10px 8px;text-align:center;font-size:0.8em;color:#64748b;text-transform:uppercase;">Score</th>
        <th style="padding:10px 8px;font-size:0.8em;color:#64748b;text-transform:uppercase;">Bar</th>
        <th style="padding:10px 8px;font-size:0.8em;color:#64748b;text-transform:uppercase;">Weight</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:8px;">
    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;">
      <div style="font-weight:700;color:#166534;margin-bottom:8px;">Top Strengths</div>
      <ul style="margin:0;padding-left:18px;font-size:0.85em;color:#15803d;">{strengths_html}</ul>
    </div>
    <div style="background:#fef2f2;border:1px solid #fecaca;border-radius:8px;padding:16px;">
      <div style="font-weight:700;color:#991b1b;margin-bottom:8px;">Top Improvements</div>
      <table style="width:100%;font-size:0.8em;border-collapse:collapse;">
        <tbody>{improvements_html}</tbody>
      </table>
    </div>
  </div>

</div>"""


def render_comparison_html(src_a: str, res_a: dict, src_b: str, res_b: dict) -> str:
    ov_a, gr_a = compute_overall(res_a["scores"])
    ov_b, gr_b = compute_overall(res_b["scores"])
    winner_a = ov_a >= ov_b

    rows = ""
    for r in RUBRIC:
        sa = float(res_a["scores"][r["key"]]["score"])
        sb = float(res_b["scores"][r["key"]]["score"])
        bold_a = "font-weight:700;" if sa > sb else ""
        bold_b = "font-weight:700;" if sb > sa else ""
        rows += f"""<tr style="border-bottom:1px solid #f3f4f6;">
          <td style="padding:10px 8px;font-weight:600;">{r['label']}</td>
          <td style="padding:10px 8px;text-align:center;{bold_a}color:{score_color(sa)};">{sa:.0f}/10 {render_bar(sa)}</td>
          <td style="padding:10px 8px;text-align:center;{bold_b}color:{score_color(sb)};">{sb:.0f}/10 {render_bar(sb)}</td>
        </tr>"""

    ga_col = GRADE_COLOR.get(gr_a, "#6b7280")
    gb_col = GRADE_COLOR.get(gr_b, "#6b7280")
    short_a = src_a[:35] + "..." if len(src_a) > 38 else src_a
    short_b = src_b[:35] + "..." if len(src_b) > 38 else src_b

    winner_badge = f"""
    <div style="text-align:center;margin-bottom:16px;">
      <span style="background:#dcfce7;color:#166534;padding:6px 16px;border-radius:20px;font-weight:700;font-size:0.9em;">
        Winner: {'A' if winner_a else 'B'} — {short_a if winner_a else short_b}
      </span>
    </div>""" if ov_a != ov_b else ""

    return f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:900px;">
  {winner_badge}
  <table style="width:100%;border-collapse:collapse;">
    <thead>
      <tr style="background:#f1f5f9;">
        <th style="padding:10px 8px;text-align:left;width:160px;font-size:0.8em;color:#64748b;text-transform:uppercase;">Dimension</th>
        <th style="padding:10px 8px;text-align:center;font-size:0.8em;color:#1e293b;">
          <span style="color:{ga_col};font-size:1.3em;font-weight:800;">{gr_a}</span> {ov_a:.1f}/100<br>
          <span style="font-weight:400;color:#64748b;font-size:0.85em;">{short_a}</span>
        </th>
        <th style="padding:10px 8px;text-align:center;font-size:0.8em;color:#1e293b;">
          <span style="color:{gb_col};font-size:1.3em;font-weight:800;">{gr_b}</span> {ov_b:.1f}/100<br>
          <span style="font-weight:400;color:#64748b;font-size:0.85em;">{short_b}</span>
        </th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""


# ──────────────────────────────────────────────
# Markdown report (for download)
# ──────────────────────────────────────────────

def format_markdown_report(source: str, result: dict) -> str:
    scores = result["scores"]
    overall, grade = compute_overall(scores)
    lines = [
        f"# API DX Scorecard — {source}",
        f"\n**Overall: {overall:.1f} / 100 · Grade: {grade}**",
        f"\n> {result.get('summary','').strip()}",
        f"\n**Stripe-bar gap:** {result.get('stripe_bar_gap','').strip()}",
        "\n---\n## Scores\n",
        "| Dimension | Score | Weight |",
        "|---|---|---|",
    ]
    for r in RUBRIC:
        s = scores[r["key"]]
        lines.append(f"| **{r['label']}** | {s['score']}/10 | {int(r['weight']*100)}% |")
    lines.append("\n## Evidence & Fixes\n")
    for r in RUBRIC:
        s = scores[r["key"]]
        lines += [
            f"### {r['label']} — {s['score']}/10",
            f"**Evidence:** {s['evidence']}",
            f"**Fix:** {s['fix']}\n",
        ]
    lines.append("## Top Strengths\n")
    for st in result.get("top_strengths", []):
        lines.append(f"- {st}")
    lines.append("\n## Top Improvements\n")
    lines.append("| Priority | Area | Change | Why It Matters |")
    lines.append("|---|---|---|---|")
    for imp in result.get("top_improvements", []):
        lines.append(f"| **{imp.get('priority','')}** | {imp.get('area','')} | {imp.get('change','')} | {imp.get('why_it_matters','')} |")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Handlers
# ──────────────────────────────────────────────

def _resolve_input(input_type, url, pasted):
    if input_type == "URL":
        url = (url or "").strip()
        if not url:
            raise ValueError("Paste a URL to public API documentation.")
        return fetch_url(url), url
    else:
        pasted = (pasted or "").strip()
        if not pasted:
            raise ValueError("Paste the API documentation text.")
        return pasted, "Pasted documentation"


def run_single(input_type, url, pasted):
    try:
        content, source = _resolve_input(input_type, url, pasted)
        if len(content) < 200:
            return f"Content too short ({len(content)} chars). Try a different URL or paste more text.", "", "", ""
        result = score_documentation(source, content)
        html = render_scorecard_html(source, result)
        md = format_markdown_report(source, result)
        jira = build_jira_ticket(source, result)
        gh = build_github_issue(source, result)
        return html, md, jira, gh
    except json.JSONDecodeError as e:
        return f"Model returned malformed JSON. Retry. ({e})", "", "", ""
    except requests.RequestException as e:
        return f"Could not fetch URL: {e}", "", "", ""
    except (ValueError, RuntimeError) as e:
        return str(e), "", "", ""
    except Exception as e:
        return f"Unexpected error: {type(e).__name__}: {e}", "", "", ""


def run_compare(url_a, url_b):
    try:
        if not (url_a or "").strip() or not (url_b or "").strip():
            return "Paste two URLs to compare.", ""
        content_a = fetch_url(url_a.strip())
        content_b = fetch_url(url_b.strip())
        res_a = score_documentation(url_a.strip(), content_a)
        res_b = score_documentation(url_b.strip(), content_b)
        html = render_comparison_html(url_a.strip(), res_a, url_b.strip(), res_b)
        md_a = format_markdown_report(url_a.strip(), res_a)
        md_b = format_markdown_report(url_b.strip(), res_b)
        combined_md = f"# Comparison Report\n\n## A: {url_a}\n\n{md_a}\n\n---\n\n## B: {url_b}\n\n{md_b}"
        return html, combined_md
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}", ""


# ──────────────────────────────────────────────
# UI
# ──────────────────────────────────────────────

EXAMPLE_URLS = [
    "https://docs.stripe.com/api/charges/create",
    "https://plaid.com/docs/api/products/transactions/",
    "https://docs.github.com/en/rest/issues/issues",
    "https://developers.cloudflare.com/api/operations/zone-create-zone",
]

DESCRIPTION = """\
**API DX Scorecard** grades public API documentation against a six-dimension rubric  
modeled on the bar set by Stripe, Plaid, Twilio, and GitHub.  
Built by **[Amogh Marathe](https://www.linkedin.com/in/amoghmarathe/)** · 
[GitHub](https://github.com/amogh13marathe/api-dx-scorer)
"""

CSS = """
.tab-nav button { font-weight: 600; }
.export-box textarea { font-family: monospace; font-size: 0.82em; }
"""

with gr.Blocks(title="API DX Scorecard", theme=gr.themes.Soft(), css=CSS) as demo:
    gr.Markdown("# 🔌 API DX Scorecard")
    gr.Markdown(DESCRIPTION)

    with gr.Tabs():

        # ── Tab 1: Single Score ──────────────────────────────
        with gr.Tab("Score a doc"):
            with gr.Row():
                with gr.Column(scale=1):
                    input_type = gr.Radio(["URL", "Paste docs"], value="URL", label="Input type")
                    url_box = gr.Textbox(label="API docs URL", placeholder="https://docs.stripe.com/api/charges/create", lines=1)
                    paste_box = gr.Textbox(label="Paste API docs", placeholder="POST /v1/...", lines=10, visible=False)
                    run_btn = gr.Button("Score it ⚡", variant="primary", size="lg")
                    gr.Examples(examples=[[u] for u in EXAMPLE_URLS], inputs=[url_box], label="Try a real API")

                with gr.Column(scale=2):
                    scorecard_html = gr.HTML(label="Scorecard")

            with gr.Accordion("Export", open=False):
                with gr.Tabs():
                    with gr.Tab("Markdown report"):
                        md_out = gr.Textbox(label="", lines=20, show_copy_button=True, elem_classes=["export-box"])
                    with gr.Tab("Jira ticket"):
                        jira_out = gr.Textbox(label="Copy into Jira description", lines=20, show_copy_button=True, elem_classes=["export-box"])
                    with gr.Tab("GitHub issue"):
                        gh_out = gr.Textbox(label="Copy into GitHub Issues", lines=20, show_copy_button=True, elem_classes=["export-box"])

            def _toggle(t):
                return gr.update(visible=(t == "URL")), gr.update(visible=(t == "Paste docs"))

            input_type.change(_toggle, inputs=input_type, outputs=[url_box, paste_box])
            run_btn.click(
                run_single,
                inputs=[input_type, url_box, paste_box],
                outputs=[scorecard_html, md_out, jira_out, gh_out],
            )

        # ── Tab 2: Compare ──────────────────────────────────
        with gr.Tab("Compare two docs"):
            with gr.Row():
                url_a = gr.Textbox(label="API docs URL — A", placeholder="https://docs.stripe.com/api/charges/create", lines=1)
                url_b = gr.Textbox(label="API docs URL — B", placeholder="https://plaid.com/docs/api/products/transactions/", lines=1)
            compare_btn = gr.Button("Compare ⚡", variant="primary", size="lg")
            compare_html = gr.HTML(label="Comparison")
            with gr.Accordion("Combined markdown report", open=False):
                compare_md = gr.Textbox(label="", lines=20, show_copy_button=True, elem_classes=["export-box"])

            compare_btn.click(
                run_compare,
                inputs=[url_a, url_b],
                outputs=[compare_html, compare_md],
            )

    gr.Markdown(
        "---\n"
        "_Model: Llama 3.3 70B via Groq (free). "
        "Scores are directional, not absolute. Rubric and weights are open in `prompts.py`._"
    )

if __name__ == "__main__":
    demo.launch()
