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

MODEL_PRIMARY  = "llama-3.3-70b-versatile"   # 100K TPD free tier
MODEL_FALLBACK = "llama-3.1-8b-instant"       # 500K TPD free tier — auto-used if primary hits rate limit
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

    # Detect JS-rendered shells (< 400 chars of real content after stripping)
    if len(text.strip()) < 400:
        raise ValueError(
            "This page appears to be JavaScript-rendered (the HTML shell returned almost no text). "
            "Try pasting the documentation text directly using the 'Paste docs' input type instead."
        )

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
    for model in (MODEL_PRIMARY, MODEL_FALLBACK):
        # 8B model has a tight TPM cap — truncate harder
        max_chars = MAX_DOC_CHARS if model == MODEL_PRIMARY else 8_000
        truncated = _truncate(content, max_chars)
        messages = [
            {"role": "system", "content": build_system_prompt()},
            {"role": "user", "content": build_user_prompt(source_label, truncated)},
        ]
        try:
            completion = _client.chat.completions.create(
                model=model,
                temperature=0.2,
                max_tokens=2000,
                response_format={"type": "json_object"},
                messages=messages,
            )
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            err = str(e)
            if "rate_limit_exceeded" in err and model == MODEL_PRIMARY:
                continue
            raise
    raise RuntimeError(
        "Daily token limit reached on both models. Groq free tier resets every 24 hours. "
        "Try again tomorrow, or upgrade at console.groq.com/settings/billing."
    )


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
    "A": "#16a34a", "A−": "#22c55e",
    "B+": "#65a30d", "B": "#ca8a04", "B−": "#d97706",
    "C+": "#ea580c", "C": "#dc2626", "C−": "#b91c1c",
    "D": "#7f1d1d", "F": "#450a0a",
}

