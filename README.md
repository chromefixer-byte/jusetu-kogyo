# jusetu-kogyo — 建設業向けRAGポートフォリオ

**公共建築工事標準仕様書（電気設備工事編）令和7年版**を対象とした、CLI型RAG（Retrieval-Augmented Generation）ツール。

副業参入用ポートフォリオとして「業務文書をAIに扱わせる際の意思決定」を実装・展示することが目的。

---

## セットアップ

**注意：埋め込みモデル（ruri-v3-310m）はHuggingFaceからダウンロードするため、インターネット接続が必要です。
Claude Code Remote環境ではhuggingface.coへのアクセスがブロックされる場合があります。その場合はローカル環境で実行してください。**

```bash
# 依存パッケージ
pip install -r requirements.txt

# 素材PDF配置
mkdir -p data/raw
# PDFファイル名: 公共建築工事標準仕様書（電気設備工事編）令和７年版.pdf
# ダウンロード元: https://www.mlit.go.jp/gobuild/content/001888825.pdf

# APIキー設定（console.anthropic.com で発行。Maxプランとは別課金）
export ANTHROPIC_API_KEY=sk-...
```

## 実行フロー

```bash
# 1. 取り込み（抽出→チャンク→埋め込み→Chroma格納）
python -m src.ingest --pdf data/raw/001888825.pdf

# 2. 検索・回答
python -m src.query "分電盤の保護等級は屋内形と屋外形でそれぞれ何か？"

# 3. 一括評価（10問）
python eval/run_eval.py
# → eval/results.jsonl に出力（verdict欄は人間が記入）
```

## ファイル構成

```
src/extract/
  plumber.py      pdfplumber抽出
  pymupdf_ext.py  PyMuPDF抽出
  arbiter.py      突合判定（採用エンジン選択）
src/
  chunker.py      条番号正規表現・分割ルール
  ingest.py       抽出→分割→埋め込み→Chroma格納
  query.py        検索→生成→出典付き回答
eval/
  questions.jsonl 想定質問10問（PM支給・改変禁止）
  run_eval.py     一括評価実行
  results.jsonl   評価結果（実行後に生成）
tests/
  test_prefix.py  プレフィックスユニットテスト
  test_arbiter.py arbiterユニットテスト
  test_chunker.py chunkerユニットテスト
data/
  chunks.jsonl    中間チャンク（ingest後に生成・目視検査用）
  chroma/         Chromaベクトルストア（ingest後に生成）
```

---

## 設計判断

### PDF抽出：pdfplumber＋PyMuPDF突合

単一エンジンでは「テーブル抽出精度（pdfplumber有利）」と「本文読み順（PyMuPDF有利）」のトレードオフが生じる。
arbiter.pyがページ単位で2エンジンの結果を比較し、**文字化け率（weight 0.6）+ 行断片化度（weight 0.4）** のスコアが低い方を採用。採用エンジンはchunk metadataの `source_engine` フィールドに痕跡として残す。

判定基準を明文化した理由：建設・検査業務では「なぜその数値を採用したか」を記録することが必須。ベクトルDBに判定根拠（採用エンジン）を残す設計もその思想の反映。

### チャンク分割：条番号正規表現

- 条（X.Y.Z）単位で1チャンク
- 300字未満 → 同じ節の隣接条文と統合（断片防止）
- 2,000字超 → 項（(1)(2)...）単位で分割（コンテキスト長制限への対応）
- 閾値は仮置き。実PDF確認後に調整し、調整結果はこのREADMEに追記する

上位階層（編/章/節）の見出しを追跡してhierarchyフィールドを構築。
例: `第2編 電力設備工事/第1章 機材/第3節 配線器具/1.3.1`

### 埋め込みモデル：ruri-v3-310m

日本語検索精度（JMTEB）で現行最良クラスのローカルモデル。GPU不要（CPU動作）。
**プレフィックスが異なる（文書側: `文章: ` / クエリ側: `クエリ: `）**点が最大の既知の罠。
付与漏れをユニットテスト（`tests/test_prefix.py`）で検査する。

埋め込み対象は `heading + body` の連結。body単独では「何についての条文か」が失われ検索精度が落ちる。

### フレームワーク：LlamaIndex + Chroma

検索主目的のRAGの定番。Chromaはローカル・無料でポートフォリオ用途に適切。

### 生成：Claude API（claude-sonnet-4-6）

プロンプトに「出典の章・条番号を必ず明示、根拠がなければ『該当なし』と答える」を含む。根拠のない補完を禁止することで、建設仕様書の誤引用リスクを低減。

---

## 棄却リスト

| 候補 | 棄却理由 |
|---|---|
| tesseract | 日本語精度で実用不達（実試行済み） |
| Docling | 日本語の漢数字・長音記号の誤抽出報告あり |
| YomiToku | 精度最高クラスだがCC BY-NC-SA。商用ライセンス別途必要 |
| ハイブリッド検索 | 10問規模に過剰。将来改善候補 |
| RAGAS | 評価の最終責任を機械に渡さない設計方針と相容れない |
| multilingual-e5-small | ruri-v3-310mの日本語精度に劣る（初期案から変更） |

---

## 評価結果（eval/results.jsonl）

`python eval/run_eval.py` 実行後に生成される。verdict欄はショウゴさんが記入。

7問以上passを目標とするが、未達の場合は以下で分析：
- chunk境界が条文の途中で切れていないか（chunks.jsonlで目視確認）
- 検索でヒットしたchunk_idがexpected_sourceの条番号を含むか
- LLMが参照条文を正しく引用できているか

---

## テスト実行

```bash
python -m pytest tests/ -v
```

| テスト | 確認内容 |
|---|---|
| test_prefix.py | クエリ・文書両側のプレフィックス付与 |
| test_arbiter.py | 文字化け・断片化スコアリング、エンジン選択 |
| test_chunker.py | 分割フィールド・階層構造・条番号抽出 |
