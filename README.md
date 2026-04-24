# Bookmarks Organiser

A Python tool that parses Netscape bookmark files, removes duplicates, and uses NVIDIA NIM's free AI API to auto-categorize bookmarks and generate clean, logical names.

## Features

- **Parse** Netscape Bookmark HTML files (Chrome, Firefox, Edge export format)
- **Remove duplicates** by URL (keeps the first occurrence)
- **AI-powered naming** via NVIDIA NIM (free tier)
- **Auto-categorization** into logical folders (Technology, Science, Work, Education, etc.)
- **Cost-effective batching** — processes 15 bookmarks per API call with local caching
- **Rate limit compliance** — stays within NVIDIA NIM's 40 RPM free tier limit

## Setup

1. Install dependencies:
```bash
uv sync
```

2. Get a free NVIDIA API key:
   - Go to [build.nvidia.com](https://build.nvidia.com)
   - Sign up for the free NVIDIA Developer Program
   - Generate an API key

3. Set the environment variable:
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
   - Sends bookmarks to NVIDIA NIM in batches of 15
   - Each bookmark gets a concise name and a category
   - Results are cached in `.bookmark_cache.json` so re-runs are free
   - Respects the 40 requests/minute rate limit with 1.5s delays between batches
4. **Rebuild** — Outputs a clean Netscape bookmarks HTML file organized into folders

## AI Model

Uses `meta/llama-3.2-3b-instruct` on NVIDIA NIM's free tier — fast, lightweight, and good enough for naming/categorization tasks.

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