GRADING_RUBRIC_HTML = """
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:820px;margin-bottom:20px;">
  <details style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px 16px;">
    <summary style="font-weight:700;color:#1e293b;font-size:0.9em;cursor:pointer;list-style:none;display:flex;align-items:center;gap:6px;">
      <span>📊</span> How grades are calculated
    </summary>
    <div style="margin-top:14px;">
      <div style="font-size:0.82em;color:#475569;margin-bottom:12px;">
        Overall score = weighted average of six dimensions × 10. Each dimension scored 0–10 by LLM against Stripe/Plaid benchmark.
      </div>
      <table style="width:100%;border-collapse:collapse;font-size:0.83em;">
        <thead>
          <tr style="background:#f1f5f9;">
            <th style="padding:7px 10px;text-align:left;color:#64748b;font-weight:600;">Grade</th>
            <th style="padding:7px 10px;text-align:left;color:#64748b;font-weight:600;">Score Range</th>
            <th style="padding:7px 10px;text-align:left;color:#64748b;font-weight:600;">What it means</th>
          </tr>
        </thead>
        <tbody>
          <tr style="border-bottom:1px solid #f1f5f9;"><td style="padding:7px 10px;font-weight:800;color:#16a34a;">A</td><td style="padding:7px 10px;color:#334155;">90–100</td><td style="padding:7px 10px;color:#334155;">Stripe-tier. Developer can integrate without leaving the page.</td></tr>
          <tr style="border-bottom:1px solid #f1f5f9;background:#fafafa;"><td style="padding:7px 10px;font-weight:800;color:#22c55e;">A−</td><td style="padding:7px 10px;color:#334155;">85–89</td><td style="padding:7px 10px;color:#334155;">Near-Stripe. One or two minor gaps; still mostly self-serve.</td></tr>
          <tr style="border-bottom:1px solid #f1f5f9;"><td style="padding:7px 10px;font-weight:800;color:#65a30d;">B+</td><td style="padding:7px 10px;color:#334155;">80–84</td><td style="padding:7px 10px;color:#334155;">Solid docs. Developer moves fast but hits occasional friction.</td></tr>
          <tr style="border-bottom:1px solid #f1f5f9;background:#fafafa;"><td style="padding:7px 10px;font-weight:800;color:#ca8a04;">B</td><td style="padding:7px 10px;color:#334155;">75–79</td><td style="padding:7px 10px;color:#334155;">Functional. Some fields, errors, or examples missing.</td></tr>
          <tr style="border-bottom:1px solid #f1f5f9;"><td style="padding:7px 10px;font-weight:800;color:#d97706;">B−</td><td style="padding:7px 10px;color:#334155;">70–74</td><td style="padding:7px 10px;color:#334155;">Workable but rough. Developer will need to guess or experiment.</td></tr>
          <tr style="border-bottom:1px solid #f1f5f9;background:#fafafa;"><td style="padding:7px 10px;font-weight:800;color:#ea580c;">C+</td><td style="padding:7px 10px;color:#334155;">65–69</td><td style="padding:7px 10px;color:#334155;">Below average. Missing key sections; onboarding takes hours.</td></tr>
          <tr style="border-bottom:1px solid #f1f5f9;"><td style="padding:7px 10px;font-weight:800;color:#dc2626;">C</td><td style="padding:7px 10px;color:#334155;">60–64</td><td style="padding:7px 10px;color:#334155;">Significant gaps. Support ticket likely before first successful call.</td></tr>
          <tr style="border-bottom:1px solid #f1f5f9;background:#fafafa;"><td style="padding:7px 10px;font-weight:800;color:#b91c1c;">C−</td><td style="padding:7px 10px;color:#334155;">55–59</td><td style="padding:7px 10px;color:#334155;">Mostly incomplete. Developers will abandon or DM your team.</td></tr>
          <tr style="border-bottom:1px solid #f1f5f9;"><td style="padding:7px 10px;font-weight:800;color:#7f1d1d;">D</td><td style="padding:7px 10px;color:#334155;">50–54</td><td style="padding:7px 10px;color:#334155;">Effectively undocumented for most dimensions.</td></tr>
          <tr style="background:#fafafa;"><td style="padding:7px 10px;font-weight:800;color:#450a0a;">F</td><td style="padding:7px 10px;color:#334155;">&lt; 50</td><td style="padding:7px 10px;color:#334155;">No usable documentation. Do not ship.</td></tr>
        </tbody>
      </table>
      <div style="margin-top:12px;font-size:0.8em;color:#64748b;">
        <b>Dimension weights:</b> Clarity 20% · Completeness 20% · Example Quality 20% · Error Handling 15% · Onboarding Friction 15% · Consistency 10%
      </div>
    </div>
  </details>
</div>
"""

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
          <td colspan="4" style="padding:4px 10px 14px 10px;font-size:0.84em;color:#1e293b;border-bottom:1px solid #e2e8f0;background:#fafafa;">
            <span style="font-weight:700;color:#334155;">Evidence:</span> <span style="color:#334155;">{s['evidence']}</span><br style="margin-bottom:4px;">
            <span style="font-weight:700;color:#0f172a;">Fix:</span> <span style="color:#0f172a;">{s['fix']}</span>
          </td>
        </tr>"""

    strengths_html = "".join(
        f'<div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:8px;">'
        f'<span style="color:#16a34a;font-size:1em;margin-top:1px;">✓</span>'
        f'<span style="color:#166534;font-size:0.88em;line-height:1.4;">{s}</span>'
        f'</div>'
        for s in result.get("top_strengths", [])
    )

    improvements_html = ""
    for imp in result.get("top_improvements", []):
        pri = imp.get("priority", "")
        p_bg   = {"P0": "#fef2f2", "P1": "#fffbeb", "P2": "#f8fafc"}.get(pri, "#f8fafc")
        p_border = {"P0": "#fecaca", "P1": "#fde68a", "P2": "#e2e8f0"}.get(pri, "#e2e8f0")
        p_color  = {"P0": "#dc2626", "P1": "#d97706", "P2": "#64748b"}.get(pri, "#64748b")
        example = imp.get("stripe_bar_example", "")
        example_block = ""
        if example:
            example_block = f"""
            <div style="margin-top:10px;background:#f0f9ff;border:1px solid #bae6fd;border-radius:6px;padding:10px 12px;">
              <div style="font-size:0.7em;font-weight:700;color:#0369a1;letter-spacing:.06em;margin-bottom:6px;">⚡ BENCHMARK EXAMPLE</div>
              <div style="font-size:0.82em;color:#0f172a;line-height:1.5;font-family:'SFMono-Regular',Consolas,monospace;white-space:pre-wrap;">{example}</div>
            </div>"""
        improvements_html += f"""
        <div style="background:{p_bg};border:1px solid {p_border};border-radius:8px;padding:12px 14px;margin-bottom:10px;">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
            <span style="background:{p_color};color:#fff;font-size:0.7em;font-weight:700;padding:2px 8px;border-radius:12px;">{pri}</span>
            <span style="font-weight:600;color:#1e293b;font-size:0.9em;">{imp.get('area','')}</span>
          </div>
          <div style="font-size:0.87em;color:#1e293b;margin-bottom:4px;font-weight:500;">{imp.get('change','')}</div>
          <div style="font-size:0.82em;color:#475569;font-style:italic;">{imp.get('why_it_matters','')}</div>
          {example_block}
        </div>"""

    source_display = source if len(source) < 60 else source[:57] + "..."

    return f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:820px;">

  {GRADING_RUBRIC_HTML}

  <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:20px 24px;margin-bottom:16px;display:flex;align-items:center;gap:24px;">
    <div style="text-align:center;min-width:90px;">
      <div style="font-size:3em;font-weight:800;color:{grade_col};line-height:1;">{grade}</div>
      <div style="font-size:0.75em;color:#9ca3af;margin-top:2px;">Grade</div>
    </div>
    <div>
      <div style="font-size:1.5em;font-weight:700;color:#0f172a;">{overall:.1f} <span style="font-size:0.6em;color:#64748b;">/ 100</span></div>
      <div style="font-size:0.85em;color:#334155;margin-top:4px;word-break:break-all;font-weight:500;">{source_display}</div>
      <div style="font-size:0.84em;color:#475569;margin-top:6px;font-style:italic;">{result.get('summary','')}</div>
    </div>
  </div>

  <div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:0.88em;color:#1c1917;">
    <span style="font-weight:700;color:#92400e;">⚡ Gap vs. industry benchmark: </span><span style="color:#1c1917;">{result.get('stripe_bar_gap','')}</span>
  </div>

  <table style="width:100%;border-collapse:collapse;margin-bottom:20px;">
    <thead>
      <tr style="background:#f1f5f9;">
        <th style="padding:10px 8px;text-align:left;font-size:0.78em;color:#64748b;text-transform:uppercase;letter-spacing:.05em;">Dimension</th>
        <th style="padding:10px 8px;text-align:center;font-size:0.78em;color:#64748b;text-transform:uppercase;">Score</th>
        <th style="padding:10px 8px;font-size:0.78em;color:#64748b;text-transform:uppercase;">Bar</th>
        <th style="padding:10px 8px;font-size:0.78em;color:#64748b;text-transform:uppercase;">Weight</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;margin-bottom:20px;">
    <div style="font-weight:700;color:#166534;font-size:0.95em;margin-bottom:10px;">✅ Top Strengths</div>
    {strengths_html}
  </div>

  <div>
    <div style="font-weight:700;color:#1e293b;font-size:0.95em;margin-bottom:12px;">🔧 Prioritized Improvements</div>
    {improvements_html}
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


LOADING_HTML = """
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:40px 24px;text-align:center;">
  <div style="display:inline-block;margin-bottom:24px;">
    <svg width="48" height="48" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
      <circle cx="24" cy="24" r="20" fill="none" stroke="#e2e8f0" stroke-width="4"/>
      <circle cx="24" cy="24" r="20" fill="none" stroke="#6366f1" stroke-width="4"
        stroke-dasharray="30 95" stroke-linecap="round" transform="rotate(-90 24 24)">
        <animateTransform attributeName="transform" type="rotate"
          from="0 24 24" to="360 24 24" dur="0.9s" repeatCount="indefinite"/>
      </circle>
    </svg>
  </div>
  <div style="font-size:1.1em;font-weight:600;color:#1e293b;margin-bottom:8px;" id="loading-msg">Fetching documentation...</div>
  <div style="font-size:0.85em;color:#94a3b8;">Scoring six DX dimensions against the Stripe bar</div>
  <div style="margin-top:28px;background:#f1f5f9;border-radius:8px;height:8px;width:320px;display:inline-block;overflow:hidden;">
    <div style="height:8px;background:linear-gradient(90deg,#6366f1,#8b5cf6);border-radius:8px;
      animation:progress 2.5s ease-in-out infinite;">
    </div>
  </div>
  <style>
    @keyframes progress {
      0%   { width: 0%;   margin-left: 0%; }
      50%  { width: 60%;  margin-left: 20%; }
      100% { width: 0%;   margin-left: 100%; }
    }
  </style>
