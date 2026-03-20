# AI Discord Server Manager

An LLM-powered Discord server management bot built with LangGraph. Send natural language requests and the bot handles investigation, planning, approval, and execution automatically.

**日本語版**: [README_ja.md](README_ja.md)

## Features

- **Natural Language Interface** — Request server management in Japanese or English (e.g. `/manage チャンネルを作って`)
- **Investigation / Execution Separation** — Read-only investigation agents and write execution agents are fully separated
- **Approval Flow** — Shows targets and details before execution with approve/reject buttons. SHA-256 tamper detection on todos
- **Permission Checks** — Each execution action maps to required Discord permissions. Insufficient permissions are auto-blocked
- **Iterative Planning** — LLM planner loops up to 5 times to gather investigation results and build optimal execution plans
- **Conversation History** — Maintains context across the last 5 turns
- **i18n** — Japanese (ja) / English (en) support
- **Media Support** — Create emojis, stickers, soundboard sounds, and server icons/banners from URLs or Discord message attachments. Auto-extracts IDs from message links
- **Audio Processing** — Truncates audio to 5 seconds for soundboard via PyAV (MP3 stream copy / libmp3lame re-encode auto-detection)
- **Ban/Kick DM Notifications** — Sends embed with server name, reason, and message to the target (silently ignores blocked DMs)

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

### Investigation (read-only — 20 agents)

| Agent | Description |
|-------|-------------|
| server | Server info (name, member count, features, etc.) |
| channel | Text/voice/stage channels (includes `permissions_synced`) |
| category | Categories |
| thread | Threads |
| forum | Forum channels |
| message | Messages |
| role | Roles |
| permission | Channel permission overwrites |
| member | Member info |
| vc | Voice channel state, current members, permission sync status |
| stage | Stage instances |
| event | Scheduled events |
| automod | AutoMod rules |
| invite | Invite links |
| webhook | Webhooks |
| emoji | Custom emojis |
| sticker | Stickers |
| soundboard | Soundboard sounds |
| audit_log | Audit log |
| poll | Polls |

### Execution (write — requires approval, 19 agents)

| Agent | Actions |
|-------|---------|
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
| emoji | create (URL / message attachment), edit, delete |
| sticker | create (URL / message attachment), edit, delete |
| soundboard | create (URL / message attachment, auto 5s truncate), edit, delete |
| poll | create, end |

## Getting Started

### Prerequisites

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A Discord Bot Token ([Discord Developer Portal](https://discord.com/developers/applications))
- An LLM API key (OpenAI, Anthropic, or OpenAI-compatible endpoint)

### Setup

```bash
# Clone
git clone https://github.com/<your-repo>/dicord-chat.git
cd dicord-chat

# Install dependencies
uv sync
# or: pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

Edit `.env` with your credentials:

```env
DISCORD_TOKEN=your_bot_token
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=your_api_key
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | — | Discord bot token |
| `LLM_API_KEY` | Yes | — | OpenAI or Anthropic API key |
| `LLM_MODEL` | Yes | — | Model name (e.g. `gpt-4o`, `claude-sonnet-4-20250514`) |
| `LLM_PROVIDER` | No | `openai` | `openai` or `anthropic` |
| `LLM_BASE_URL` | No | — | Custom API base URL (OpenAI-compatible) |
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
| `/manage <request>` | Natural language server management request |
| `/help` | Command list |
| `/ping` | Latency check |

## Testing

```bash
uv run pytest
```

553 tests covering all investigation/execution agents and workflow logic.

## Project Structure

```
bot.py                  # Entry point
agents/
  base.py               # Agent base classes
  main_agent.py         # Orchestrator (LLM planner)
  prompts.py            # LLM prompt templates
  registry.py           # Dynamic agent loader
  log.py                # Request log (JSONL)
  investigation/        # 20 investigation agents
  execution/            # 19 execution agents
graph/
  state.py              # AgentState TypedDict
  workflow.py           # LangGraph workflow definition
  llm.py                # LLM factory (OpenAI / Anthropic)
cogs/
  agent_cog.py          # /manage command + approval UI
  general.py            # /help, /ping
database/               # SQLite (conversation history, approval records)
services/               # Attachment download, audio processing, message search
locales/
  en.json               # English
  ja.json               # Japanese
i18n.py                 # Translation module
formatters/
  response.py           # Response formatting
tests/                  # 553 tests
```

## License

Apache License 2.0 — see [LICENSE.md](LICENSE.md)
