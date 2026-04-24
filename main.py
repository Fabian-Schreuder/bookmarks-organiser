from __future__ import annotations

import html
import json
import os
import sys
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from openai import OpenAI

BATCH_SIZE = 15
MODEL = "meta/llama-3.2-3b-instruct"
CATEGORIES = [
    "Technology",
    "Science",
    "News",
    "Entertainment",
    "Finance",
    "Health",
    "Education",
    "Shopping",
    "Social",
    "Work",
    "Tools",
    "Reference",
    "Other",
]
SYSTEM_PROMPT = (
    "You are a bookmark organizer. For each bookmark, suggest a concise name (max 6 words) "
    f"and a category from: {', '.join(CATEGORIES)}. "
    "Return ONLY valid JSON with this exact structure: "
    '{"results": [{"url": "...", "name": "...", "category": "..."}]}'
)


@dataclass
class Bookmark:
    url: str
    title: str
    add_date: str = ""
    icon: str = ""
    original_path: list[str] = field(default_factory=list)
    ai_name: str = ""
    ai_category: str = ""

    def __hash__(self) -> int:
        return hash(self.url)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Bookmark):
            return NotImplemented
        return self.url == other.url


@dataclass
class Folder:
    name: str
    add_date: str = ""
    last_modified: str = ""
    children: list[Folder | Bookmark] = field(default_factory=list)


class BookmarkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.root: Folder | None = None
        self._folder_stack: list[Folder] = []
        self._current_bookmark: dict[str, str] | None = None
        self._in_h3: bool = False
        self._h3_text: str = ""
        self._dl_level: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {k: v or "" for k, v in attrs}

        if tag == "dl":
            self._dl_level += 1
        elif tag == "h3":
            self._in_h3 = True
            self._h3_text = ""
            folder = Folder(
                name="",
                add_date=attrs_dict.get("add_date", ""),
                last_modified=attrs_dict.get("last_modified", ""),
            )
            if self._folder_stack:
                self._folder_stack[-1].children.append(folder)
            self._folder_stack.append(folder)
        elif tag == "a":
            self._current_bookmark = {
                "href": attrs_dict.get("href", ""),
                "add_date": attrs_dict.get("add_date", ""),
                "icon": attrs_dict.get("icon", ""),
                "title": "",
            }

    def handle_endtag(self, tag: str) -> None:
        if tag == "dl":
            self._dl_level -= 1
            if self._folder_stack and self._dl_level >= 0 and len(self._folder_stack) > 1:
                self._folder_stack.pop()
        elif tag == "h3" and self._in_h3:
            self._in_h3 = False
            if self._folder_stack:
                self._folder_stack[-1].name = self._h3_text.strip()
                if self.root is None and self._dl_level == 1:
                    self.root = self._folder_stack[-1]
        elif tag == "a" and self._current_bookmark is not None:
            bm = Bookmark(
                url=self._current_bookmark["href"],
                title=html.unescape(self._current_bookmark["title"]).strip(),
                add_date=self._current_bookmark.get("add_date", ""),
                icon=self._current_bookmark.get("icon", ""),
                original_path=[f.name for f in self._folder_stack[:-1]]
                if len(self._folder_stack) > 1
                else [],
            )
            if self._folder_stack:
                self._folder_stack[-1].children.append(bm)
            self._current_bookmark = None

    def handle_data(self, data: str) -> None:
        if self._in_h3:
            self._h3_text += data
        elif self._current_bookmark is not None:
            self._current_bookmark["title"] += data

    @classmethod
    def parse_file(cls, path: Path) -> Folder:
        parser = cls()
        parser.feed(path.read_text(encoding="utf-8"))
        if parser.root is None:
            parser.root = Folder(name="Bookmarks")
            while parser._folder_stack:
                f = parser._folder_stack.pop(0)
                if f is not parser.root:
                    parser.root.children.append(f)
        return parser.root


