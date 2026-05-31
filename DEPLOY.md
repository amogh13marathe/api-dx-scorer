# Deployment Guide

Two targets: **Hugging Face Spaces** (live demo) and **GitHub** (code + case study). Do both. They cross-link.

Total time: ~15 minutes.

---

## 0. Prerequisites (one-time)

1. **Groq API key** — free at https://console.groq.com → "API Keys" → "Create API Key". Copy it. Llama 3.3 70B is on the free tier; rate limit is 30 req/min, which is more than enough for a demo.
2. **Hugging Face account** — free at https://huggingface.co/join.
3. **GitHub account** — already have one.

---

## 1. Push to GitHub

```bash
cd "/Users/amoghmarathe/Claude-Projects/Product Manager Job hunt/api-dx-scorer"

git init
git add .
git commit -m "Initial commit: API DX Scorecard"

# Create the repo on github.com first, then:
git remote add origin git@github.com:<your-github-username>/api-dx-scorer.git
git branch -M main
git push -u origin main
```

After pushing, edit `README.md` and `app.py` to replace `<your-handle>` and the placeholder URLs with your actual GitHub handle and the Hugging Face Space URL (you'll have that after step 2).

---

## 2. Deploy to Hugging Face Spaces

1. Go to https://huggingface.co/new-space
2. Fill in:
   - **Owner:** your username
   - **Space name:** `api-dx-scorer`
   - **License:** MIT
   - **SDK:** Gradio
   - **Hardware:** CPU basic (free)
   - **Visibility:** Public
3. Click **Create Space**.

HF gives you a git URL like `https://huggingface.co/spaces/<your-handle>/api-dx-scorer`.

Push this folder to it:

```bash
cd "/Users/amoghmarathe/Claude-Projects/Product Manager Job hunt/api-dx-scorer"

git remote add hf https://huggingface.co/spaces/<your-handle>/api-dx-scorer
git push hf main
```

(If `main` doesn't exist on the HF remote yet, use `git push --set-upstream hf main`.)

---

## 3. Add the Groq API key as a Space secret

1. Open your Space on huggingface.co.
2. Go to **Settings** → **Variables and secrets**.
3. Click **New secret**.
4. **Name:** `GROQ_API_KEY`
5. **Value:** your key from step 0.
6. Save.

The Space will rebuild automatically. You'll see a build log in the **Logs** tab. After ~60 seconds, the demo is live at:

`https://huggingface.co/spaces/<your-handle>/api-dx-scorer`

---

## 4. Cross-link

In your GitHub `README.md`, replace the placeholder Live demo row with the Space URL.
In your Hugging Face Space (Settings → README), add a "Code on GitHub" link to the repo.

---

## 5. Add to your portfolio / personal site

Paste this snippet wherever:

```html
<a href="https://huggingface.co/spaces/<your-handle>/api-dx-scorer">
  API DX Scorecard — live demo
</a>
·
<a href="https://github.com/<your-handle>/api-dx-scorer">
  Code & case study
</a>
```

Or in Markdown for LinkedIn featured section:

> **API DX Scorecard** — a PM tool that grades API documentation against the bar set by Stripe, Plaid, and Twilio. Six-dimension weighted rubric, prioritized fixes, deployed as a free public tool. [Live demo](https://huggingface.co/spaces/<your-handle>/api-dx-scorer) · [Case study](https://github.com/<your-handle>/api-dx-scorer)

---

## Troubleshooting

**"GROQ_API_KEY is not set"** — The secret is missing or the Space hasn't rebuilt since you added it. Open Settings → Factory rebuild.

**"Build failed: gradio==4.44.0 not found"** — HF sometimes lags on Gradio versions. Try `gradio>=4.40,<5` in `requirements.txt`.

**"Could not fetch URL"** — Some docs sites (Stripe, Plaid) JS-render. Use the **Paste docs** mode instead.

**"Module 'lxml' not found"** — Add `lxml` to `requirements.txt` (already there) and rebuild.
