# Score Function

Score Function は、仕様適合度・コード品質・テスト体制・セキュリティ・PR 運用・デプロイ体制の 6 つの面をスコアリングし、幾何平均＋不確実性控除で 0–100 の最終指標を返します。本リポジトリは CC0 (Public Domain) で配布され、式・設定・入出力例・実装・API・CI を一括で参照できます。

> Security の符号修正 / クリティカル特例 / k=14 / 幾何平均前フロア=5 を反映済み。

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
  score_function.ts          # TypeScript 版（Node/自前サーバレス向け）
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

- HTTP API で公開する場合は自前のアプリ／サーバレス環境からこのモジュールを呼び出してください（以前の Vercel / Cloudflare 向けサンプルは撤去済み）。

### 4. CI への組み込み

CI では `collect_metrics.py` → `python -m score_function` → ゲート判定の 3 ステップを 1 ジョブにまとめて実行してください。GitHub Actions 例は撤去したので、各自の CI/CD（GitHub Actions, CircleCI, Jenkins など）で相当のステップを用意してください。

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

### 6. ランタイム / 配布のヒント

- **Python**: `pip install .` でローカル利用できます。CLI は `python -m score_function ...` あるいは `score-function` で実行し、`python -m build` で PyPI 配布用パッケージを生成できます。
- **TypeScript / npm**: `npm run build` で `dist/tools/score_function.{js,d.ts}` を出力し、そのまま `npm publish` で公開できます（`prepublishOnly` が `tsc` を実行）。
- **任意基盤への組み込み**: API / バッチ / CLI など任意の実行環境からライブラリ関数を呼ぶだけで完結します。Python 例: `python -m score_function score-function.yml metrics.json`。TypeScript 例: `node dist/tools/score_function.js metrics.json`。

## ログと可視化

- 出力 JSON 全体（特に `faces`, `final`, `gate_ok`）をそのままログ収集基盤に送れば、BI やモニタリングから参照できます。
- `gate_ok == false` を通知し、`final` の時系列を可視化しておくと品質リグレッションの検知が容易です。

## 入出力スキーマ

- Config: `score-function.yml`
- Metrics: `examples/metrics.sample.json` (0–1 正規化済み値と `uncertainty_sigma`)

## プロファイル

`score-function.yml` の `external_weights` に `sre` / `speed` プロファイルを定義しています。CLI では config で `profile` を切り替えるか、API で上書きしてください。

## ライセンス

CC0 1.0 / Public Domain。出典不要で自由にご利用いただけます。
