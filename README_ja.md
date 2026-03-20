# AI Discord Server Manager

LLM + LangGraph で動く Discord サーバー管理ボット。自然言語でリクエストを投げると、ボットが調査・計画・承認・実行のフローで自動的にサーバー管理タスクをこなす。

**English**: [README.md](README.md)

## Features

- **自然言語インターフェース** — `/manage チャンネルを作って` のように日本語/英語でリクエスト可能
- **調査・実行の分離** — 読み取り専用の調査エージェントと、書き込みの実行エージェントが完全に分離
- **承認フロー** — 実行前に対象と内容を表示し、ボタンで承認/拒否。todos の改ざん検出 (SHA-256) 付き
- **権限チェック** — 実行エージェントの各アクションに必要な Discord 権限をマッピング。権限不足のアクションは自動ブロック
- **反復的計画** — LLM プランナーが最大 5 回のループで調査結果を収集し、最適な実行計画を立案
- **会話履歴** — 直近 5 ターンのコンテキストで文脈を維持
- **i18n** — 日本語 (ja) / 英語 (en) 対応
- **メディア対応** — URL / Discord メッセージ添付ファイルから絵文字・スタンプ・サウンドボード・サーバーアイコン/バナーを作成。メッセージリンクから自動で ID 抽出
- **音声処理** — PyAV でサウンドボード用に 5 秒切り捨て (MP3 ストリームコピー / libmp3lame 再エンコード自動切替)
- **Ban/Kick DM 通知** — Embed でサーバー名・理由・メッセージを通知 (DM ブロック時は無視)

## Architecture

```
User Request
     │
     ▼
┌──────────────────────────────────────────────┐
│           Pre-Approval Workflow              │
│  (LangGraph StateGraph)                      │
│                                              │
│  initialize → plan → [investigate ↻]        │
│                    → prepare_approval        │
└──────────────────┬───────────────────────────┘
                   │
            Approve / Reject (Discord UI)
                   │
                   ▼
┌──────────────────────────────────────────────┐
│           Post-Approval Workflow             │
│                                              │
│  check_approval → run_execution → finalize   │
└──────────────────────────────────────────────┘
```

## Agents

### Investigation (読み取り専用 — 20 agents)

| Agent | 対象 |
|-------|------|
| server | サーバー情報 (名前、メンバー数、機能など) |
| channel | テキスト/ボイス/ステージチャンネル (`permissions_synced` 含む) |
| category | カテゴリ |
| thread | スレッド |
| forum | フォーラムチャンネル |
| message | メッセージ |
| role | ロール |
| permission | チャンネル権限上書き |
| member | メンバー情報 |
| vc | ボイスチャンネルの状態・権限同期 |
| stage | ステージインスタンス |
| event | スケジュール済みイベント |
| automod | AutoMod ルール |
| invite | 招待リンク |
| webhook | Webhook |
| emoji | 絵文字 |
| sticker | スタンプ |
| soundboard | サウンドボード |
| audit_log | 監査ログ |
| poll | 投票 |

### Execution (書き込み — 承認必須, 19 agents)

| Agent | アクション |
|-------|-----------|
| server | name, description, icon, banner, verification_level, system/rules/safety/afk/public_updates channels, content_filter, notification_level |
| channel | create, edit, delete, reorder, clone |
| category | create, edit, delete |
| thread | create, create_from_message, edit, delete, archive, lock, add/remove member, join, leave |
| forum | create/edit/delete posts, create/edit/delete tags, create/edit/delete forum channel |
| message | send, reply, edit, delete, pin, unpin, reactions, bulk_delete, crosspost, suppress_embeds |
| role | create, edit, delete, reorder, assign, revoke |
| permission | set, clear, sync, move_to_category |
| member | edit_nickname, edit_roles, timeout, kick (with DM), ban (with DM), unban |
| vc | move, mute, unmute, deafen, undeafen, disconnect, edit |
| stage | create/end instance, update topic, edit channel |
| event | create, edit, delete |
| automod | create, edit, delete rules |
| invite | create, delete |
| webhook | create, edit, delete, execute |
| emoji | create (URL / メッセージ添付), edit, delete |
| sticker | create (URL / メッセージ添付), edit, delete |
| soundboard | create (URL / メッセージ添付, 自動5秒切り捨て), edit, delete |
| poll | create, end |

## Getting Started

### 必要なもの

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) (推奨) または pip
- Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))
- LLM API キー (OpenAI / Anthropic / OpenAI互換)

### セットアップ

```bash
# Clone
git clone https://github.com/<your-repo>/dicord-chat.git
cd dicord-chat

# 依存関係のインストール
uv sync
# または: pip install -r requirements.txt

# 環境設定
cp .env.example .env
```

`.env` を編集して認証情報を設定:

```env
DISCORD_TOKEN=your_bot_token
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=your_api_key
```

### 環境変数

| 変数 | 必須 | デフォルト | 説明 |
|------|------|------------|------|
| `DISCORD_TOKEN` | はい | — | Discord bot token |
| `LLM_API_KEY` | はい | — | OpenAI または Anthropic API キー |
| `LLM_MODEL` | はい | — | モデル名 (例: `gpt-4o`, `claude-sonnet-4-20250514`) |
| `LLM_PROVIDER` | いいえ | `openai` | `openai` または `anthropic` |
| `LLM_BASE_URL` | いいえ | — | カスタム API ベース URL (OpenAI互換) |
| `DATABASE_URL` | いいえ | `sqlite:///database/bot.db` | SQLite 接続文字列 |

### 起動

```bash
uv run python bot.py
```

### Docker

```bash
docker compose up -d --build
```

## Commands

| コマンド | 説明 |
|----------|------|
| `/manage <request>` | 自然言語でサーバー管理をリクエスト |
| `/help` | コマンド一覧 |
| `/ping` | レイテンシ確認 |

## Testing

```bash
uv run pytest
```

553 tests covering all investigation/execution agents and workflow logic.

## Project Structure

```
bot.py                  # エントリーポイント
agents/
  base.py               # エージェント基底クラス
  main_agent.py         # オーケストレーター (LLM プランナー)
  prompts.py            # LLM プロンプト
  registry.py           # エージェント動的ローダー
  log.py                # リクエストログ (JSONL)
  investigation/        # 20 調査エージェント
  execution/            # 19 実行エージェント
graph/
  state.py              # AgentState TypedDict
  workflow.py           # LangGraph ワークフロー定義
  llm.py                # LLM ファクトリ
cogs/
  agent_cog.py          # /manage コマンド + 承認UI
  general.py            # /help, /ping
database/               # SQLite (会話履歴, 承認記録)
services/               # 添付ファイルDL, 音声処理, メッセージ検索
locales/
  en.json               # English
  ja.json               # 日本語
i18n.py                 # 翻訳モジュール
formatters/
  response.py           # レスポンス整形
tests/                  # 553 tests
```

## License

Apache License 2.0 — see [LICENSE.md](LICENSE.md)
