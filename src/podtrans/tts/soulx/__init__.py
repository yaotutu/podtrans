"""SoulX-Podcast TTS service adapter."""

from podtrans.tts.soulx.client import SoulXClient
from podtrans.tts.soulx.converter import SoulXConverter

__all__ = ["SoulXClient", "SoulXConverter"]
