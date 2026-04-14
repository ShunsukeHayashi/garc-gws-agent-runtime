# GARC vs LARC — 比較ドキュメント

## 概要

GARCとLARCは同じランタイムガバナンスモデルを共有する兄弟プロジェクトです。
バックエンドプラットフォームのみが異なります。

| 側面 | LARC | GARC |
|------|------|------|
| バックエンド | Feishu / Lark | Google Workspace |
| ファイルストレージ | Lark Drive | Google Drive |
| 構造化DB | Lark Base | Google Sheets |
| メッセージング | Lark IM | Gmail / Google Chat |
| ナレッジ | Lark Wiki | Google Docs |
| 承認フロー | Lark Approval | Sheets + Gmail |
| カレンダー | Lark Calendar | Google Calendar |
| タスク | Lark Project | Google Tasks |
| 認証 | Lark OAuth + `lark-cli` | Google OAuth 2.0 |
| MCP統合 | `openclaw-lark` スキル | Gmail/Drive/Calendar MCP |

## 共通アーキテクチャ（変わらないもの）

### 1. 開示チェーン（Disclosure Chain）

```
SOUL.md → USER.md → MEMORY.md → RULES.md → HEARTBEAT.md
```

LARCではLark Drive、GARCではGoogle Driveに保存。
読み込み後のローカルキャッシュ構造（`~/.larc/` / `~/.garc/`）は同一。

### 2. パーミッションインテリジェンス

```bash
larc auth suggest "create expense report"   # LARC
garc auth suggest "create expense report"   # GARC
```

どちらも同じキーワードマッチング + スコープ推定ロジック。
出力フォーマットも同一。LARCはLarkスコープ、GARCはGoogle OAuthスコープ。

### 3. 実行ゲート

```
none     → 即時実行（読み取り系）
preview  → --confirm フラグ必要（外部可視・書き込み）
approval → 承認ゲート（金銭・権限・不可逆）
```

ゲートポリシーのタスクカテゴリは共通。LARCはLark Approval、GARCはSheets+Gmailで管理。

### 4. エージェントレジストリ

LARCはLark Baseにエージェント台帳、GARCはGoogle Sheetsに同構造で保存。
`agents.yaml`のフォーマットは両プロジェクトで互換性があります。

### 5. メモリシステム

LARCはLark Baseの`memory`テーブル、GARCはGoogle Sheetsの`memory`タブ。
日次pull/pushのインターフェースは同一。

## 主な差異

### 認証フロー

**LARC**: `lark-cli auth login` → Larkのブラウザ認証 → トークン保存

**GARC**: `garc auth login` → Google OAuth 2.0 フロー → `~/.garc/token.json`

GARCの方が標準的なOAuth2フロー。credentials.jsonの事前ダウンロードが必要。

### MCP統合

**LARC**: `openclaw-lark` プラグイン（9スキル: bitable/calendar/doc/im/task等）

**GARC**: 
- `mcp__claude_ai_Gmail__*` — Gmail操作
- `mcp__claude_ai_Google_Drive__*` — Drive操作  
- `mcp__claude_ai_Google_Calendar__*` — Calendar操作
- Claude Code組み込みMCP → 直接使用可能

GARCはLARCより即座にMCPで動作確認できます（Claude Code側にMCPが既に組み込まれているため）。

### スコープ粒度

**LARC**: Larkのスコープは`docs:doc:readonly`等のパス形式

**GARC**: Googleのスコープは`https://www.googleapis.com/auth/drive.readonly`等のURL形式。
より細かく、`drive`（全Drive）vs `drive.file`（自分が作成したファイルのみ）等の区別がある。

### 承認フロー

**LARC**: Lark Approvalという専用承認ワークフロー機能がある

**GARC**: Google Sheetsのapprovalタブ + Gmail通知で承認管理。
Lark Approvalほどリッチな機能はないが、シンプルで確実。

## 実装状況比較

| 機能 | LARC | GARC |
|------|------|------|
| bootstrap | ✅ live | 🏗 実装済（API接続待ち） |
| memory pull/push | ✅ live | 🏗 実装済（API接続待ち） |
| memory search | ✅ live | 🏗 実装済（API接続待ち） |
| send message | ✅ live | 🏗 実装済（API接続待ち） |
| task list/create | ✅ live | 🏗 実装済（API接続待ち） |
| auth suggest | ✅ live | ✅ 実装済（Python、動作可） |
| approve gate | ✅ live | ✅ 実装済（JSON、動作可） |
| agent register | ✅ live | 🏗 実装済（API接続待ち） |
| heartbeat | ✅ live | 🏗 実装済（API接続待ち） |
| kg build/query | ✅ live | 🏗 実装済（API接続待ち） |
| ingress queue | ✅ live | ✅ 実装済（ローカルキャッシュ） |

## 移行・使い分けガイド

### LARCからGARCへの移行

1. `agents.yaml`はそのまま使用可能（スコープのみ変更）
2. 開示チェーンファイル（SOUL.md等）をGoogle Driveにアップロード
3. Lark BaseのデータをGoogle Sheetsにエクスポート
4. `larc` → `garc` コマンドは1:1対応

### 両方使う場合

```
Feishu/Lark ユーザー向けタスク → LARC
Google Workspace ユーザー向けタスク → GARC
```

agents.yamlは共通形式のため、エージェントを両プラットフォームに登録可能。
上位エージェント（OpenClaw）が状況に応じてどちらのランタイムを使うか選択します。
