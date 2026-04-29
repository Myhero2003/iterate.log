# Iterate.log

Flask + Markdown で構築した、日々の学びを記録するポートフォリオサイトです。  
`daily` と `monthly` の記録をまとめて一覧表示し、各記事を詳細ページで読めます。  
Vercel へのデプロイを前提にしたシンプルな構成です。

## Features

- `/`  
  `reflections/daily/` と `reflections/monthly/` の Markdown を読み込み、Front Matter（title/date/category など）を取得して日付降順で表示
- `/works`  
  `works/` ディレクトリ内のプロジェクト一覧をカード形式で表示。ホバー時の浮き上がり演出付き
- `/works/<id>`  
  プロジェクトの詳細情報を表示。3D作品やゲーム制作などの実績を紹介
- `/profile`  
  `content/profile.md` の YAML Front Matter からライフパス（タイムライン）、アイデンティティ（強み）、スキルセットを抽出し、洗練されたUIで表示
- デザイン切替 (Theme Switcher)  
  ナビゲーションバーのトグルボタンで、2つの異なるデザインを即座に切り替え可能
  - **Sharp (Default)**: `DESIGN.md` 準拠。Inter フォント、角丸 0px、Slate カラーのプロフェッショナルな外観
  - **Dark**: `DESIGN２.md` 準拠。黒背景にネオンイエローのアクセント、ハイコントラストなサイバーパンク・スタイル
- YouTube & WebGL 対応  
  実績詳細ページでの紹介動画埋め込みや、WebGL化された成果物の解説に対応

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
├── works/
│   └── *.md
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
│   ├── profile.html
│   ├── works.html
│   └── works_detail.html
├── app.py
├── requirements.txt
├── vercel.json
├── DESIGN.md     (Sharpデザイン定義)
└── DESIGN２.md    (Darkデザイン定義)
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

### Works Example

`/works/` 内に配置します。`order` で表示順を制御できます。

```md
---
title: "卒業研究: 3Dポートフォリオ"
period: "2025年4月 — 2026年2月"
tags: ["Unity", "Firebase"]
summary: "バーチャル空間で成果物を閲覧できるシステム。"
thumbnail_emoji: "🎓"
order: 1
---

## 📽️ 紹介映像
(YouTube iframe...)

## 🚀 卒業後の展開
(WebGL化の記録など...)

本文...
```

### Profile (Structured Data)

`content/profile.md` の Front Matter でリッチなコンテンツを管理します。

```yaml
---
timeline:
  - year: 2026
    event: "エンジニアデビュー"
identity:
  - title: "強み"
    description: "手を動かして学ぶスタイル"
    icon: "🔨"
skills:
  - category: "言語"
    items:
      - name: "Python"
        icon: "🐍"
---
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
- Works: <http://127.0.0.1:5000/works>
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
