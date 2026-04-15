# GARC v0.1.0 — ファインディング対応プレイブック

> 作成: 2026-04-15  
> 対象バージョン: v0.1.0 (commit 680bd43)  
> 実稼働テスト + コードレビューによるファインディングをもとに作成。

---

## 優先度定義

| レベル | 基準 |
|--------|------|
| **P0** | 即座に運用を妨げる。リリース前に必須対応 |
| **P1** | 継続運用で詰まる。初回本番投入前に対応 |
| **P2** | 機能欠如。SMB〜エンタープライズ展開前に対応 |
| **P3** | 将来の拡張。ロードマップに計上 |

---

## P0 — リリースブロッカー (3件)

---

### P0-1: `garc agent register` が重複登録する

**症状**  
`garc agent register` を複数回実行すると `agents.yaml` の全エージェントが毎回 Sheets に追記される。一意性チェックがないため、台帳が汚染される。

**対応方策**  
1. `garc-setup.py` の `register_agents()` で、登録前に `agents` タブを読み取り `id` カラムで既存チェック
2. 既存エントリは `skip`、変更がある場合は `update`（行を上書き）、新規のみ `append`
3. 出力に `Registered N / Skipped N / Updated N` を表示

**実装ファイル**  
- `scripts/garc-setup.py` — `register_agents()` 関数
- `lib/agent.sh` — `_agent_register()` でも同様のチェックが必要

**受入条件**  
- 同一 `id` のエージェントを2回登録しても Sheets 行数が増えない
- `garc agent list` で重複行が表示されない

---

### P0-2: `garc daemon poll-once` が Gmail 取得後にエンキューしない

**症状**  
`garc daemon poll-once` でポーリングループを5秒で強制終了するため、Gmail JSON fetch の完了前にプロセスが kill される。未読メールが取得されてもキューに入らない。

**対応方策**  
1. `_daemon_poll_once()` の実装を「ループ起動 + 5秒後 kill」から「1回だけ前景実行」に変更
2. `_gmail_poller_loop()` に `--once` フラグを追加。`once=true` の場合は1サイクル実行後に `break`
3. `poll-once` はループを spawn せず直接 `_gmail_poller_loop_once()` を呼ぶ

**実装ファイル**  
- `lib/daemon.sh` — `_daemon_poll_once()` および `_gmail_poller_loop()`

**受入条件**  
- `garc daemon poll-once` 実行後に `garc ingress list` で Gmail 由来のキューアイテムが確認できる

---

### P0-3: 全コマンドに `requests` ライブラリ警告が出力される

**症状**  
Python 3.14 + urllib3/chardet バージョン不一致により、全 Python ヘルパー実行時に警告が stderr に出力される。自動化スクリプトや JSON パースが壊れる。

```
RequestsDependencyWarning: urllib3 (2.6.3) or chardet (7.4.0.post1)/charset_normalizer (3.4.4) doesn't match a supported version!
```

**対応方策**  
1. `garc_core.py` の先頭に `warnings.filterwarnings("ignore", category=Warning, module="requests")` を追加
2. あわせて `requirements.txt` の `requests` を `urllib3` と互換バージョンに固定 (`urllib3>=2.0,<3`)
3. 根本解決: `google-api-python-client` が依存する `httplib2` + `requests` のバージョンを揃える

**実装ファイル**  
- `scripts/garc_core.py` — 先頭に警告抑制を追加
- `requirements.txt` — バージョン固定

**受入条件**  
- `garc gmail profile` の出力に警告行がゼロ

---

## P1 — 本番投入前必須 (4件)

---

### P1-1: OAuth トークン自動リフレッシュが未検証

**症状**  
`token.json` の有効期限は約1時間。期限切れ後の自動リフレッシュが実際に動作するか未検証。長時間運用の daemon や ingress 処理でトークン切れが起きると全 API 呼出しが失敗する。

**対応方策**  
1. `garc_core.py` の `get_credentials()` が `creds.refresh_token` を使った自動更新を行っていることを確認
2. `garc auth status` に有効期限 + 残り時間を表示するオプション追加
3. 期限 5 分前に daemon ログに警告を出す仕組みを `_gmail_poller_loop()` に追加
4. 統合テスト: トークンを意図的に期限切れさせてリフレッシュが動くことを確認

**実装ファイル**  
- `scripts/garc_core.py` — `get_credentials()`
- `scripts/garc-auth-helper.py` — `status` サブコマンド
- `lib/daemon.sh` — ループ内でトークン期限チェック

**受入条件**  
- 1時間以上連続稼働した daemon が API 失敗なしで動作する

---

### P1-2: `ingress run-once` 後にキューが `in_progress` のまま詰まる

