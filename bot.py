import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_bot")


class DiscordBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix=os.getenv("PREFIX", "!"),
            intents=intents,
            help_command=None,
        )
        self.logger = logger

    async def setup_hook(self) -> None:
        for file in os.listdir("cogs"):
            if file.endswith(".py"):
                await self.load_extension(f"cogs.{file[:-3]}")
                self.logger.info(f"Loaded extension '{file[:-3]}'")

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user or message.author.bot:
            return
        await self.process_commands(message)


bot = DiscordBot()
bot.run(os.getenv("TOKEN"))
