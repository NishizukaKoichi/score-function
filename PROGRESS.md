# Score Function — Progress & Handover Tracker

最新状況・残作業・引き継ぎ先のためのチケット一覧。`status` は `Done / In Progress / Todo`。

## Milestones

| Milestone | Description | Status | Notes |
| --- | --- | --- | --- |
| M1: Foundation | リポ構築、仕様ドキュメント、Python/TS 実装、CI/サーバレス雛形 | **Done** | GitHub `score-function` に初期コミット済み |
| M2: Metrics Automation | ESLint/Jest/pytest/Syft/Semgrep/Stryker からの実データ連携 | **Todo** | `tools/collect_metrics.py` を各プロジェクトに合わせて拡張 |
| M3: Validation & QA | テストデータ拡充、単体テスト/型チェック/CI 強化 | **Todo** | CLI/API のリグレッションテスト、tsc 実行など |
| M4: Deployment | Vercel Edge / Cloudflare Workers / 任意 API へのデプロイと監視 | **Todo** | 各環境用の自動デプロイフローを準備 |
| M5: Adoption | 他チーム/AI への導入、ドキュメント整備、Ops ノート更新 | **Todo** | 運用指標や FAQ を README/Docs に追加 |

## Tickets

| ID | Category | Description | Status | Owner / Notes |
| --- | --- | --- | --- | --- |
| T-01 | Docs | README を Score Function 仕様で刷新 | Done | 完了 (v1.3) |
| T-02 | Config | `score-function.yml` プロファイルと閾値定義 | Done | 完了 |
| T-03 | Python | `tools/score_function.py` 実装・CLI 化 | Done | 完了 |
| T-04 | TypeScript | `tools/score_function.ts` (Node/Edge/Workers) | Done | 完了 |
| T-05 | Sample Data | `examples/metrics.sample.json` 提供 | Done | 完了 |
| T-06 | Metrics Stub | `tools/collect_metrics.py` で各レポートを集約 | Done (雛形) | 実データ連携は T-10 で継続 |
| T-07 | Serverless | Vercel Edge `api/score-function/route.ts` | Done | 完了 |
| T-08 | Workers | Cloudflare `workers/score-function.ts` | Done | 完了 |
| T-09 | CI Gate | `.github/workflows/score-function.yml` | Done | 完了 |
| T-10 | Metrics Integration | CI で ESLint/Jest/pytest/Syft/Semgrep/Stryker から実値取得 | Todo | 各プロジェクトのレポート形式に対応させる |
| T-11 | Testing | Python/TS 版の単体テスト・tsc 実行・型検査 | Todo | `pytest`／`tsc --noEmit` など |
| T-12 | Packaging | PyPI/ npm などでの配布検討 | Todo | 任意 |
| T-13 | Deployment | Vercel/Workers へ本番デプロイ＆監視設定 | Todo | Secrets, deploy scripts 作成 |
| T-14 | Observability | メトリクス収集とダッシュボード化 | Todo | 各環境でのログ、アラート設計 |
| T-15 | Adoption Docs | FAQ、運用手順、プロファイル最適化手順を Docs 化 | Todo | README 拡張 or `/docs/` 追加 |

## Next Actions

1. **T-10**: 実際の ESLint/Jest/pytest/Syft/Semgrep/Stryker の出力ファイル形式を確認して `tools/collect_metrics.py` を拡張し、`reports/` 以下から本番値を生成できるようにする。  
2. **T-11**: Python 版へ最小限の単体テスト (`pytest`) を追加し、TypeScript 版は `tsc` で型チェック、CI に組み込む。  
3. **T-13**: 想定デプロイ先 (例: Vercel/Cloudflare) を決め、GitHub Actions からデプロイできるよう Secrets とワークフローを整備。  
4. **T-15**: 利用ガイド／プロファイル調整方法／メトリクス正規化例を Docs 化して他チームが自走できるようにする。