**症状**  
`garc ingress run-once` で Claude Code へプロンプトを渡した後、Claude が作業を完了しても `garc ingress done` を手動で呼ばないとステータスが `in_progress` のままになる。キューが消化されずに詰まる。

**対応方策**  
1. `garc ingress run-once` の出力末尾に必ず以下を含める:
   ```
   完了後に必ず実行: garc ingress done --queue-id <id> --note "<完了内容>"
   ```
2. Claude Code スキル (`SKILL.md`) に「作業完了後 `garc ingress done` を実行する」ルールを明記
3. `none` ゲートのアイテムは自動で `done` にする `-auto-close` フラグを検討
4. `garc ingress list` で `in_progress` が一定時間 (例: 30分) 以上のアイテムに警告表示

**実装ファイル**  
- `lib/ingress.sh` — `_ingress_run_once()` 出力末尾
- `.claude/skills/garc-runtime/SKILL.md` — 完了ルールの明記

**受入条件**  
- `run-once` の出力末尾に `done` コマンドのガイダンスが表示される

---

### P1-3: Google Sheets の初期空行 1000 行問題

**症状**  
`garc setup all` でプロビジョニングした Sheets の各タブが 1000〜1004 行の空行を持つ。`sheets read` や `memory search` で空行がヒットし、結果が汚染される。

**対応方策**  
1. `garc-setup.py` の Sheets 作成時に空行を事前に挿入しない (`batchUpdate` で行数指定)
2. 既存 Sheets の空行クリーンアップコマンド `garc setup cleanup-sheets` を追加
3. `sheets read` / `memory search` で空行 (全カラムが空) を結果から除外するフィルタを追加

**実装ファイル**  
- `scripts/garc-setup.py` — Sheets provisioning
- `scripts/garc-sheets-helper.py` — 空行フィルタ
- `scripts/garc_core.py` — Sheets 読取ユーティリティ

**受入条件**  
- `garc sheets read --range "memory!A:E"` が空行ゼロで返る

---

### P1-4: approval gate のブロック後に承認者への通知手段がない

**症状**  
`approval` ゲートでキューが `blocked` 状態になっても、承認者 (人間) への通知手段がない。Google Chat 未実装のため、承認リクエストが放置される。

**対応方策**  
1. `approval` ゲート発動時に承認依頼メールを Gmail で自動送信 (短期対応)
   - `GARC_APPROVAL_EMAIL` 環境変数で承認者メールを指定
   - `_ingress_run_once()` の approval 分岐で `garc gmail send` を内部呼出し
2. 承認メールに `garc ingress approve --queue-id <id>` のコマンドを記載
3. (中期) Google Chat 実装後は Chat にも通知

**実装ファイル**  
- `lib/ingress.sh` — `_ingress_run_once()` approval 分岐
- `config/config.env.example` — `GARC_APPROVAL_EMAIL` の追加

**受入条件**  
- `approval` ゲートのタスクをエンキューすると承認者メールが届く

---

## P2 — エンタープライズ展開前必須 (6件)

---

### P2-1: Google Chat 通知未実装

**症状**  
承認通知・完了通知・エラー通知をリアルタイムで受け取る手段がない。Gmail メールは遅延があり、Chat スペースへの投稿ができない。

**対応方策**  
1. `lib/chat.sh` + `scripts/garc-chat-helper.py` を新規作成
2. Google Chat API (`chat.googleapis.com`) の `spaces.messages.create` を実装
3. `garc chat send --space <id> --text "<msg>"` コマンドを追加
4. `GARC_CHAT_SPACE_ID` 環境変数でデフォルトスペースを設定
5. 承認通知・ingress done 通知・heartbeat アラートを Chat に自動送信

**実装ファイル**  
- `lib/chat.sh` (新規)
- `scripts/garc-chat-helper.py` (新規)
- `bin/garc` — `chat` コマンドのディスパッチ追加

---

### P2-2: Service Account / Domain-wide Delegation 未対応

**症状**  
現状はユーザー OAuth トークンのみ対応。ヘッドレス・ボット運用 (daemon、CI/CD) では Service Account が必要。企業のポリシーでユーザー OAuth を使えないケースに対応不可。

**対応方策**  
1. `garc_core.py` の `get_credentials()` に Service Account フローを追加
   ```python
   if GARC_SERVICE_ACCOUNT_FILE:
       creds = service_account.Credentials.from_service_account_file(...)
   ```
2. `garc auth login --service-account` サブコマンドを追加
3. `GARC_USE_SERVICE_ACCOUNT=true` 環境変数でフロー切替
4. Domain-wide Delegation 用の subject 設定 (`GARC_SA_SUBJECT`) を追加

**実装ファイル**  
- `scripts/garc_core.py`
- `scripts/garc-auth-helper.py`
- `config/config.env.example`

---

