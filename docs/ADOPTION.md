# Score Function Adoption Guide

本ドキュメントは Score Function を自分たちの組織・AI フローに組み込む際のベストプラクティスをまとめたものです。

## 1. セットアップ手順

1. リポジトリ取得: `git clone https://github.com/NishizukaKoichi/score-function.git`
2. 依存インストール:
   - Python: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt`
   - Node: `npm install`
3. メトリクス収集: `python tools/collect_metrics.py --reports-dir reports > metrics.json`
4. スコア算出: `python tools/score_function.py score-function.yml metrics.json`
5. CI ゲート: `.github/workflows/score-function.yml` をコピーし、レポート生成ステップを自分の lint/test/sast/scan スクリプトに置き換える。

## 2. プロファイル調整

`score-function.yml` には `external_weights` の `sre` / `speed` プロファイルが定義されています。
- SRE 重視: `sec`/`dep` を 1.2× することで信頼性を高める判定。
- 速度重視: `spec`/`code`/`test`/`pr` を 1.15×、`sec`/`dep` を 0.9× にしてデリバリー優先。

独自プロファイルを追加する場合:
```yaml
external_weights:
  security_first: { spec: 0.9, code: 1.0, test: 1.0, sec: 1.5, pr: 0.9, dep: 1.3 }
```
CLI/API 呼び出し時に `profile="security_first"` を指定してください。

## 3. 指標正規化

Score Function は 0–1 の入力を想定しているため、各指標を min-max もしくは分位点で正規化します。
- 推奨: 直近 30 日の `p10 -> 0`, `p90 -> 1` を基準に線形正規化。
- CVSS や dep_vulns は syft などのスキャン結果を 0–1 にスケーリング (`cvss/10`, `count / 上限`)。
- 低いほど良い指標 (AM, CN, CC, DP, etc.) はそのまま 0 がベスト、1 がワーストとして扱います。

## 4. レポート連携

`tools/collect_metrics.py` は以下の標準出力を想定しています。必要に応じて `--eslint`, `--jest` などでファイルを切り替え、またはスクリプトをカスタマイズしてください。

| Tool | コマンド例 | 出力先 |
|------|------------|--------|
| ESLint | `eslint -f json -o reports/eslint.json` | `reports/eslint.json` |
| Jest | `jest --coverage --coverageReporters=json-summary` | `coverage-summary.json` |
| pytest | `pytest --json-report --json-report-file=reports/pytest-report.json` | `reports/pytest-report.json` |
| Stryker | `npx stryker run --reporters json` | `reports/stryker-report.json` |
| Semgrep | `semgrep --json -o reports/semgrep.json` | `reports/semgrep.json` |
| Syft | `syft scan --output json > reports/syft.json` | `reports/syft.json` |

CI では `collect_metrics.py` までを 1 ステップにまとめ、Score Function CLI→ゲート判定までを一気に流すとシンプルです。

## 5. API / サーバレス導入

### Vercel Edge
1. `vercel.json` と `api/score-function/route.ts` をリポに含める。
2. GitHub Secrets に `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` を登録。
3. `Deploy Vercel Edge` ワークフローが push/手動で `npx vercel deploy --prod` を実行します。
4. デプロイ URL を Slack/AI ツールから叩けば POST `/api/score-function` でスコア計算可能。

### Cloudflare Workers
1. `wrangler.toml` と `workers/score-function.ts` を配置。
2. `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` を GitHub Secrets に設定。
3. `Deploy Cloudflare Worker` ワークフローが `wrangler publish` を呼び出して更新。
4. エッジロケーションで `scoreFunction` を呼び出せる API が完成。

## 6. 運用ノート

- **ゲート条件**: `min(face) >= 70` かつ 幾何平均 `>= 80`。どちらかを割るとゲート NG。必要なら `score-function.yml` の `gate` セクションで閾値を調整。
- **不確実性**: `uncertainty_sigma` は 0–1 の範囲。信頼できない指標が多い場合は 0.2 以上に引き上げ、最終スコアを安全側にバイアス。
- **学習サイクル**: 週次/スプリント単位で各重み・閾値をベイズ最適化やマルチアームバンディットで更新し、SLO 達成度を目的関数にします。
- **AI 連携**: LLM/エージェントから呼び出す場合、metrics.json を生成して API or CLI を実行するだけでスコアリング可能。インサイトを返すために `faces` / `weighted_faces` の内訳を可視化すると理解が進みます。

## 7. ハンドオーバー

- 進捗/タスクは `PROGRESS.md` に記載。
- 次の保守担当は T-15 以降のチケット状況を確認し、必要に応じて新規チケットを追記してください。

