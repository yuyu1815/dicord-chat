# AGENTS.md: AI-Driven Development Guidelines for Extreme Readability

## 1. 目的 (Purpose)

本ドキュメントは、AI（LLM）を活用したコード生成およびリファクタリングにおいて、**「不要な後方互換性の維持によるコードの肥大化」を防ぎ、人間の認知負荷を極限まで下げる（査読性を高める）**ための戦略と規約を定義する。

AIは本質的に「既存のコードを壊さないよう継ぎ足す」バイアスを持つ。我々はこのバイアスを意図的なプロンプト設計によって打破し、常にゼロベースで最適化された美しいコードを要求する。

## 2. 根本原則 (Core Principles)

AIエージェント、およびAIを操作するエンジニアは以下の原則を遵守すること。

- **互換性よりシンプルさ (Simplicity over Compatibility):**
  既存のスパゲッティコードやレガシーなインターフェースに引きずられてはならない。必要であれば既存のシグネチャ（引数・戻り値）を破壊し、現在最も美しくシンプルな形を再提案せよ。

- **完璧な未来より、シンプルな現在 (YAGNI & Done is better than perfect):**
  「将来使うかもしれない」という理由で汎用的なラッパーや過剰な抽象化（AHA: Avoid Hasty Abstractions）を行わない。現在の要件を最短距離で解決するコードのみを記述する。

- **認知負荷の最小化 (Minimize Cognitive Load):**
  コードを読む際、人間が「記憶」しなければならない状態（ミュータブルな変数、深いネスト、暗黙のコンテキスト）を徹底的に排除する。

## 3. AIプロンプト戦略 (Prompting Strategies to Prevent Bloat)

AIにコードを生成・修正させる際は、以下の戦略（プロンプトパターン）を用いて肥大化を防ぐこと。

### 3.1 ゼロベース再構築 (Zero-Based Rewrite)

既存コードの「修正」を依頼してはならない。ロジックだけを抽出し、ゼロから書かせる。


### 3.2 制約駆動プロンプト (Constraint-Based Prompting)

AIの自由度を物理的な制約で縛り、強制的にシンプルに保つ。

### 3.3 インターフェース先行合意 (Interface-First Design)

いきなり実装を書かせず、まずは「外側」の設計から合意をとる。

### 3.4 テスト駆動生成 (Test-Driven Generation)

既存コードを渡す代わりに、「期待する入出力（テストケース）」のみを渡し、それを満たす最短のコードを書かせる。

## 4. 極限の査読性を担保するコーディング規約 (Coding Standards)

AIが出力するコード、および人間がレビューするコードは、以下の規約を満たしていなければならない。

### 4.1 制御フローの簡素化

- **早期リターン (Guard Clauses):** 異常系、エッジケースは関数の冒頭で `if` で弾き、即座に `return` または例外をスローする。`else` 句は原則として使用を禁止する。
- **テーブル駆動 (Table-Driven Methods):** 3つ以上の `if/elif` や `switch` 文は、辞書（Map/Dict）を用いたマッピング処理に置き換え、ロジックをデータ構造に変換する。
- **肯定形の条件式:** 二重否定（例: `!isNotHidden`）を禁止し、直感的に読める肯定形の変数名・条件式を強制する。

### 4.2 状態とデータの管理

- **ミュータブルの排除:** 一度宣言した変数の再代入（`count = count + 1` など）を極力避ける。状態の変更ではなく、新しいデータを返す関数（純粋関数）として設計する。
- **プリミティブ型への執着の排除:** 単なる文字列や整数ではなく、意味を持つ値オブジェクト（例: `EmailAddress`, `Money` クラス/構造体）を使用し、型レベルで不正を弾く。
- **フラグ引数の禁止:** 関数の引数に `boolean` (True/False) を渡して振る舞いを変えてはならない。フラグが必要な場合は、関数を2つに分割する。

### 4.3 命名とドキュメンテーション

