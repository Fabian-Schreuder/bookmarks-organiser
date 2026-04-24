# Bookmarks Organiser

A Python tool that parses Netscape bookmark files, removes duplicates, and uses AI to auto-categorize bookmarks and generate clean, logical names. Supports both **local Ollama** and **NVIDIA NIM cloud**.

## Features

- **Parse** Netscape Bookmark HTML files (Chrome, Firefox, Edge export format)
- **Remove duplicates** by URL (keeps the first occurrence)
- **AI-powered naming** via local Ollama or NVIDIA NIM (free tier)
- **Auto-categorization** into logical folders (Technology, Science, Work, Education, etc.)
- **Cost-effective batching** — processes 15 bookmarks per API call with local caching
- **Rate limit compliance** — stays within NVIDIA NIM's 40 RPM free tier limit

## Setup

1. Install dependencies:
```bash
uv sync
```

2. Choose your AI provider:

### Option A: Local Ollama (recommended — no API keys, no timeouts)

1. [Install Ollama](https://ollama.com/download)
2. Pull a model (default is `llama3.2:3b`):
   ```bash
   ollama pull llama3.2:3b
   ```
3. Set the environment variable:
   ```bash
   export OLLAMA_HOST=http://localhost:11434
   ```

   Optional: override the model:
   ```bash
   export OLLAMA_MODEL=llama3.2:3b
   ```

### Option B: NVIDIA NIM (cloud)

1. Go to [build.nvidia.com](https://build.nvidia.com)
2. Sign up for the free NVIDIA Developer Program
3. Generate an API key
4. Set the environment variable:
   ```bash
   export NVIDIA_API_KEY=nvapi-xxxxxxxx
   ```

## Usage

### Full AI mode (recommended)
Generates logical names and auto-categorizes bookmarks into folders:

```bash
uv run python main.py bookmarks.html organized_bookmarks.html
```

### Without AI
Just deduplicates and sorts by original folder structure:

```bash
uv run python main.py bookmarks.html organized_bookmarks.html --no-ai
```

## How it works

1. **Parse** — Reads the Netscape bookmarks HTML and extracts all URLs, titles, and folder paths
2. **Deduplicate** — Removes exact URL duplicates (case-insensitive, trailing-slash normalized)
3. **AI Enrichment** (if enabled):
   - Sends bookmarks to Ollama or NVIDIA NIM in batches of 15
   - Each bookmark gets a concise name and a category
   - Results are cached in `.bookmark_cache.json` so re-runs are free
   - Respects the 40 requests/minute rate limit when using NVIDIA NIM
4. **Rebuild** — Outputs a clean Netscape bookmarks HTML file organized into folders

## AI Model

- **Ollama**: Defaults to `llama3.2:3b` — fast, local, no rate limits
- **NVIDIA NIM**: Uses `meta/llama-3.2-3b-instruct` on the free tier

## Categories

Bookmarks are organized into these AI-generated folders:

- Technology
- Science
- News
- Entertainment
- Finance
- Health
- Education
- Shopping
- Social
- Work
- Tools
- Reference
- Other