def extract_all_bookmarks(folder: Folder) -> list[Bookmark]:
    bookmarks: list[Bookmark] = []

    def _traverse(node: Folder | Bookmark, path: list[str]) -> None:
        if isinstance(node, Bookmark):
            node.original_path = path.copy()
            bookmarks.append(node)
        elif isinstance(node, Folder):
            current_path = path + [node.name] if node.name else path
            for child in node.children:
                _traverse(child, current_path)

    _traverse(folder, [])
    return bookmarks


def deduplicate_bookmarks(bookmarks: list[Bookmark]) -> list[Bookmark]:
    seen: set[str] = set()
    unique: list[Bookmark] = []
    for bm in bookmarks:
        normalized = bm.url.rstrip("/").lower()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(bm)
    return unique


def load_cache(cache_path: Path) -> dict[str, dict[str, str]]:
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    return {}


def save_cache(cache_path: Path, cache: dict[str, dict[str, str]]) -> None:
    cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")


def sanitize_json_output(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def process_batch_with_ai(client: OpenAI, bookmarks: list[Bookmark]) -> dict[str, dict[str, str]]:
    lines = []
    for idx, bm in enumerate(bookmarks, 1):
        safe_title = bm.title.replace("|", "/").replace("\n", " ")
        lines.append(f"{idx}. URL: {bm.url} | Title: {safe_title}")

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "Bookmarks:\n" + "\n".join(lines)},
        ],
        temperature=0.2,
        max_tokens=2048,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content or "{}"
    data = json.loads(sanitize_json_output(raw))

    results: dict[str, dict[str, str]] = {}
    for item in data.get("results", []):
        url = item.get("url", "").rstrip("/").lower()
        if url:
            results[url] = {
                "name": item.get("name", "").strip(),
                "category": item.get("category", "Other").strip(),
            }

    return results


