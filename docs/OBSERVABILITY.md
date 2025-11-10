# Observability & Monitoring

Score Function を継続運用するためのログ／メトリクス収集・アラートの推奨構成です。

## 1. ログ出力

Vercel Edge / Cloudflare Workers ではレスポンス前に以下のログを出しています（`api/score-function/route.ts`, `workers/score-function.ts`）。

```jsonc
{
  "label": "score-function",
  "profile": "sre",
  "final": 85.9,
  "geo": 86.9,
  "gate_ok": true
}
```

- **Vercel**: `vercel logs <deployment>` で確認。`VERCEL_LOGS_ENDPOINT` へストリーミングして BigQuery 等に集約可能。
- **Cloudflare**: Workers Logpush を有効化し、R2 / Splunk / Datadog に転送。

## 2. メトリクス化

1. ログを集中ストレージ (BigQuery, S3, Logpush) に送る。
2. 定期バッチまたは streaming pipeline で以下のメトリクスを生成:
   - `score_function.final`
   - `score_function.geo`
   - `score_function.gate_ok` (0/1)
   - `score_function.face.<name>` (spec/code/...)
3. Grafana / Looker / Data Studio でトレンドを可視化し、しきい値ベースのアラートを構築。

## 3. アラート例

| 条件 | 推奨アクション |
|------|----------------|
| `gate_ok = 0` が連続 3 回 | 直近レポートを確認し、どの面がゲートを割ったか調査 |
| `sec < 75` | セキュリティチームに通知し、脆弱性掃討を優先 |
| `uncertainty_sigma > 0.3` | メトリクス入力の信頼度低下。CI 動作やレポートの欠損を調査 |

## 4. デバッグ Tips

- `metrics.json` を保存しておくと、再計算 (`python -m score_function ...`) で再現性を担保できます。
- TypeScript API で `env.DEBUG=true` を設定し、`scoreFunction` 実行時の入力/出力をさらにログ出力することも可能です（運用ポリシーに合わせてマスク処理を追加してください）。

## 5. 今後の拡張例

- OpenTelemetry エクスポータを追加してトレースと紐付け。
- Slack/Webhook 通知: gate failure 時に自動で通知。
- `score_function` から返す `faces` をヒートマップ化し、改善ポイントをダッシュボードで共有。
