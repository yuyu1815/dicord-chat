# AI Discord Server Manager

LLM + LangGraph で動く Discord サーバー管理ボット。自然言語でリクエストを投げると、ボットが調査・計画・承認・実行のフローで自動的にサーバー管理タスクをこなす。

## Features

- **自然言語インターフェース** — `/manage チャンネルを作って` のように日本語/英語でリクエスト可能
- **調査・実行の分離** — 読み取り専用の調査エージェントと、書き込みの実行エージェントが完全に分離
- **承認フロー** — 実行前に対象と内容を表示し、ボタンで承認/拒否。todos の改ざん検出 (SHA-256) 付き
- **権限チェック** — 実行エージェントの各アクションに必要な Discord 権限をマッピング。権限不足のアクションは自動ブロック
- **反復的計画** — LLM プランナーが最大 5 回のループで調査結果を収集し、最適な実行計画を立案
- **会話履歴** — 直近 5 ターンのコンテキストで文脈を維持
- **i18n** — 日本語 (ja) / 英語 (en) 対応
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
| channel | テキスト/ボイス/ステージチャンネル |
| category | カテゴリ |
| thread | スレッド |
| forum | フォーラムチャンネル |
| message | メッセージ |
| role | ロール |
| permission | チャンネル権限上書き |
| member | メンバー情報 |
| vc | ボイスチャンネルの状態 |
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
| emoji | create, edit, delete |
| sticker | create, edit, delete |
| soundboard | create, edit, delete |
| poll | create, end |

## Getting Started

### Prerequisites

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) (recommended)
- Discord Bot Token
- OpenAI or Anthropic API Key

### Setup

```bash
# Clone
git clone https://github.com/<your-repo>/dicord-chat.git
cd dicord-chat

# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env with your tokens
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | — | Discord bot token |
| `LLM_API_KEY` | Yes | — | OpenAI or Anthropic API key |
| `LLM_MODEL` | Yes | — | Model name (e.g. `gpt-4o`, `claude-sonnet-4-20250514`) |
| `LLM_PROVIDER` | No | `openai` | `openai` or `anthropic` |
| `LLM_BASE_URL` | No | — | Custom API base URL |
| `DATABASE_URL` | No | `sqlite:///database/bot.db` | SQLite connection string |

### Run

```bash
uv run python bot.py
```

### Docker

```bash
docker compose up -d --build
```

## Commands

| Command | Description |
|---------|-------------|
| `/manage <request>` | 自然言語でサーバー管理をリクエスト |
| `/help` | コマンド一覧 |
| `/ping` | レイテンシ確認 |

## Testing

```bash
uv run pytest
```

514 tests covering all investigation/execution agents and workflow logic.

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
locales/
  en.json               # English
  ja.json               # 日本語
i18n.py                 # 翻訳モジュール
formatters/
  response.py           # レスポンス整形
tests/                  # 514 tests
```

## License

Apache License 2.0 — see [LICENSE.md](LICENSE.md)