def enrich_bookmarks_with_ai(
    bookmarks: list[Bookmark],
    cache_path: Path,
    client: OpenAI,
) -> None:
    cache = load_cache(cache_path)
    uncached: list[Bookmark] = []

    for bm in bookmarks:
        normalized = bm.url.rstrip("/").lower()
        if normalized in cache:
            bm.ai_name = cache[normalized].get("name", bm.title)
            bm.ai_category = cache[normalized].get("category", "Other")
        else:
            uncached.append(bm)

    if not uncached:
        return

    print(f"AI enrichment needed for {len(uncached)} bookmarks (cached: {len(bookmarks) - len(uncached)})")

    total_batches = (len(uncached) + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(0, len(uncached), BATCH_SIZE):
        batch = uncached[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        print(f"Processing AI batch {batch_num}/{total_batches} ({len(batch)} bookmarks)...")

        try:
            results = process_batch_with_ai(client, batch)
            for bm in batch:
                normalized = bm.url.rstrip("/").lower()
                if normalized in results:
                    bm.ai_name = results[normalized]["name"]
                    bm.ai_category = results[normalized]["category"]
                    cache[normalized] = results[normalized]
                else:
                    bm.ai_name = bm.title
                    bm.ai_category = "Other"
                    cache[normalized] = {"name": bm.title, "category": "Other"}
            save_cache(cache_path, cache)
        except Exception as e:
            print(f"Warning: AI batch {batch_num} failed: {e}")
            for bm in batch:
                bm.ai_name = bm.title
                bm.ai_category = "Other"

        if batch_num < total_batches:
            time.sleep(1.5)


def build_ai_folder_tree(bookmarks: list[Bookmark]) -> Folder:
    root = Folder(name="Bookmarks")
    groups: dict[str, list[Bookmark]] = {}

    for bm in bookmarks:
        cat = bm.ai_category if bm.ai_category else "Other"
        groups.setdefault(cat, []).append(bm)

    for folder_name, items in sorted(groups.items()):
        folder = Folder(name=folder_name)
        for bm in sorted(items, key=lambda x: (x.ai_name or x.title).lower()):
            folder.children.append(bm)
        root.children.append(folder)

    return root


def build_fallback_tree(bookmarks: list[Bookmark]) -> Folder:
    root = Folder(name="Bookmarks")
    groups: dict[str, list[Bookmark]] = {}

    for bm in bookmarks:
        key = bm.original_path[0] if bm.original_path else "Uncategorized"
        groups.setdefault(key, []).append(bm)

    for folder_name, items in sorted(groups.items()):
        folder = Folder(name=folder_name)
        for bm in sorted(items, key=lambda x: x.title.lower()):
            folder.children.append(bm)
        root.children.append(folder)

    return root


def render_html(folder: Folder) -> str:
    lines = [
        "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
        "<!-- This is an automatically generated file. -->",
        '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
        "<TITLE>Bookmarks</TITLE>",
        "<H1>Bookmarks</H1>",
    ]

    def _render(node: Folder | Bookmark, indent: int = 0) -> list[str]:
        pad = "    " * indent
        out: list[str] = []
        if isinstance(node, Folder):
            out.append(
                f'{pad}<DT><H3 ADD_DATE="{node.add_date}" '
                f'LAST_MODIFIED="{node.last_modified}">{html.escape(node.name)}</H3>'
            )
            out.append(f"{pad}<DL><p>")
            for child in node.children:
                out.extend(_render(child, indent + 1))
            out.append(f"{pad}</DL><p>")
        elif isinstance(node, Bookmark):
            icon_attr = f' ICON="{node.icon}"' if node.icon else ""
            add_date_attr = f' ADD_DATE="{node.add_date}"' if node.add_date else ""
            display_title = html.escape(node.ai_name or node.title)
            out.append(
                f'{pad}<DT><A HREF="{html.escape(node.url)}"'
                f'{add_date_attr}{icon_attr}>{display_title}</A>'
            )
        return out

    lines.extend(_render(folder, 0))
    return "\n".join(lines) + "\n"


def get_ai_client() -> OpenAI:
    key = os.environ.get("NVIDIA_API_KEY", "")
    if not key:
        raise RuntimeError("NVIDIA_API_KEY environment variable not set")
    return OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=key)


def process_bookmarks(
    input_path: Path,
    output_path: Path,
    use_ai: bool = True,
    cache_path: Path | None = None,
) -> dict[str, int]:
    root = BookmarkParser.parse_file(input_path)
    all_bms = extract_all_bookmarks(root)
    unique_bms = deduplicate_bookmarks(all_bms)

    if use_ai:
        if cache_path is None:
            cache_path = Path(".bookmark_cache.json")
        client = get_ai_client()
        enrich_bookmarks_with_ai(unique_bms, cache_path, client)
        new_root = build_ai_folder_tree(unique_bms)
    else:
        new_root = build_fallback_tree(unique_bms)

    output_path.write_text(render_html(new_root), encoding="utf-8")
    return {
        "total": len(all_bms),
        "unique": len(unique_bms),
        "duplicates_removed": len(all_bms) - len(unique_bms),
        "folders": len(new_root.children),
    }


if __name__ == "__main__":
    use_ai = True
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]

    if "--no-ai" in flags:
        use_ai = False

    if not args:
        print("Usage: python main.py <input_bookmarks.html> [output_bookmarks.html]")
        print("")
        print("Environment variable required for AI mode:")
        print("  NVIDIA_API_KEY=nvapi-...")
        print("")
        print("Options:")
        print("  --no-ai    Skip AI enrichment, just deduplicate and sort")
        sys.exit(1)

    input_file = Path(args[0])
    output_file = Path(args[1]) if len(args) > 1 else Path("organized_bookmarks.html")

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)

    try:
        stats = process_bookmarks(input_file, output_file, use_ai=use_ai)
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"Processed {stats['total']} bookmarks")
    print(f"Removed {stats['duplicates_removed']} duplicates")
    print(f"Organized into {stats['folders']} folders")
    print(f"Output written to: {output_file}")