- **ユビキタス言語:** 業務ドメインで使われる言葉とコード内のクラス名・変数名を完全に一致させる。
- **Whyを語るコメント:** コードを読めば分かる「何をしているか(What)」のコメントはLinterで警告対象とする。「なぜその実装・数値を選んだのか(Why)」というコンテキストのみをコメントとして残す。
- **対称性の維持:** `start/stop`, `add/remove`, `open/close` など、対になる処理の命名規則をシステム全体で完全に統一する。

## 5. レビュー・チェックリスト (Code Review Checklist)

PR（プルリクエスト）をマージする前に、以下の問いに全て「Yes」と答えられるか確認すること。

- [ ] そのコードは、事前知識のないエンジニアが「10秒」読んで意図を理解できるか？
- [ ] 既存の歪んだインターフェースに合わせるための、無駄なラッパー関数や変換処理が存在していないか？
- [ ] 「将来必要になるかもしれない」という理由だけで追加された不要なロジックはないか？
- [ ] 例外処理は、エラーを握りつぶさず（フェイルファスト）、上位層で一元的にハンドリングされるようになっているか？

---

# Discord Bot — 設計書

## 概要

Discord上での管理操作および対話処理を行うマルチエージェントシステム。
LangGraphによる状態管理とフロー制御、discord.pyによるDiscord API連携。

**基本原則:** 調査と実行を分離し、実行は必ずユーザー許可後に行う。

---

## 技術スタック

| レイヤー | 技術 | 理由 |
|---------|------|------|
| フレームワーク | discord.py 2.7+ | 最新のDiscord API対応 |
| エージェント基盤 | LangGraph | 状態管理・フロー制御・マルチエージェント協調 |
| LLM連携 | langchain | LangGraphとの統合、モデル抽象化 |
| パッケージ管理 | uv | 高速な依存解決、lockfile管理 |
| 環境変数 | python-dotenv | .envファイルによる設定管理 |
| データベース | SQLite | 軽量、設定不要、許可状態管理 |
| ログ | logging | 標準ライブラリ、シンプルな構成 |

### アーキテクチャ原則

**本プロジェクトは「最小構成」を維持する。**

- 過剰な抽象化、将来の拡張性を見越した機能は追加しない
- 現在必要な機能のみを実装する（YAGNI）
- 複雑な状態管理、キャッシュレイヤー、複数DB接続は避ける

---

## エージェントアーキテクチャ

### 基本構造

```
┌─────────────────────────────────────────────────────────────┐
│                       メインAgent                            │
│  (依頼受付・解析・Todo生成・振り分け・結果集約・許可フロー)    │
└─────────────────────┬───────────────────────────────────────┘
                      │
         ┌────────────┴────────────┐
         │                         │
         ▼                         ▼
┌─────────────────┐       ┌─────────────────┐
│  調査Agent群    │       │  実行Agent群     │
│  (読み取り専用) │       │  (許可後実行)    │
└─────────────────┘       └─────────────────┘
```

### Agent種別

**調査Agent（InvestigationAgent）**
- 情報取得、状態確認、分析、整理、実行候補の提示
- 変更操作は行わない
- 対象ごとに分離（サーバー/チャンネル/ロール/メンバー等）

**実行Agent（ExecutionAgent）**
- 作成、変更、削除、その他管理操作
- 単独では動作せず、ユーザーの明示的な許可後にのみ実行
- 対象ごとに分離（サーバー/チャンネル/ロール/メンバー等）

### 対象領域一覧

