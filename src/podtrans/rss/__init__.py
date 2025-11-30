"""RSS module for podcast feed processing and episode downloading.

This module provides functionality to:
- Parse RSS feeds and extract podcast episode information
- Download audio files from podcast episodes
- Integrate with the existing PodTrans pipeline
"""

from .schemas import PodcastEpisode, RSSFeed, RSSProcessingResult

__all__ = ["PodcastEpisode", "RSSFeed", "RSSProcessingResult"]