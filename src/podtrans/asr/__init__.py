"""ASR (Automatic Speech Recognition) module.

This module provides WhisperX-based ASR with speaker diarization.
"""

from podtrans.asr.schemas import ASRResult, Segment, Word
from podtrans.asr.whisperx_handler import WhisperXHandler

__all__ = [
    "ASRResult",
    "Segment",
    "Word",
    "WhisperXHandler",
]
