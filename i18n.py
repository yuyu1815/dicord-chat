"""Lightweight i18n module using JSON translation files."""

import json
import logging
from pathlib import Path
from string import Formatter

import discord
from discord.app_commands import Translator as AppCommandTranslator

logger = logging.getLogger("discord_bot")

_LOCALES_DIR = Path(__file__).resolve().parent / "locales"
_DEFAULT_LOCALE = "en"
_translations: dict[str, dict[str, str]] = {}


class _SafeFormatter(Formatter):
    """Format strings safely by converting all values to str."""

    def format_field(self, value, format_spec):
        return str(value)


_formatter = _SafeFormatter()


def load_translations() -> None:
    """Load all JSON translation files from the locales directory."""
    global _translations
    _translations = {}
    if not _LOCALES_DIR.is_dir():
        logger.warning("Locales directory not found at %s", _LOCALES_DIR)
        return
    for path in _LOCALES_DIR.glob("*.json"):
        locale = path.stem
        try:
            with open(path, encoding="utf-8") as f:
                _translations[locale] = json.load(f)
            logger.info("Loaded %d translation keys for locale '%s'", len(_translations[locale]), locale)
        except Exception as e:
            logger.error("Failed to load translations from %s: %s", path, e)


def t(key: str, *, locale: str = _DEFAULT_LOCALE, **kwargs) -> str:
    """Look up a translation key, falling back to the key itself if not found.

    Args:
        key: Translation key (dot-namespaced or English text for slash commands).
        locale: Language code (e.g., "en", "ja").
        **kwargs: Interpolation values for {placeholder} in the translation string.

    Returns:
        Translated string with placeholders interpolated.
    """
    strings = _translations.get(locale, {})
    if key in strings:
        text = strings[key]
    else:
        default_strings = _translations.get(_DEFAULT_LOCALE, {})
        text = default_strings.get(key, key)
        if locale != _DEFAULT_LOCALE and key not in default_strings:
            logger.debug("Translation key '%s' not found for locale '%s'", key, locale)
    if kwargs:
        try:
            return _formatter.format(text, **kwargs)
        except (KeyError, IndexError):
            logger.warning("Failed to format translation key '%s' with kwargs %s", key, kwargs)
    return text


class DiscordCommandTranslator(AppCommandTranslator):
    """Translator for discord.py slash command metadata (descriptions, etc.)."""

    async def translate(
        self,
        string: discord.app_commands.locale_str,
        locale: discord.Locale,
        context,
    ) -> str | None:
        lang = locale.value.split("-")[0]
        return _translations.get(lang, {}).get(string.message)


def get_locale_from_ctx(ctx) -> str:
    """Extract locale code from a command context.

    Priority: guild_locale > user locale > guild preferred_locale > "en".
    """
    if hasattr(ctx, "interaction") and ctx.interaction:
        guild_locale = getattr(ctx.interaction, "guild_locale", None)
        if guild_locale:
            return guild_locale.value.split("-")[0]
        user_locale = getattr(ctx.interaction, "locale", None)
        if user_locale:
            return user_locale.value.split("-")[0]
    if ctx.guild and hasattr(ctx.guild, "preferred_locale") and ctx.guild.preferred_locale:
        return ctx.guild.preferred_locale.value.split("-")[0]
    return _DEFAULT_LOCALE


# Auto-load translations on module import.
load_translations()