| 対象 | 調査Agent | 実行Agent | 主な操作 |
|------|-----------|-----------|----------|
| サーバー | ✅ | ✅ | 設定変更、構成変更 |
| チャンネル | ✅ | ✅ | 作成/変更/削除 |
| カテゴリー | ✅ | ✅ | 作成/変更/削除 |
| スレッド | ✅ | ✅ | 作成/アーカイブ/ロック |
| フォーラム | ✅ | ✅ | 投稿作成/削除 |
| メッセージ | ✅ | ✅ | 送信/編集/削除/ピン |
| ロール | ✅ | ✅ | 作成/変更/付与/剥奪 |
| 権限 | ✅ | ✅ | Overwrite変更 |
| メンバー | ✅ | ✅ | タイムアウト/Kick/Ban |
| VC | ✅ | ✅ | 移動/ミュート/デフ |
| Stage | ✅ | ✅ | 設定変更/制御 |
| イベント | ✅ | ✅ | 作成/変更/削除 |
| AutoMod | ✅ | ✅ | ルール作成/変更 |
| 招待リンク | ✅ | ✅ | 作成/無効化 |
| Webhook | ✅ | ✅ | 作成/削除 |
| 絵文字 | ✅ | ✅ | 追加/削除 |
| ステッカー | ✅ | ✅ | 追加/削除 |
| サウンドボード | ✅ | ✅ | 追加/削除 |
| 監査ログ | ✅ | ❌ | 取得のみ（読み取り専用） |

---

## LangGraphフロー定義

### 状態（State）

```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    request: str                    # ユーザーからの依頼
    todos: list[str]                 # 分解されたTodoリスト
    investigation_results: dict      # 調査結果
    execution_candidates: list       # 実行候補
    approval_id: str | None          # 許可ID
    approved: bool                    # ユーザー許可状態
    execution_results: dict          # 実行結果
    final_response: str               # 最終応答
```

### グラフ構造

```python
from langgraph.graph import StateGraph, END

workflow = StateGraph(AgentState)

# ノード定義
workflow.add_node("parse_request", parse_request_node)
workflow.add_node("decompose_todos", decompose_todos_node)
workflow.add_node("route_investigation", route_investigation_node)
workflow.add_node("aggregate_results", aggregate_results_node)
workflow.add_node("request_approval", request_approval_node)
workflow.add_node("execute_actions", execute_actions_node)
workflow.add_node("summarize", summarize_node)

# エッジ定義
workflow.set_entry_point("parse_request")
workflow.add_edge("parse_request", "decompose_todos")
workflow.add_edge("decompose_todos", "route_investigation")
workflow.add_edge("route_investigation", "aggregate_results")
workflow.add_edge("aggregate_results", "request_approval")

# 条件分岐（許可待ち）
workflow.add_conditional_edges(
    "request_approval",
    lambda state: "execute" if state["approved"] else END,
    {"execute": "execute_actions", END: END}
)

workflow.add_edge("execute_actions", "summarize")
workflow.add_edge("summarize", END)
```

---

## プロジェクト構成

```
.
├── bot.py                    # エントリーポイント
├── agents/
│   ├── __init__.py
│   ├── main_agent.py         # メインAgent（司令塔）
│   ├── investigation/        # 調査Agent群
│   │   ├── __init__.py
│   │   ├── server.py
│   │   ├── channel.py
│   │   ├── role.py
│   │   └── ...
│   └── execution/             # 実行Agent群
│       ├── __init__.py
│       ├── server.py
│       ├── channel.py
│       └── ...
├── graph/
│   ├── __init__.py
│   ├── state.py              # State定義
│   ├── nodes.py              # ノード定義
│   └── workflow.py           # LangGraphワークフロー
├── cogs/
│   └── agent_cog.py          # Discord Bot Cog（UI連携）
├── database/
│   ├── __init__.py
│   └── schema.sql            # 許可状態管理等
├── pyproject.toml
├── uv.lock
└── .env
```

## コーディング規約（プロジェクト固有）

### Agent実装パターン