</div>
"""

LOADING_HTML_SCORING = LOADING_HTML.replace("Fetching documentation...", "Scoring with LLM...")


def run_single(input_type, url, pasted):
    # Show loader immediately
    yield LOADING_HTML, "", "", ""
    try:
        content, source = _resolve_input(input_type, url, pasted)
        if len(content) < 200:
            yield f"Content too short ({len(content)} chars). Try a different URL or paste more text.", "", "", ""
            return
        yield LOADING_HTML_SCORING, "", "", ""
        result = score_documentation(source, content)
        html = render_scorecard_html(source, result)
        md = format_markdown_report(source, result)
        jira = build_jira_ticket(source, result)
        gh = build_github_issue(source, result)
        yield html, md, jira, gh
    except json.JSONDecodeError as e:
        yield f"Model returned malformed JSON. Retry. ({e})", "", "", ""
    except requests.RequestException as e:
        yield f"Could not fetch URL: {e}", "", "", ""
    except (ValueError, RuntimeError) as e:
        yield str(e), "", "", ""
    except Exception as e:
        err = str(e)
        if "rate_limit_exceeded" in err:
            import re as _re
            wait = _re.search(r'Please try again in ([^.\'\"]+)', err)
            if wait:
                yield f"⏳ Token limit reached. Try again in {wait.group(1).strip()}.", "", "", ""
            elif "Request too large" in err:
                yield "⚠️ This page is too large even for the fallback model. Try pasting a shorter excerpt using 'Paste docs' mode.", "", "", ""
            else:
                yield f"⏳ Token limit reached. Error: {err}", "", "", ""
        else:
            yield f"Unexpected error: {type(e).__name__}: {e}", "", "", ""


def run_compare(url_a, url_b):
    yield LOADING_HTML, ""
    try:
        if not (url_a or "").strip() or not (url_b or "").strip():
            yield "Paste two URLs to compare.", ""
            return
        content_a = fetch_url(url_a.strip())
        content_b = fetch_url(url_b.strip())
        yield LOADING_HTML_SCORING, ""
        res_a = score_documentation(url_a.strip(), content_a)
        res_b = score_documentation(url_b.strip(), content_b)
        html = render_comparison_html(url_a.strip(), res_a, url_b.strip(), res_b)
        md_a = format_markdown_report(url_a.strip(), res_a)
        md_b = format_markdown_report(url_b.strip(), res_b)
        combined_md = f"# Comparison Report\n\n## A: {url_a}\n\n{md_a}\n\n---\n\n## B: {url_b}\n\n{md_b}"
        yield html, combined_md
    except Exception as e:
        yield f"Error: {type(e).__name__}: {e}", ""


# ──────────────────────────────────────────────
# UI
# ──────────────────────────────────────────────

EXAMPLE_URLS = [
    "https://docs.stripe.com/api/charges/create",
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
                show_progress="hidden",
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
                show_progress="hidden",
            )

    gr.Markdown(
        "---\n"
        "_Model: Llama 3.3 70B via Groq (free). "
        "Scores are directional, not absolute. Rubric and weights are open in `prompts.py`._"
    )

if __name__ == "__main__":
    demo.launch()
