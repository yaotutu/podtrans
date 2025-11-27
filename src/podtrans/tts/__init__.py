"""TTS (Text-to-Speech) module for podcast audio generation."""

from podtrans.tts.base import TTSService
from podtrans.tts.schemas import SpeakerConfig, TTSResult
from podtrans.tts.soulx.client import SoulXClient

__all__ = ["TTSService", "SpeakerConfig", "TTSResult", "SoulXClient"]
