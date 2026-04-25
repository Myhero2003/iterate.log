# Iterate.log

Flask + Markdown で構築した、日々の学びを記録するポートフォリオサイトです。  
`daily` と `monthly` の記録をまとめて一覧表示し、各記事を詳細ページで読めます。  
Vercel へのデプロイを前提にしたシンプルな構成です。

## Features

- `/`  
  `reflections/daily/` と `reflections/monthly/` の Markdown を読み込み、Front Matter（title/date/category など）を取得して日付降順で表示
- `/log/<type>/<filename>`  
  記事本文を Markdown から HTML に変換して表示
- `/profile`  
  `content/profile.md` を表示し、GitHub / X / note のリンクをSNSボタンとして上部に表示
- デザイン  
  `DESIGN.md` の仕様（色・フォント・角丸・幾何学トーン）に準拠

## Tech Stack

- Python 3
- Flask
- python-markdown
- PyYAML
- Vercel Serverless Functions (`api/index.py`)

## Directory Structure

```text
iterate.log/
├── api/
│   └── index.py
├── content/
│   └── profile.md
├── reflections/
│   ├── daily/
│   │   └── *.md
│   └── monthly/
│       └── *.md
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── detail.html
│   └── profile.html
├── app.py
├── requirements.txt
└── vercel.json
```

## Markdown Format (Front Matter)

日次・月次ともに、先頭に YAML Front Matter を置きます。

### Daily Example

```md
---
title: "2026-04-25 学習ログ"
date: "2026-04-25"
category: "Python"
study_hours: 2.5
tags:
  - Flask
  - Vercel
---

本文...
```

### Monthly Example

```md
---
title: "2026-04 月次振り返り"
date: "2026-04"
category: "Monthly Review"
condition: 4
career_growth: 3
tags:
  - Reflection
---

本文...
```

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

アクセス先:

- Home: <http://127.0.0.1:5000/>
- Detail: `http://127.0.0.1:5000/log/daily/<filename>`
- Profile: <http://127.0.0.1:5000/profile>

## Deploy on Vercel

このプロジェクトは `vercel.json` で全ルートを `api/index.py` にルーティングします。

- Build: `@vercel/python`
- Entry point: `api/index.py`
- Flask app: `app.py` の `app`

Vercel CLI 例:

```bash
vercel
```

## Notes

- `date` は `YYYY-MM-DD` / `YYYY-MM` / `YYYY/MM/DD` / `YYYY.MM.DD` をサポート
- `date` がない記事は一覧の末尾に並びます
- `filename` は `/log/<type>/<filename>` で直接参照されるため、重複しない命名を推奨します
