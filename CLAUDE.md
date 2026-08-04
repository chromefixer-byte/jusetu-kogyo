# CLAUDE.md

## プロジェクト概要

建設業向けRAGシステムのポートフォリオプロジェクト。
公共建築工事標準仕様書（電気設備工事編）令和7年版を対象とした、CLI型のRAG検索ツール。

## 作業指示

docs/instructions/instructions-v1.md を読んでから着工すること。

## リポジトリ構成

```
src/extract/   PDF抽出（plumber, pymupdf, arbiter）
src/chunker.py チャンク分割
src/ingest.py  埋め込み・Chroma格納
src/query.py   検索・回答生成
eval/          評価（questions.jsonl, run_eval.py）
docs/          仕様書・指示書
data/raw/      素材PDF（.gitignore）
```

## 環境

- Python 3.10+
- OPENROUTER_API_KEY 環境変数必須（OpenRouter経由でLLM生成）
- GPU不要（ruri-v3-310mはCPUで動作可能）

## 素材PDF

data/raw/ に以下を配置:
https://www.mlit.go.jp/gobuild/content/001888825.pdf

## 運用規律

- 難航時はdocs/reports/にpushしてPMへ差し戻す
- 環境問題は発注者に直接聞いてよい
- eval/questions.jsonlは改変しない（PM支給物）
