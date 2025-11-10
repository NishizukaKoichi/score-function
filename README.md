# Score Function (v1.3)

Score Function は、仕様適合度・コード品質・テスト体制・セキュリティ・PR 運用・デプロイ体制の 6 つの面をスコアリングし、幾何平均＋不確実性控除で 0–100 の最終指標を返します。本リポジトリは CC0 (Public Domain) で配布され、式・設定・入出力例・実装・API・CI を一括で参照できます。

> Security の符号修正 / クリティカル特例 / k=14 / 幾何平均前フロア=5 を反映済み。

詳細な導入手順・正規化・プロファイル調整は `docs/ADOPTION.md` を参照してください。

## 数式サマリ

- クリップ: `clip(x)=min(1,max(0,x))`
- ロジスティック: `H(x; τ, k)=1/(1+exp(-k(x-τ)))`, `k=14`
- 罰則は全て乗算 (例: `×(1-0.3·H(...))`)
- 幾何平均前フロア `S'i = max(5, Si)`
- 総合:
  \[
  G = 100\cdot\Big(\prod_{f\in F}\frac{S_f'}{100}\Big)^{1/6},\qquad
  \text{Final}=G\cdot(1-0.1\hat\sigma)
  \]
- ゲート条件: `min(Si) ≥ 70` **かつ** `G ≥ 80`

面ごとの式・罰則係数・逆指標の扱いは `score-function.yml` に完全記述済みです。

## ファイル構成

```
README.md                    # このファイル
LICENSE                      # CC0 1.0 Universal
score-function.yml           # 配布用コンフィグ (profile="sre")
examples/metrics.sample.json
score_function/
  __init__.py                # Python ライブラリ & CLI エントリ
  __main__.py
  py.typed
tools/
  collect_metrics.py         # ESLint/Jest/pytest/Syft/Semgrep/Stryker の雛形集約
  score_function.ts          # TypeScript 版 (Node/Edge/Workers 共通)
api/score-function/route.ts  # Vercel Edge Function エントリ
workers/score-function.ts    # Cloudflare Workers エントリ
.github/workflows/score-function.yml # CI 例 (PR ゲート)
```

## 使い方

### 1. メトリクスの収集

`tools/collect_metrics.py` は ESLint / Jest coverage / pytest json-report / Syft / Semgrep / Stryker の JSON を取り込み、Score Function の 0–1 指標へ正規化します。デフォルトでは `reports/` 配下の次ファイルを読みます:

- `eslint.json` (`eslint -f json`)
- `coverage-summary.json` (`jest --coverage --coverageReporters=json-summary`)
- `pytest-report.json` (`pytest --json-report`)
- `stryker-report.json` (`stryker run --reporters json`)
- `semgrep.json` (`semgrep --json`)
- `syft.json` (`syft scan --output json`)

カスタムパスは `--eslint` などの引数、もしくは `--reports-dir` でルートを指定してください。`--strict` を付けると未検出レポートで即エラーになります。

```bash
python tools/collect_metrics.py > metrics.json
```

### 2. スコアの算出 (Python)

```bash
python -m score_function score-function.yml metrics.json
```

標準出力:

```json
{
  "faces": {"spec":84.3,"code":88.7,"test":79.5,"sec":90.2,"pr":86.0,"dep":91.3},
  "weighted_faces": {"spec":84.3,"code":88.7,"test":79.5,"sec":108.2,"pr":86.0,"dep":109.5},
  "geo": 86.9,
  "final": 85.9,
  "gate_ok": true
}
```

### 3. TypeScript / サーバレス

```ts
import { scoreFunction, DEFAULT_CONFIG } from "./tools/score_function";
const result = scoreFunction(DEFAULT_CONFIG, metrics);
```

- Vercel Edge: `api/score-function/route.ts`
- Cloudflare Workers: `workers/score-function.ts`

### 4. CI への組み込み

`.github/workflows/score-function.yml` を参照してください。`collect_metrics.py` → `python -m score_function` → ゲート判定の 3 ステップで PR をブロックできます。

### 5. テスト / 型チェック

```bash
# Python (pytest)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest

# TypeScript (tsc)
npm install
npm run build
```

### 6. デプロイ (Vercel / Cloudflare)

- **Vercel Edge**：`vercel.json` と `api/score-function/route.ts` を対象に `Deploy Vercel Edge` ワークフローが `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` の GitHub Secrets を使って `npx vercel deploy --prod` を実行します。手動 `workflow_dispatch` か main への push で起動可能です。
- **Cloudflare Workers**：`wrangler.toml` + `workers/score-function.ts` を `Deploy Cloudflare Worker` ワークフローが `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` を用いて `wrangler publish` します。
- ローカルでの手動デプロイ例:

```bash
# Vercel
npm install && npm run build
VERCEL_TOKEN=... npx vercel deploy --prod

# Cloudflare
npm install && npm run build
npx wrangler publish
```

# 7. 配布

- **Python**: `pyproject.toml` を同梱しているため `pip install .` でローカルインストールできます。CLI は `python -m score_function ...` もしくは `score-function` エントリポイントで利用可能です。`python -m build` で sdist/wheel を生成して PyPI に公開できます。
- **TypeScript / npm**: `npm publish` で `dist/tools/score_function.{js,d.ts}` を配布できます。`prepublishOnly` が `npm run build` を呼ぶので、`npm version` → `npm publish` のフローで自動的に型定義付きバンドルを配布できます。

# 8. オブザーバビリティ

`docs/OBSERVABILITY.md` にログ収集・メトリクス化・アラート設計のベストプラクティスをまとめています。Vercel Edge / Cloudflare Workers では `score-function` ラベルの JSON ログを出力しているので、Logpush/BigQuery 等に送ってダッシュボード化してください。

## 入出力スキーマ

- Config: `score-function.yml`
- Metrics: `examples/metrics.sample.json` (0–1 正規化済み値と `uncertainty_sigma`)

## プロファイル

`score-function.yml` の `external_weights` に `sre` / `speed` プロファイルを定義しています。CLI では config で `profile` を切り替えるか、API で上書きしてください。

## ライセンス

CC0 1.0 / Public Domain。出典不要で自由にご利用いただけます。
