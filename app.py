"""Iterate.log — Flask application."""
import datetime as dt
import glob
import os
import re
from pathlib import Path

import markdown
import yaml
from flask import Flask, abort, render_template

app = Flask(__name__)

# ── Paths ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent
CONTENT_DIR = BASE_DIR / "content"
REFLECTIONS_DIR = BASE_DIR / "reflections"
WORKS_DIR = BASE_DIR / "works"


# ── Helpers ──────────────────────────────────────────────────────────

def parse_frontmatter(raw: str) -> tuple[dict, str]:
    """Split YAML front-matter and body from a Markdown string.

    Returns (metadata_dict, body_markdown).
    """
    meta: dict = {}
    body = raw

    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2]

    return meta, body


def load_markdown_html(raw_body: str) -> str:
    """Convert Markdown body text to HTML."""
    return markdown.markdown(raw_body, extensions=["extra"])


def load_content_markdown(filename: str) -> str:
    """Read a Markdown file from the content directory and convert to HTML.

    Uses the 'extra' extension for tables, fenced code blocks, footnotes, etc.
    """
    filepath = CONTENT_DIR / filename
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    _meta, body = parse_frontmatter(raw)
    return load_markdown_html(body)


def extract_social_links(raw_markdown: str) -> list[dict]:
    """Extract known social links from markdown text."""
    matches = re.findall(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", raw_markdown)
    socials: list[dict] = []
    seen = set()

    for label, url in matches:
        lower_url = url.lower()
        if "github.com" in lower_url:
            key = "github"
            icon = "github"
            name = "GitHub"
        elif "twitter.com" in lower_url or "x.com" in lower_url:
            key = "x"
            icon = "x"
            name = "X"
        elif "note.com" in lower_url:
            key = "note"
            icon = "note"
            name = "note"
        else:
            continue

        if key in seen:
            continue
        seen.add(key)

        socials.append(
            {
                "key": key,
                "label": name if not label else label,
                "url": url,
                "icon": icon,
            }
        )

    return socials


def to_date_sort_key(value: object) -> dt.datetime:
    """Convert front-matter date value to datetime for sorting."""
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)

    raw = str(value or "").strip()
    if not raw:
        return dt.datetime.min

    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return dt.datetime.strptime(raw, fmt)
        except ValueError:
            continue

    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return dt.datetime.min


def collect_reflections() -> list[dict]:
    """Scan reflections/daily and reflections/monthly directories.

    Returns a list of dicts sorted by date descending.
    Each dict contains: title, date, category, study_hours, tags,
    type (daily|monthly), filename, and any other front-matter fields.
    """
    entries: list[dict] = []

    for entry_type in ("daily", "monthly"):
        dir_path = REFLECTIONS_DIR / entry_type
        if not dir_path.is_dir():
            continue

        for filepath in glob.glob(str(dir_path / "*.md")):
            with open(filepath, "r", encoding="utf-8") as f:
                raw = f.read()

            meta, _body = parse_frontmatter(raw)
            file_name = Path(filepath).name

            entry = {
                "title": meta.get("title") or file_name.replace(".md", ""),
                "date": str(meta.get("date", "")),
                "category": meta.get("category", "Monthly") if entry_type == "monthly" else meta.get("category", "Daily"),
                "study_hours": meta.get("study_hours"),
                "condition": meta.get("condition"),
                "career_growth": meta.get("career_growth"),
                "tags": meta.get("tags", []),
                "type": entry_type,
                "filename": file_name,
                "_sort_key": to_date_sort_key(meta.get("date")),
            }
            entries.append(entry)

    # Sort by date descending
    entries.sort(key=lambda e: e["_sort_key"], reverse=True)
    for item in entries:
        item.pop("_sort_key", None)
    return entries


def collect_works() -> list[dict]:
    """Scan works/ directory for project Markdown files.

    Returns a list of dicts sorted by the 'order' front-matter field.
    Each dict contains: id, title, period, tags, summary,
    thumbnail_emoji, and order.
    """
    entries: list[dict] = []

    if not WORKS_DIR.is_dir():
        return entries

    for filepath in glob.glob(str(WORKS_DIR / "*.md")):
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()

        meta, _body = parse_frontmatter(raw)
        file_name = Path(filepath).stem  # e.g. 'graduation-research'

        entry = {
            "id": file_name,
            "title": meta.get("title") or file_name.replace("-", " ").title(),
            "period": meta.get("period", ""),
            "tags": meta.get("tags", []),
            "summary": meta.get("summary", ""),
            "thumbnail_emoji": meta.get("thumbnail_emoji", "📁"),
            "order": meta.get("order", 999),
        }
        entries.append(entry)

    entries.sort(key=lambda e: e["order"])
    return entries


# ── Routes ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Landing page — shows all reflections as a clean news-style list."""
    entries = collect_reflections()
    return render_template("index.html", entries=entries)


@app.route("/log/<entry_type>/<filename>")
def log_detail(entry_type: str, filename: str):
    """Detail page — render a single reflection Markdown as HTML."""
    if entry_type not in ("daily", "monthly"):
        abort(404)

    if "/" in filename or filename.startswith("."):
        abort(404)

    filepath = REFLECTIONS_DIR / entry_type / filename
    if not filepath.is_file():
        abort(404)

    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    meta, body = parse_frontmatter(raw)
    content_html = load_markdown_html(body)

    return render_template(
        "detail.html",
        meta=meta,
        content=content_html,
        entry_type=entry_type,
    )


@app.route("/profile")
def profile():
    """Profile page — renders content/profile.md as HTML with structured data."""
    filepath = CONTENT_DIR / "profile.md"
    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    meta, body = parse_frontmatter(raw)
    content_html = load_markdown_html(body)
    social_links = extract_social_links(raw)

    return render_template(
        "profile.html",
        content=content_html,
        profile_title=meta.get("title", "Profile"),
        tagline=meta.get("tagline", ""),
        social_links=social_links,
        timeline=meta.get("timeline", []),
        identity=meta.get("identity", []),
        skills=meta.get("skills", []),
    )


@app.route("/works")
def works_index():
    """Works page — shows all projects as cards."""
    projects = collect_works()
    return render_template("works.html", projects=projects)


@app.route("/works/<work_id>")
def works_detail(work_id: str):
    """Works detail page — render a single project Markdown as HTML."""
    if "/" in work_id or work_id.startswith("."):
        abort(404)

    filepath = WORKS_DIR / f"{work_id}.md"
    if not filepath.is_file():
        abort(404)

    with open(filepath, "r", encoding="utf-8") as f:
        raw = f.read()

    meta, body = parse_frontmatter(raw)
    content_html = load_markdown_html(body)

    return render_template(
        "works_detail.html",
        meta=meta,
        content=content_html,
        work_id=work_id,
    )


# ── Local development ───────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
