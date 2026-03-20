import logging
import os

import aiosqlite
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

missing = [k for k in ("DISCORD_TOKEN", "LLM_API_KEY", "LLM_MODEL") if not os.getenv(k)]
if missing:
    raise SystemExit(f"Missing required environment variables: {', '.join(missing)}\nPlease set them in your .env file.")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")


class DiscordBot(commands.Bot):
    """Discordサーバー管理ボット。

    Attributes:
        logger: ロガーインスタンス。
        config: LLM・データベース等の設定辞書。
        main_agent: :class:`MainAgent` インスタンス。LLM未設定時は ``None``。
    """

    def __init__(self) -> None:
        super().__init__(
            command_prefix=os.getenv("PREFIX", "!"),
            intents=intents,
            help_command=None,
        )
        self.logger = logger
        self.config = {
            "llm_provider": os.getenv("LLM_PROVIDER", "openai"),
            "llm_model": os.getenv("LLM_MODEL"),
            "llm_api_key": os.getenv("LLM_API_KEY"),
            "llm_base_url": os.getenv("LLM_BASE_URL"),
            "database_url": os.getenv("DATABASE_URL", "sqlite:///database/bot.db"),
        }

    async def setup_hook(self) -> None:
        """ボット起動時の初期化処理。データベース・LLM・エージェント・Cogを読み込む。"""
        await self._init_database()

        from graph.llm import create_llm
        from agents.main_agent import MainAgent

        try:
            llm = create_llm(
                provider=self.config["llm_provider"],
                model=self.config["llm_model"],
                api_key=self.config["llm_api_key"],
                base_url=self.config["llm_base_url"],
            )
            main_agent = MainAgent(llm)
            self.main_agent = main_agent
        except Exception as e:
            self.logger.warning("LLM not configured, /manage command will not work: %s", e)
            self.main_agent = None

        for file in os.listdir("cogs"):
            if file.endswith(".py"):
                await self.load_extension(f"cogs.{file[:-3]}")
                self.logger.info(f"Loaded extension '{file[:-3]}'")

    async def _init_database(self) -> None:
        """SQLiteデータベースを初期化し、必要なテーブルを作成する。"""
        db_path = self.config["database_url"].replace("sqlite:///", "")
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    approved INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            await db.commit()
        self.logger.info("Database initialized: %s", db_path)

    async def on_message(self, message: discord.Message) -> None:
        """メッセージ受信時にコマンドを処理する。ボット自身のメッセージは無視する。"""
        if message.author == self.user or message.author.bot:
            return
        await self.process_commands(message)


bot = DiscordBot()
bot.run(os.getenv("DISCORD_TOKEN"))
