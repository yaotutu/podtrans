"""RSS feed fetcher and parser using feedparser library.

This module provides functionality to fetch and parse RSS feeds, extracting
podcast episode information in a structured format compatible with the pipeline.
"""

import re
from datetime import datetime
from typing import Optional, List

import feedparser
import httpx
from loguru import logger

from podtrans.config import get_settings
from podtrans.rss.schemas import PodcastEpisode, RSSFeed


class RSSFetcher:
    """RSS feed fetcher and parser.

    This class handles fetching RSS feeds from URLs and parsing them
    to extract podcast episode information using the feedparser library.
    """

    def __init__(self):
        """Initialize the RSS fetcher with default settings."""
        self.settings = get_settings()

    def fetch_feed(self, feed_url: str, max_episodes: int = 1) -> RSSFeed:
        """Fetch and parse an RSS feed synchronously.

        Args:
            feed_url: URL of the RSS feed to fetch
            max_episodes: Maximum number of episodes to extract (default: 1)

        Returns:
            RSSFeed object containing feed information and episodes

        Raises:
            httpx.HTTPError: If the HTTP request fails
            ValueError: If the feed cannot be parsed or is invalid
        """
        logger.info(f"Fetching RSS feed: {feed_url}")
        logger.info(f"Max episodes to extract: {max_episodes}")

        try:
            # Prepare HTTP request with proper headers
            headers = {
                "User-Agent": self.settings.rss_user_agent,
                "Accept": "application/rss+xml, application/xml, text/xml",
            }

            # Fetch RSS feed content
            with httpx.Client(timeout=self.settings.rss_timeout) as client:
                response = client.get(feed_url, headers=headers)
                response.raise_for_status()

                logger.debug(f"RSS feed fetched successfully, size: {len(response.content)} bytes")

                # Parse RSS content with feedparser
                feed_data = feedparser.parse(response.content)

                # Check for parsing errors
                if feed_data.bozo and feed_data.bozo_exception:
                    logger.warning(f"Feed may be malformed: {feed_data.bozo_exception}")

                # Convert feedparser data to our models
                rss_feed = self._convert_feed_data(feed_data, feed_url, max_episodes)

                logger.info(
                    f"Successfully parsed RSS feed '{rss_feed.title}' with {rss_feed.total_episodes} episodes"
                )
                return rss_feed

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching RSS feed {feed_url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch or parse RSS feed {feed_url}: {e}")
            raise ValueError(f"RSS feed processing failed: {e}")

    def _convert_feed_data(
        self, feed_data: feedparser.FeedParserDict, feed_url: str, max_episodes: int
    ) -> RSSFeed:
        """Convert feedparser data to RSSFeed model.

        Args:
            feed_data: Raw feedparser data
            feed_url: Original feed URL
            max_episodes: Maximum episodes to include

        Returns:
            RSSFeed object with structured episode data
        """
        # Extract basic feed information
        feed_info = feed_data.feed
        feed_title = feed_info.get('title', 'Unknown Feed')
        feed_description = feed_info.get('description', '')
        feed_language = feed_info.get('language', '')

        logger.debug(f"Processing feed: {feed_title}")

        # Extract and process episodes
        episodes = []
        total_entries = len(feed_data.entries)

        logger.debug(f"Found {total_entries} total entries in feed")

        # Sort entries by publication date (newest first)
        sorted_entries = sorted(
            feed_data.entries,
            key=lambda x: self._parse_entry_date(x),
            reverse=True,
        )

        # Process only the requested number of episodes
        entries_to_process = sorted_entries[:max_episodes]

        for i, entry in enumerate(entries_to_process):
            try:
                logger.debug(f"Processing entry {i+1}/{len(entries_to_process)}: {entry.get('title', 'Unknown')}")

                # Extract audio URL from enclosure
                audio_url = self._extract_audio_url(entry)
                if not audio_url:
                    logger.warning(f"No audio URL found for episode: {entry.get('title', 'Unknown')}")
                    continue

                # Parse publication date
                pub_date = self._parse_entry_date(entry)
                if not pub_date:
                    logger.warning(f"No valid publication date for episode: {entry.get('title', 'Unknown')}")
                    pub_date = datetime.now()

                # Parse duration
                duration = self._parse_duration(entry.get('itunes_duration'))

                # Parse file size
                size = self._parse_file_size(entry)

                # Create episode object
                episode = PodcastEpisode(
                    title=entry.get('title', 'Unknown Episode'),
                    description=entry.get('summary', entry.get('description', '')),
                    audio_url=audio_url,
                    pub_date=pub_date,
                    duration=duration,
                    size=size,
                    guid=self._extract_guid(entry, audio_url),
                    author=entry.get('author', entry.get('itunes_author', '')),
                    image_url=self._extract_image_url(entry),
                )

                episodes.append(episode)
                logger.debug(f"Successfully processed episode: {episode.title}")

            except Exception as e:
                logger.warning(f"Failed to process episode {entry.get('title', 'Unknown')}: {e}")
                continue

        # Create and return RSS feed object
        rss_feed = RSSFeed(
            title=feed_title,
            description=feed_description or None,
            link=feed_url,
            language=feed_language or None,
            last_updated=datetime.now(),
            episodes=episodes,
        )

        # Ensure episodes are sorted by date
        rss_feed.sort_episodes_by_date()

        logger.info(f"Converted feed data: {len(episodes)} episodes processed successfully")
        return rss_feed

    def _extract_audio_url(self, entry: feedparser.FeedParserDict) -> Optional[str]:
        """Extract audio URL from RSS entry.

        Args:
            entry: RSS entry from feedparser

        Returns:
            Audio URL string or None if not found
        """
        # Method 1: Check enclosure (most common for podcasts)
        if hasattr(entry, 'enclosure') and entry.enclosure:
            enclosure_type = getattr(entry.enclosure, 'type', '').lower()
            # Check if it's an audio file
            if any(audio_type in enclosure_type for audio_type in ['audio', 'mpeg', 'mp3']):
                url = getattr(entry.enclosure, 'href', '')
                if url:
                    return url

        # Method 2: Check for media content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if getattr(media, 'type', '').lower().startswith('audio/'):
                    url = getattr(media, 'url', '')
                    if url:
                        return url

        # Method 3: Look for audio URLs in links
        if hasattr(entry, 'links') and entry.links:
            for link in entry.links:
                link_type = getattr(link, 'type', '').lower()
                if any(audio_type in link_type for audio_type in ['audio', 'mpeg', 'mp3']):
                    url = getattr(link, 'href', '')
                    if url:
                        return url

        return None

    def _extract_guid(self, entry: feedparser.FeedParserDict, fallback_url: str) -> str:
        """Extract unique identifier for the episode.

        Args:
            entry: RSS entry from feedparser
            fallback_url: Audio URL to use as fallback

        Returns:
            Unique GUID string
        """
        # Try standard GUID first
        guid = getattr(entry, 'id', '')
        if guid and guid.strip():
            return guid.strip()

        # Try link
        link = getattr(entry, 'link', '')
        if link and link.strip():
            return link.strip()

        # Fallback to audio URL
        return fallback_url

    def _extract_image_url(self, entry: feedparser.FeedParserDict) -> Optional[str]:
        """Extract episode image URL if available.

        Args:
            entry: RSS entry from feedparser

        Returns:
            Image URL string or None if not found
        """
        # Method 1: iTunes image
        if hasattr(entry, 'itunes_image'):
            itunes_image = getattr(entry.itunes_image, 'href', None)
            if itunes_image:
                return itunes_image

        # Method 2: Media thumbnail
        if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
            thumbnail = entry.media_thumbnail[0] if entry.media_thumbnail else None
            if thumbnail:
                url = getattr(thumbnail, 'url', '')
                if url:
                    return url

        # Method 3: Standard image
        if hasattr(entry, 'image'):
            image = getattr(entry.image, 'href', None) if hasattr(entry.image, 'href') else None
            if image:
                return image

        return None

    def _parse_entry_date(self, entry: feedparser.FeedParserDict) -> Optional[datetime]:
        """Parse publication date from RSS entry.

        Args:
            entry: RSS entry from feedparser

        Returns:
            datetime object or None if parsing fails
        """
        # Try multiple date fields in order of preference
        date_fields = [
            'published_parsed',
            'updated_parsed',
        ]

        for field in date_fields:
            date_tuple = getattr(entry, field, None)
            if date_tuple and len(date_tuple) >= 6:
                try:
                    # feedparser returns time.struct_time
                    return datetime(*date_tuple[:6])
                except (ValueError, TypeError) as e:
                    logger.debug(f"Failed to parse date from {field}: {e}")
                    continue

        return None

    def _parse_duration(self, duration_str) -> Optional[float]:
        """Parse episode duration from various formats.

        Args:
            duration_str: Duration string from RSS (can be HH:MM:SS, MM:SS, or seconds)

        Returns:
            Duration in seconds or None if parsing fails
        """
        if not duration_str:
            return None

        try:
            duration_str = str(duration_str).strip()

            # Format 1: HH:MM:SS
            if ':' in duration_str and duration_str.count(':') == 2:
                parts = duration_str.split(':')
                if len(parts) == 3:
                    hours, minutes, seconds = map(int, parts)
                    return hours * 3600 + minutes * 60 + seconds

            # Format 2: MM:SS
            elif ':' in duration_str and duration_str.count(':') == 1:
                parts = duration_str.split(':')
                if len(parts) == 2:
                    minutes, seconds = map(int, parts)
                    return minutes * 60 + seconds

            # Format 3: Plain seconds (integer)
            elif duration_str.isdigit():
                return float(duration_str)

            # Format 4: Try to extract numbers from string
            else:
                # Look for patterns like "1:23:45" or "45:67"
                match = re.search(r'(\d{1,2}):(\d{2})(?::(\d{2}))?', duration_str)
                if match:
                    groups = match.groups()
                    if groups[2]:  # HH:MM:SS
                        hours, minutes, seconds = map(int, groups[:3])
                        return hours * 3600 + minutes * 60 + seconds
                    else:  # MM:SS
                        minutes, seconds = map(int, groups[:2])
                        return minutes * 60 + seconds

        except (ValueError, AttributeError) as e:
            logger.debug(f"Failed to parse duration '{duration_str}': {e}")

        return None

    def _parse_file_size(self, entry: feedparser.FeedParserDict) -> Optional[int]:
        """Parse file size from RSS entry.

        Args:
            entry: RSS entry from feedparser

        Returns:
            File size in bytes or None if not found
        """
        # Check enclosure size
        if hasattr(entry, 'enclosure') and entry.enclosure:
            size = getattr(entry.enclosure, 'length', None)
            if size:
                try:
                    return int(size)
                except (ValueError, TypeError):
                    pass

        # Check media content size
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                size = getattr(media, 'fileSize', None)
                if size:
                    try:
                        return int(size)
                    except (ValueError, TypeError):
                        continue

        return None

    def validate_feed_url(self, feed_url: str) -> bool:
        """Validate that a URL looks like a valid RSS feed URL.

        Args:
            feed_url: URL to validate

        Returns:
            True if URL appears valid, False otherwise
        """
        if not feed_url or not feed_url.strip():
            return False

        # Basic URL format check
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$',
            re.IGNORECASE,
        )

        if not url_pattern.match(feed_url):
            return False

        return True