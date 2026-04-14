# GARC Quickstart — 15分で動かす

## 前提

- Python 3.10+
- pip3
- Google アカウント（Gmail / Drive 使用中）

---

## Step 1 — インストール

```bash
git clone <this-repo> ~/study/garc-gws-agent-runtime
cd ~/study/garc-gws-agent-runtime

# Python依存パッケージ
pip3 install -r requirements.txt

# CLIをPATHに追加
echo 'export PATH="$HOME/study/garc-gws-agent-runtime/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# 確認
garc --version
# → garc 0.1.0
```

---

## Step 2 — Google Cloud Console でAPIを有効化

1. https://console.cloud.google.com/ にアクセス
2. 新規プロジェクトを作成（または既存を選択）
3. **「APIとサービス」→「APIとサービスを有効化」** で以下を有効化：

| API | サービス名 |
|-----|---------|
| Google Drive API | `drive.googleapis.com` |
| Google Sheets API | `sheets.googleapis.com` |
| Gmail API | `gmail.googleapis.com` |
| Google Calendar API | `calendar-json.googleapis.com` |
| Google Tasks API | `tasks.googleapis.com` |
| Google Docs API | `docs.googleapis.com` |
| Google People API | `people.googleapis.com` |

4. **「認証情報」→「OAuth 2.0 クライアントID」** を作成
   - アプリタイプ: **デスクトップアプリ**
   - JSONダウンロード → `~/.garc/credentials.json` に保存

5. **「OAuth同意画面」** → テストユーザーに自分のGmailを追加

---

## Step 3 — 認証

```bash
garc auth login --profile backoffice_agent
# → ブラウザが開く → Googleログイン → 全スコープを承認
# → ~/.garc/token.json が生成される

garc auth status
# → 付与されたスコープが表示される
```

---

## Step 4 — ワークスペースを自動プロビジョニング

```bash
garc setup all
# → Google DriveにGARC Workspaceフォルダを作成
# → Google Sheetsにすべてのタブを作成（memory/agents/queue/heartbeat/approval...）
# → 開示チェーンテンプレート（SOUL.md等）をDriveにアップロード
# → ~/.garc/config.env にIDを自動保存
```

---

## Step 5 — 動作確認

```bash
garc status
# → 全項目が ✅ になることを確認

garc bootstrap --agent main
# → DriveからSOUL.md/USER.md/MEMORY.md等を読み込み
# → ~/.garc/cache/workspace/main/AGENT_CONTEXT.md に統合

garc auth suggest "send weekly report to manager"
# → スコープ推定が動く
```

---

## 主な操作例

```bash
# メール
garc gmail inbox --unread
garc gmail send --to boss@co.com --subject "週次レポート" --body "先週の進捗..."
garc gmail search "from:alice@co.com" --max 10

# カレンダー
garc calendar today
garc calendar week
garc calendar create --summary "MTG" --start "2026-04-16T14:00:00" --end "2026-04-16T15:00:00" --attendees alice@co.com
garc calendar freebusy --start 2026-04-16 --end 2026-04-17 --emails alice@co.com bob@co.com

# Drive
garc drive list
garc drive search "議事録" --type doc
garc drive upload ./report.pdf --convert
garc drive create-doc "Meeting Notes 2026-04-15"

# Sheets
garc sheets info
garc sheets read --range "memory!A:E" --format json
garc sheets search --sheet memory --query "経費"

# メモリ
garc memory pull
garc memory push "顧客Aとの商談: 来週デモを実施することになった"
garc memory search "顧客A"

# タスク
garc task list
garc task create "Q1レポートを作成" --due 2026-04-30
garc task done <task_id>

# 権限確認
garc auth suggest "経費精算を申請してマネージャーに送る"
garc approve gate create_expense

# エージェント登録
garc agent register
garc agent list
```

---

## 設定ファイル

`~/.garc/config.env`（`garc setup all` で自動生成）:

```bash
GARC_DRIVE_FOLDER_ID=1xxxxxxxxxxxxxxxxxxxxxxxxx
GARC_SHEETS_ID=1xxxxxxxxxxxxxxxxxxxxxxxxx
GARC_GMAIL_DEFAULT_TO=your@gmail.com
GARC_CALENDAR_ID=primary
GARC_DEFAULT_AGENT=main
```

---

## トラブルシューティング

| エラー | 対処 |
|--------|------|
| `credentials.json not found` | Google Cloud ConsoleでOAuth認証情報をダウンロード |
| `Token refresh failed` | `garc auth login` で再認証 |
| `API not enabled` | Google Cloud ConsoleでAPIを有効化 |
| `403 insufficientPermissions` | `garc auth login --profile backoffice_agent` で再認証（スコープ追加） |
| `Sheets tab missing` | `garc setup sheets` でタブを再作成 |
