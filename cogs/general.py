import discord
from discord.ext import commands
from discord.ext.commands import Context

from i18n import t, get_locale_from_ctx


class General(commands.Cog, name="general"):
    """汎用コマンドを提供するCog。"""

    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.hybrid_command(
        name="help", description="List all commands the bot has loaded."
    )
    async def help(self, context: Context) -> None:
        """全コマンドの一覧を表示する。"""
        locale = get_locale_from_ctx(context)
        embed = discord.Embed(
            title=t("ui.help_title", locale=locale),
            description=t("ui.help_description", locale=locale),
            color=0xBEBEFE,
        )
        for i in self.bot.cogs:
            cog = self.bot.get_cog(i.lower())
            commands = cog.get_commands()
            data = []
            for command in commands:
                description = command.description.partition("\n")[0]
                data.append(f"{command.name} - {description}")
            help_text = "\n".join(data)
            embed.add_field(
                name=i.capitalize(), value=f"```{help_text}```", inline=False
            )
        await context.send(embed=embed)

    @commands.hybrid_command(
        name="ping",
        description="Check if the bot is alive.",
    )
    async def ping(self, context: Context) -> None:
        """ボットの応答速度を確認する。"""
        locale = get_locale_from_ctx(context)
        embed = discord.Embed(
            title=t("ui.ping_title", locale=locale),
            description=t("ui.ping_latency", locale=locale, latency=round(self.bot.latency * 1000)),
            color=0xBEBEFE,
        )
        await context.send(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(General(bot))