### P2-3: 監査ログ未実装

**症状**  
「誰がいつ何のコマンドを実行したか」の記録がない。法人コンプライアンス要件 (SOC2, ISO27001等) に非対応。

**対応方策**  
1. `garc_core.py` に `audit_log(action, resource, result)` 関数を追加
2. 全 write 系操作 (gmail send, calendar create, sheets append, ingress done 等) で自動ログ記録
3. ログ先: Google Sheets の `audit_log` タブ + ローカル `~/.garc/cache/logs/audit.jsonl`
4. `garc audit log` コマンドでログ参照
5. 将来: GCP Cloud Logging 連携

**実装ファイル**  
- `scripts/garc_core.py` — `audit_log()` デコレータ
- `scripts/garc-setup.py` — `audit_log` タブ作成
- `lib/audit.sh` (新規)

---

### P2-4: `garc auth revoke` 未実装

**症状**  
トークン失効の方法が `rm ~/.garc/token.json` の手動作業のみ。セキュリティインシデント時やオフボーディング時に正式な revoke フローがない。

**対応方策**  
1. `garc-auth-helper.py` に `revoke` サブコマンドを追加
   ```python
   requests.post("https://oauth2.googleapis.com/revoke", params={"token": creds.token})
   ```
2. revoke 後に `token.json` を削除
3. `garc auth revoke --all` で全プロファイルのトークンを一括失効
4. `lib/auth.sh` に `_auth_revoke()` を追加

**実装ファイル**  
- `scripts/garc-auth-helper.py`
- `lib/auth.sh`

---

### P2-5: `garc kg query` の E2E 動作未確認

**症状**  
`garc kg build` は動作確認済みだが `garc kg query` の実動作が未検証。ナレッジグラフ検索が Claude Code の実行コンテキストに正しく渡されるか不明。

**対応方策**  
1. `garc kg query "<keyword>"` の実動作確認テスト実施
2. `lib/kg.sh` + `scripts/garc-drive-helper.py` の `kg-query` サブコマンドを確認
3. 検索結果が `ingress context` の Claude プロンプトに含まれることを確認
4. `garc bootstrap` 時に KG を自動取込するフローの確認

**実装ファイル**  
- `lib/kg.sh`
- `scripts/garc-drive-helper.py`

---

### P2-6: Google Docs 本文編集未実装

**症状**  
`garc drive create-doc` で新規ドキュメントは作成できるが、既存 Docs の本文への書込み・編集ができない。週次レポートの自動更新など主要ユースケースがブロックされる。

**対応方策**  
1. Google Docs API の `documents.batchUpdate` を使った本文編集を実装
2. `garc drive edit-doc --file-id <id> --append "<text>"` コマンドを追加
3. Markdown → Docs 変換 (最低限: 見出し・段落・箇条書き)
4. `garc drive read-doc --file-id <id>` で本文取得も実装

**実装ファイル**  
- `scripts/garc-drive-helper.py` — `edit-doc`, `read-doc` サブコマンド
- `lib/drive.sh` — `edit-doc`, `read-doc` ディスパッチ

---

## P3 — ロードマップ計上 (4件)

---

### P3-1: マルチテナント (複数 Google Workspace 組織) 未対応

単一 OAuth クライアント + 単一 `config.env` のため、複数組織の同時管理が不可。将来的には組織ごとのプロファイルディレクトリ (`~/.garc/profiles/<org>/`) への切替機能が必要。

---

### P3-2: Google Forms → 自動エンキューパイプライン未実装

Google Forms の回答を Sheets に集約し、新規回答を ingress キューに自動投入するパイプライン。Apps Script または Pub/Sub トリガーとの連携が必要。

---

### P3-3: Linux systemd 対応 (daemon install)

現状は macOS launchd のみ。`garc daemon install --systemd` で `/etc/systemd/system/garc-gmail-poller.service` を生成するオプションが必要。

---

### P3-4: Python 3.10〜3.12 推奨環境への固定

Python 3.14 では `requests` 依存ライブラリとの互換性警告が発生。`setup.py` / `pyproject.toml` で `python_requires=">=3.10,<3.14"` を明示し、推奨バージョンをドキュメント化する。

---

## 対応スケジュール案

| フェーズ | 対象 | 目標バージョン |
|---|---|---|
| Sprint 1 (即時) | P0-1, P0-2, P0-3 | v0.1.1 |
| Sprint 2 (1週間) | P1-1, P1-2, P1-3, P1-4 | v0.1.2 |
| Sprint 3 (2〜3週間) | P2-1 (Chat), P2-2 (SA), P2-3 (Audit), P2-4 (Revoke) | v0.2.0 |
| Sprint 4 (1ヶ月+) | P2-5, P2-6, P3-1〜P3-4 | v0.3.0 |
