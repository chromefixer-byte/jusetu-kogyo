# jusetu-kogyo

建設業向けRAGシステム — 公共建築工事標準仕様書（電気設備工事編）を対象としたケーススタディ

## 概要

設備管理業務で使われる仕様書PDFに対し、条文構造を活かしたチャンク分割・ベクトル検索・出典付き回答を行うCLI型RAGツール。

設計判断の過程（採用理由・棄却理由・失敗分析）をREADMEに記録し、ポートフォリオとして公開する。

## 技術構成

| 工程 | 採用 |
|---|---|
| PDF抽出 | pdfplumber + PyMuPDF 突合 |
| チャンク分割 | 条番号正規表現（ドメイン知識ベース） |
| フレームワーク | LlamaIndex |
| ベクトルDB | Chroma |
| 埋め込み | ruri-v3-310m |
| 生成 | Claude API |

## セットアップ

```bash
pip install -r requirements.txt
```

## 使い方

```bash
# 1. PDFを data/raw/ に配置
# 2. ingest
python src/ingest.py

# 3. query
python src/query.py "分電盤の保護等級は？"
```

## 評価

```bash
python eval/run_eval.py
```

## ライセンス

MIT
