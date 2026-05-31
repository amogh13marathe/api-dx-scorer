# How to push this to HuggingFace

## One-time setup (if not done already)

```bash
# Install git-lfs (required by HuggingFace)
brew install git-lfs
git lfs install

# Clone your HuggingFace Space
git clone https://huggingface.co/spaces/amogh-pm/api-dx-scorer hf-api-dx-scorer
cd hf-api-dx-scorer
```

## Push the updated files

```bash
cd hf-api-dx-scorer

# Copy the 3 files from this folder into the clone
cp /path/to/this/folder/app.py .
cp /path/to/this/folder/prompts.py .
cp /path/to/this/folder/requirements.txt .

git add app.py prompts.py requirements.txt
git commit -m "v2: improved UI, side-by-side compare, Jira/GitHub export"
git push
```

The Space rebuilds automatically on push. Takes ~2 minutes.

## Set your GROQ_API_KEY secret

1. Go to https://huggingface.co/spaces/amogh-pm/api-dx-scorer/settings
2. Scroll to **Variables and secrets**
3. Add secret: Name = `GROQ_API_KEY`, Value = your key from https://console.groq.com
4. Click Save — Space restarts automatically

## What changed in v2

- Fixed Runtime error (Gradio pinned to 4.44.0 — now >=5.0.0)
- Side-by-side comparison tab (score two docs, auto-pick winner)
- Visual HTML scorecard with color-coded bars and prominent letter grade
- Export panel: Markdown report, Jira ticket (wiki markup), GitHub issue (markdown with collapsible sections)