```python
from abc import ABC, abstractmethod
from langgraph.graph import StateGraph

class BaseAgent(ABC):
    """Agent基底クラス"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Agent名"""
        pass
    
    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        """Agent実行"""
        pass


class InvestigationAgent(BaseAgent):
    """調査Agent基底クラス"""
    
    async def run(self, state: AgentState) -> AgentState:
        result = await self._investigate(state)
        state["investigation_results"][self.name] = result
        return state
    
    @abstractmethod
    async def _investigate(self, state: AgentState) -> dict:
        """調査実装（読み取り専用）"""
        pass


class ExecutionAgent(BaseAgent):
    """実行Agent基底クラス"""
    
    async def run(self, state: AgentState) -> AgentState:
        # 許可チェック（ガード節）
        if not state["approved"]:
            raise PermissionError("Execution requires user approval")
        
        result = await self._execute(state)
        state["execution_results"][self.name] = result
        return state
    
    @abstractmethod
    async def _execute(self, state: AgentState) -> dict:
        """実行実装（変更操作）"""
        pass
```

### Discord Cogでの連携

```python
class AgentCog(commands.Cog):
    def __init__(self, bot: commands.Bot, workflow: StateGraph) -> None:
        self.bot = bot
        self.workflow = workflow
    
    @commands.hybrid_command(name="manage")
    async def manage(self, ctx: commands.Context, *, request: str) -> None:
        """管理操作を実行（調査→許可確認→実行）"""
        # 初期状態
        state = AgentState(
            request=request,
            todos=[],
            investigation_results={},
            execution_candidates=[],
            approval_id=None,
            approved=False,
            execution_results={},
            final_response="",
        )
        
        # LangGraph実行（調査のみ）
        result = await self.workflow.ainvoke(state)
        
        # 実行候補を提示し、許可待ちUIを表示
        view = ApprovalView(approval_id=result["approval_id"])
        await ctx.send(result["final_response"], view=view)
```

### 許可フロー（Discord UI）

```python
import discord

class ApprovalView(discord.ui.View):
    def __init__(self, approval_id: str):
        super().__init__(timeout=300)  # 5分タイムアウト
        self.approval_id = approval_id
    
    @discord.ui.button(label="許可", style=discord.ButtonStyle.green)
    async def approve(self, interaction, button):
        # 許可状態をDBに記録
        await self._save_approval(self.approval_id, approved=True)
        # 実行Agentを起動
        await interaction.response.send_message("実行を開始します...")
    
    @discord.ui.button(label="却下", style=discord.ButtonStyle.red)
    async def reject(self, interaction, button):
        await self._save_approval(self.approval_id, approved=False)
        await interaction.response.send_message("操作をキャンセルしました")
```

### エラーハンドリング

- エラーは握りつぶさず、ログに出力する
- ユーザーへのエラーメッセージは簡潔かつ明確に
- 予期しない例外は上位層（Bot全体）でキャッチする
- Agent内のエラーは状態に含めて伝播させる

### 非同期処理

- すべてのI/O操作（Discord API、DB、LLM呼び出し）は非同期で行う
- `asyncio`の機能は必要な場合のみ使用
- LangGraphの`ainvoke`を使用して非同期実行

## 環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| DISCORD_TOKEN | Yes | Discord Botのトークン |
| LLM_PROVIDER | No | LLMプロバイダー（openai/anthropic/local） |
| LLM_MODEL | No | モデル名（デフォルト: provider依存） |
| LLM_API_KEY | Conditional | LLM APIキー（openai/anthropic使用時） |
| DATABASE_URL | No | SQLiteパス（デフォルト: `sqlite:///bot.db`） |

## 起動方法

```bash
# 依存関係のインストール
uv sync

# Botの起動
uv run python bot.py
```

## 機能追加時のチェックリスト

新しいCogやコマンドを追加する前に確認すること：

- [ ] 同じ機能を持つコマンドが既に存在していないか？
- [ ] 機能は本当に「今」必要か？（YAGNI）
- [ ] 3行以上のネストがないか？（ガード節の使用）
- [ ] エラーハンドリングが明示的か？
- [ ] ユーザーに見えるメッセージが簡潔か？

## コミット規約

[Conventional Commits](https://conventionalcommits.org/)に従う：

```
feat: add new moderation cog
fix: handle missing permissions in ban command
refactor: simplify database connection logic
docs: update README with new setup instructions
chore: update dependencies
```
