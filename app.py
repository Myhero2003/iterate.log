"""Iterate.log — Flask application."""
import datetime as dt
import email.utils
import glob
import json
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import markdown
import yaml
from flask import Flask, abort, render_template, send_from_directory

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


# Mapping from social link key to SVG filename in svg/ directory
SOCIAL_SVG_MAP = {
    "github": "github.svg",
    "x": "X.svg",
    "note": "note.svg",
    "instagram": "Instagram.svg",
}


def read_svg_content(svg_filename: str) -> str:
    """Read an SVG file from the static/svg/ directory and return its content.

    Returns empty string if file not found.
    """
    svg_path = BASE_DIR / "static" / "svg" / svg_filename
    if svg_path.is_file():
        with open(svg_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Strip XML declaration if present
        content = re.sub(r'<\?xml[^?]*\?>', '', content).strip()
        return content
    return ""


def extract_social_links(raw_markdown: str) -> list[dict]:
    """Extract known social links from markdown text."""
    matches = re.findall(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", raw_markdown)
    socials: list[dict] = []
    seen = set()

    for label, url in matches:
        lower_url = url.lower()
        if "github.com" in lower_url:
            key = "github"
            name = "GitHub"
        elif "twitter.com" in lower_url or "x.com" in lower_url:
            key = "x"
            name = "X"
        elif "note.com" in lower_url:
            key = "note"
            name = "note"
        elif "instagram.com" in lower_url:
            key = "instagram"
            name = "Instagram"
        else:
            continue

        if key in seen:
            continue
        seen.add(key)

        # Load SVG content for this social link
        svg_file = SOCIAL_SVG_MAP.get(key)
        svg_content = read_svg_content(svg_file) if svg_file else ""

        socials.append(
            {
                "key": key,
                "label": name if not label else label,
                "url": url,
                "icon": key,
                "svg_content": svg_content,
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


# ── External feeds (GitHub / note) ───────────────────────────────────

USER_AGENT = "iterate-log-portfolio"
FETCH_TIMEOUT = 4
FEED_CACHE_TTL = dt.timedelta(hours=1)


def http_get(url: str, accept: str) -> bytes | None:
    """Fetch a URL and return its body, or None when anything goes wrong.

    外部サービスが落ちてもページ全体を壊さないよう、例外は握りつぶす。
    """
    request = urllib.request.Request(
        url,
        headers={"Accept": accept, "User-Agent": USER_AGENT},
    )

    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
            return response.read()
    except (urllib.error.URLError, OSError, TimeoutError):
        return None


def is_cache_fresh(cache: dict) -> bool:
    """Whether a feed cache entry is still within its TTL."""
    fetched_at = cache["fetched_at"]
    return fetched_at is not None and dt.datetime.now() - fetched_at < FEED_CACHE_TTL


# ── GitHub repositories ──────────────────────────────────────────────

GITHUB_USERNAME = "Myhero2003"
GITHUB_URL = f"https://github.com/{GITHUB_USERNAME}"
GITHUB_API_URL = (
    f"https://api.github.com/users/{GITHUB_USERNAME}/repos"
    "?per_page=100&sort=pushed&type=owner"
)
GITHUB_REPO_LIMIT = 6

# profile.md 内のこのコメントを、リポジトリ一覧のHTMLに差し替える
GITHUB_REPOS_PLACEHOLDER = "<!--github-repos-->"

_github_cache: dict = {"fetched_at": None, "repos": []}


def fetch_github_repos() -> list[dict]:
    """Fetch the user's public repositories from the GitHub API.

    非公開リポジトリは取得できない。未認証のAPIは 60リクエスト/時 の制限が
    あるため1時間キャッシュし、取得に失敗したときは前回の結果
    （なければ空リスト）を返してページ自体は壊さない。
    """
    if is_cache_fresh(_github_cache):
        return _github_cache["repos"]

    # 次のリクエストで叩き直さないよう、失敗時も時刻だけは更新する
    _github_cache["fetched_at"] = dt.datetime.now()

    body = http_get(GITHUB_API_URL, "application/vnd.github+json")
    if body is None:
        return _github_cache["repos"]

    try:
        payload = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _github_cache["repos"]

    if not isinstance(payload, list):
        return _github_cache["repos"]

    repos = [
        {
            "name": item.get("name", ""),
            "url": item.get("html_url", ""),
            "description": item.get("description") or "",
            "language": item.get("language") or "",
            "pushed_at": str(item.get("pushed_at", ""))[:10],
        }
        for item in payload
        if isinstance(item, dict) and not item.get("fork") and not item.get("archived")
    ][:GITHUB_REPO_LIMIT]

    _github_cache["repos"] = repos
    return repos


# ── note articles ────────────────────────────────────────────────────

NOTE_USERNAME = "mahiro05_02"
NOTE_URL = f"https://note.com/{NOTE_USERNAME}"
NOTE_RSS_URL = f"{NOTE_URL}/rss"
NOTE_ARTICLE_LIMIT = 3

# profile.md 内のこのコメントを、note記事一覧のHTMLに差し替える
NOTE_ARTICLES_PLACEHOLDER = "<!--note-articles-->"

MEDIA_NS = {"media": "http://search.yahoo.com/mrss/"}

_note_cache: dict = {"fetched_at": None, "articles": []}


def fetch_note_articles() -> list[dict]:
    """Fetch the latest note articles from the author's RSS feed.

    GitHubと同じく1時間キャッシュし、失敗時は前回の結果を返す。
    """
    if is_cache_fresh(_note_cache):
        return _note_cache["articles"]

    _note_cache["fetched_at"] = dt.datetime.now()

    body = http_get(NOTE_RSS_URL, "application/rss+xml, application/xml")
    if body is None:
        return _note_cache["articles"]

    try:
        channel = ET.fromstring(body)
    except ET.ParseError:
        return _note_cache["articles"]

    articles = []
    for item in channel.findall("./channel/item")[:NOTE_ARTICLE_LIMIT]:
        thumbnail = item.find("media:thumbnail", MEDIA_NS)
        articles.append(
            {
                "title": item.findtext("title", default=""),
                "url": item.findtext("link", default=""),
                "date": format_rss_date(item.findtext("pubDate")),
                "thumbnail": thumbnail.text if thumbnail is not None else "",
            }
        )

    _note_cache["articles"] = articles
    return articles


def format_rss_date(raw: str | None) -> str:
    """Convert an RFC 822 pubDate (e.g. 'Sun, 05 Jul 2026 21:11:43 +0900') to YYYY-MM-DD."""
    if not raw:
        return ""

    try:
        return email.utils.parsedate_to_datetime(raw).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


# ── Growth chart ─────────────────────────────────────────────────────

# condition（体調・メンタル）は個人的な指標なので、既定では公開しない。
# 手元で推移を確認したいときは True にする。
SHOW_CONDITION = False

# 折れ線グラフの描画領域（SVGのviewBox基準）
CHART_WIDTH = 680
CHART_HEIGHT = 200
CHART_PAD_LEFT = 28
CHART_PAD_RIGHT = 16
CHART_PAD_TOP = 16
CHART_PAD_BOTTOM = 32

SCORE_MIN = 1
SCORE_MAX = 5


def monthly_sort_key(entry: dict) -> tuple[int, int]:
    """Derive (year, month) from a monthly entry's filename.

    月次ファイルの date は「4月の振り返りを5月1日に書いた」のようにズレることが
    あるため、iterate-YYYY-MM.md というファイル名の方を月の正としている。
    """
    match = re.search(r"(\d{4})-(\d{2})", entry.get("filename", ""))
    if match:
        return int(match.group(1)), int(match.group(2))

    fallback = to_date_sort_key(entry.get("date"))
    return fallback.year, fallback.month


def score_to_y(value: float) -> float:
    """Map a 1-5 score to a Y coordinate inside the chart area."""
    plot_height = CHART_HEIGHT - CHART_PAD_TOP - CHART_PAD_BOTTOM
    ratio = (value - SCORE_MIN) / (SCORE_MAX - SCORE_MIN)
    return CHART_PAD_TOP + (1 - ratio) * plot_height


def build_growth_chart(entries: list[dict]) -> dict | None:
    """Build coordinates for the career_growth / condition line chart.

    Returns None when there are fewer than two months of data
    (a single point makes no line worth drawing).
    """
    months = [e for e in entries if e.get("type") == "monthly"]
    months.sort(key=monthly_sort_key)

    if len(months) < 2:
        return None

    plot_width = CHART_WIDTH - CHART_PAD_LEFT - CHART_PAD_RIGHT
    step = plot_width / (len(months) - 1)
    xs = [CHART_PAD_LEFT + step * i for i in range(len(months))]

    series_defs = [("career_growth", "成長実感", "growth")]
    if SHOW_CONDITION:
        series_defs.append(("condition", "コンディション", "condition"))

    series = []
    for key, label, modifier in series_defs:
        points = []
        for x, entry in zip(xs, months):
            value = entry.get(key)
            if value is None:
                continue
            points.append(
                {
                    "x": round(x, 1),
                    "y": round(score_to_y(float(value)), 1),
                    "value": value,
                }
            )

        if len(points) < 2:
            continue

        series.append(
            {
                "key": key,
                "label": label,
                "modifier": modifier,
                "polyline": " ".join(f"{p['x']},{p['y']}" for p in points),
                "points": points,
            }
        )

    if not series:
        return None

    labels = [
        {"x": round(x, 1), "text": f"{monthly_sort_key(entry)[1]}月"}
        for x, entry in zip(xs, months)
    ]

    gridlines = [
        {"y": round(score_to_y(value), 1), "value": value}
        for value in range(SCORE_MIN, SCORE_MAX + 1)
    ]

    return {
        "width": CHART_WIDTH,
        "height": CHART_HEIGHT,
        "label_y": CHART_HEIGHT - CHART_PAD_BOTTOM + 20,
        "axis_x": CHART_PAD_LEFT - 10,
        "plot_left": CHART_PAD_LEFT,
        "plot_right": CHART_WIDTH - CHART_PAD_RIGHT,
        "series": series,
        "labels": labels,
        "gridlines": gridlines,
        "months": len(months),
    }


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

        svg_file = meta.get("thumbnail_svg")
        svg_content = read_svg_content(svg_file) if svg_file else ""

        entry = {
            "id": file_name,
            "title": meta.get("title") or file_name.replace("-", " ").title(),
            "period": meta.get("period", ""),
            "tags": meta.get("tags", []),
            "summary": meta.get("summary", ""),
            "thumbnail_emoji": meta.get("thumbnail_emoji", "📁"),
            "thumbnail_svg_content": svg_content,
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
    chart = build_growth_chart(entries)
    return render_template("index.html", entries=entries, chart=chart)


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

    # 本文中のプレースホルダを、外部から取得した一覧に差し替える
    if GITHUB_REPOS_PLACEHOLDER in content_html:
        repos_html = render_template(
            "_github_repos.html",
            repos=fetch_github_repos(),
            github_url=GITHUB_URL,
        )
        content_html = content_html.replace(GITHUB_REPOS_PLACEHOLDER, repos_html)

    if NOTE_ARTICLES_PLACEHOLDER in content_html:
        note_html = render_template(
            "_note_articles.html",
            articles=fetch_note_articles(),
            note_url=NOTE_URL,
        )
        content_html = content_html.replace(NOTE_ARTICLES_PLACEHOLDER, note_html)

    # Load inline SVG content for identity items
    identity = meta.get("identity", [])
    for item in identity:
        svg_file = item.get("svg")
        if svg_file:
            item["svg_content"] = read_svg_content(svg_file)
        else:
            item["svg_content"] = ""

    # Load inline SVG content for skill icons
    skills = meta.get("skills", [])
    for category in skills:
        for item in category.get("items", []):
            svg_file = item.get("svg")
            if svg_file:
                item["svg_content"] = read_svg_content(svg_file)
            else:
                item["svg_content"] = ""

    return render_template(
        "profile.html",
        content=content_html,
        profile_title=meta.get("title", "Profile"),
        tagline=meta.get("tagline", ""),
        social_links=social_links,
        timeline=meta.get("timeline", []),
        identity=identity,
        skills=skills,
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


# Serve prototype files (so iframe at /prototypes/... works in dev)
@app.route('/prototypes/<path:filename>')
def prototypes_files(filename: str):
    prototypes_dir = str(BASE_DIR / 'prototypes')
    return send_from_directory(prototypes_dir, filename)


# ── Local development ───────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
