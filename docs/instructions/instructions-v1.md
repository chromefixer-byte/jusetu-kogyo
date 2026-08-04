# jusetu-kogyo 作業指示書 v1

作成日: 2026-08-04 ／ PM: クリーデ ／ 対応仕様: docs/spec-v0.1.md
位置づけ: 本書一枚でv1の全指示が完結する

## 添付マニフェスト（着工前照合）

以下がリポジトリに存在すること。欠けたら着工せずPMに報告。

| # | パス | 種別 |
|---|---|---|
| 1 | docs/spec-v0.1.md | 仕様書 |
| 2 | docs/requirements-v0.3.md | 要件定義 |
| 3 | docs/data-definition-v0.2.md | データ定義 |
| 4 | eval/questions.jsonl | 評価質問（PM支給・10問） |

## PG運用規律

1. 難航時はPMへ差し戻す（docs/reports/にpush）
2. 環境・インフラの問題は発注者に直接聞いてよい
3. 支給物（questions.jsonl）は改変しない
4. 着工前に `git pull` してマニフェスト照合

## 作業範囲

- **何を**: 公共建築工事標準仕様書（電気設備工事編）を対象としたCLI型RAGツールのv1全体
- **なぜ**: 副業参入用ポートフォリオ（設計判断の展示）
- **どこで**: chromefixer-byte/jusetu-kogyo

## 素材

- PDFのURL: https://www.mlit.go.jp/gobuild/content/001888825.pdf
- data/raw/ にダウンロードして配置（.gitignoreで除外済み）

## 技術情報（PM調査済み）

### PDF条文構造

```
第N編 > 第M章 > 第K節 > X.Y.Z 条名
  (1) 項
    (ｱ) 号（全角カタカナ括弧）
      (a) 細目
```

条番号パターン: `\d+\.\d+\.\d+`
見出しパターン: `第\d+編`, `第\d+章`, `第\d+節`

### hierarchyフィールドの構築

条文の場合、hierarchyは上位の編・章・節を結合して構築する。
例: `第2編/第1章/第3節/1.3.1` → 第2編 電力設備工事 > 第1章 機材 > 第3節 配線器具 > 1.3.1 配線器具

### チャンク分割の単位

- 原則: 条（X.Y.Z）単位で1チャンク
- headingは条名（例: `1.1.1 適用`）
- bodyは条の本文（項・号・細目を含む全テキスト）
- 表はMarkdown表としてbodyに含める。整形不能なら「表あり・p.XX参照」
- 閾値: 300字未満→親節でまとめ、2,000字超→項単位で分割（仮置き・実物で調整）

### ruri-v3-310m プレフィックス

HuggingFaceのモデルカード（cl-nagoya/ruri-v3-310m）を正として照合すること。
文書側・クエリ側のプレフィックスが異なる場合があるため、付け忘れ防止のユニットテストを必ず書く。

### LLM生成（OpenRouter経由）

- 環境変数: `OPENROUTER_API_KEY`
- ベースURL: `https://openrouter.ai/api/v1`
- モデル: `anthropic/claude-haiku-4.5`（既存クレジット内・追加課金なし）
- ライブラリ: `openai`（OpenAI互換API）
- プロンプト要件: 「出典の章・条番号を必ず明示、根拠がなければ『該当なし』と答える」
- 設計判断: Anthropic直接APIではなくOpenRouterを採用した理由をREADMEに記載すること（コスト選択性の展示）

## 作業手順

### Step 1: プロジェクト初期構成

仕様書§2のファイル構成に従い、ディレクトリとrequirements.txtを作成。

```
src/extract/plumber.py, pymupdf_ext.py, arbiter.py
src/chunker.py, ingest.py, query.py
eval/run_eval.py
data/raw/  （.gitkeep）
```

requirements.txtの主要パッケージ:
- pdfplumber, PyMuPDF (pymupdf)
- llama-index, chromadb
- sentence-transformers (ruri-v3-310mの実行用)
- openai（OpenRouter互換クライアント）

### Step 2: extract（突合抽出）

1. `plumber.py`: pdfplumberでPDFからテキスト抽出。ページ単位で返す
2. `pymupdf_ext.py`: PyMuPDFで同じPDFからテキスト抽出。ページ単位で返す
3. `arbiter.py`: 同一ページの2エンジン結果を比較し、判定基準（文字化け率＋行断片化度）で最良結果を採用。採用エンジンと理由をログに残す

### Step 3: chunker

1. 条番号正規表現でテキストを条単位に分割
2. 上位階層（編・章・節）の見出しを追跡してhierarchyを構築
3. 閾値ルール（300字/2,000字）で統合・分割
4. 出力: 中間JSONL（data/chunks.jsonl）。Chroma投入前に目視検査可能にする
5. 各チャンクにchar_count, source_engine, pagesフィールドを付与

### Step 4: ingest

1. ruri-v3-310mで埋め込み（heading+body連結、プレフィックス付与）
2. Chromaに格納（collection名: jusetu_spec）
3. metadata: chunk_id, hierarchy, pages, source_engine, doc_type="spec"

### Step 5: query

1. 質問を受け取り、ruri-v3-310mで埋め込み（クエリ側プレフィックス）
2. Chromaから上位k=3件を検索
3. OpenRouter経由でLLM回答生成（出典必須プロンプト）
4. 回答と出典を表示

### Step 6: eval

1. questions.jsonlを読み込み
2. 各質問に対してqueryを実行
3. retrieved上位3件のchunk_id, answer, verdictフィールドをresults.jsonlに出力
4. verdict欄は空欄で出力（判定は発注者が行う）

## テスト

| テスト | 方法 | 合格条件 |
|---|---|---|
| プレフィックス | ユニットテスト | クエリ側・文書側の両方に正しく付与 |
| 分割品質 | chunks.jsonlのchar_count分布 | 300未満・2000超のチャンクが説明可能な範囲 |
| ビルド | requirements.txt install + 全モジュールimport | エラーなし |
| E2E | eval/run_eval.py | results.jsonlが10問分出力される |

## 禁止事項

- APIキーをコードやコミットに含めない
- questions.jsonlを改変しない
- 精度チューニングのための試行錯誤は不要（7問passを狙うが、未達分は失敗分析としてREADMEに書く）

## 完了条件

- 全モジュールが動作し、ingest→query→evalの一連が通ること
- results.jsonlが10問分出力されること（verdict判定は発注者）
- chunks.jsonlが目視検査可能な形で存在すること
- README.mdに設計判断（棄却リスト含む）が記述されていること
- push済み
