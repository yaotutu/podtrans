"""Pipeline orchestration module.

This module provides the base interfaces and orchestration logic for
connecting ASR, Translation, and TTS modules into a complete pipeline.
"""

from podtrans.pipeline.base import PipelineStage

__all__ = ["PipelineStage"]
