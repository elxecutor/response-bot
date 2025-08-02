"""
Input Handler - Retrieves data from various sources
"""

import httpx
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from abc import ABC, abstractmethod
import logging
from pathlib import Path

try:
    from .config import SourceConfig
except ImportError:
    from config import SourceConfig

logger = logging.getLogger(__name__)

class DataSource(ABC):
    """Abstract base class for data sources"""
    
    @abstractmethod
    async def fetch_data(self) -> List[Dict[str, Any]]:
        """Fetch data from the source"""
        pass

class TwitterSource(DataSource):
    """Twitter data source implementation"""
    
    def __init__(self, config: SourceConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=30.0)
        self.headers = {
            "Authorization": f"Bearer {config.bearer_token}",
            "Cookie": config.cookie,
            "User-Agent": config.user_agent,
            "X-Csrf-Token": config.csrf_token,
            "Referer": "https://x.com/home"
        }
    
    async def fetch_data(self) -> List[Dict[str, Any]]:
        """Fetch data from Twitter API"""
        try:
            response = await self.client.get(self.config.api_url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            posts = self._extract_posts(data)
            
            logger.info(f"Fetched {len(posts)} posts from Twitter")
            return posts
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching Twitter data: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching Twitter data: {e}")
            return []
    
    def _extract_posts(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract post data from Twitter API response"""
        posts = []
        
        try:
            # Navigate through Twitter API response structure
            # This structure may vary based on the specific Twitter API endpoint
            instructions = data.get('data', {}).get('home', {}).get('home_timeline_urt', {}).get('instructions', [])
            
            for instruction in instructions:
                if instruction.get('type') == 'TimelineAddEntries':
                    entries = instruction.get('entries', [])
                    
                    for entry in entries:
                        if entry.get('entryId', '').startswith('tweet-'):
                            content = entry.get('content', {})
                            item_content = content.get('itemContent', {})
                            tweet_results = item_content.get('tweet_results', {})
                            result = tweet_results.get('result', {})
                            
                            if result.get('__typename') == 'Tweet':
                                post = self._extract_tweet_data(result)
                                if post:
                                    posts.append(post)
        
        except Exception as e:
            logger.error(f"Error extracting posts from Twitter data: {e}")
        
        return posts
    
    def _extract_tweet_data(self, tweet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract relevant data from a tweet object"""
        try:
            legacy = tweet.get('legacy', {})
            user = tweet.get('core', {}).get('user_results', {}).get('result', {}).get('legacy', {})
            
            return {
                'id': legacy.get('id_str'),
                'text': legacy.get('full_text', ''),
                'created_at': legacy.get('created_at'),
                'user': {
                    'id': user.get('id_str'),
                    'screen_name': user.get('screen_name'),
                    'name': user.get('name'),
                    'followers_count': user.get('followers_count', 0)
                },
                'engagement': {
                    'retweet_count': legacy.get('retweet_count', 0),
                    'favorite_count': legacy.get('favorite_count', 0),
                    'reply_count': legacy.get('reply_count', 0),
                    'quote_count': legacy.get('quote_count', 0)
                },
                'metadata': {
                    'source': 'twitter',
                    'fetched_at': datetime.now(timezone.utc).isoformat(),
                    'lang': legacy.get('lang'),
                    'possibly_sensitive': legacy.get('possibly_sensitive', False)
                }
            }
        except Exception as e:
            logger.error(f"Error extracting tweet data: {e}")
            return None
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

class InputHandler:
    """Main input handler that manages data sources"""
    
    def __init__(self, config: SourceConfig):
        self.config = config
        self.source = self._create_source(config)
        self.data_store = []
        self.last_fetch = None
    
    def _create_source(self, config: SourceConfig) -> DataSource:
        """Create appropriate data source based on configuration"""
        if config.type.lower() == 'twitter':
            return TwitterSource(config)
        else:
            raise ValueError(f"Unsupported source type: {config.type}")
    
    async def fetch_new_data(self) -> List[Dict[str, Any]]:
        """Fetch new data from the configured source"""
        logger.info("Fetching new data...")
        
        try:
            new_data = await self.source.fetch_data()
            
            # Filter out duplicates
            existing_ids = {item.get('id') for item in self.data_store}
            new_items = [item for item in new_data if item.get('id') not in existing_ids]
            
            # Add to data store
            self.data_store.extend(new_items)
            self.last_fetch = datetime.now(timezone.utc)
            
            logger.info(f"Added {len(new_items)} new items to data store")
            return new_items
            
        except Exception as e:
            logger.error(f"Error fetching new data: {e}")
            return []
    
    def get_stored_data(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get stored data with optional limit"""
        if limit:
            return self.data_store[-limit:]
        return self.data_store.copy()
    
    def clear_old_data(self, max_age_hours: int = 24) -> None:
        """Remove old data from storage"""
        if not self.data_store:
            return
        
        cutoff_time = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
        
        filtered_data = []
        for item in self.data_store:
            try:
                # Parse created_at timestamp
                created_at = item.get('created_at')
                if created_at:
                    # Convert Twitter timestamp to datetime
                    item_time = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
                    if item_time.timestamp() > cutoff_time:
                        filtered_data.append(item)
            except Exception:
                # Keep item if we can't parse timestamp
                filtered_data.append(item)
        
        removed_count = len(self.data_store) - len(filtered_data)
        self.data_store = filtered_data
        
        if removed_count > 0:
            logger.info(f"Removed {removed_count} old items from data store")
    
    async def save_data_dump(self, filepath: str = "data_dump.json") -> None:
        """Save current data store to file"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'data': self.data_store,
                    'last_fetch': self.last_fetch.isoformat() if self.last_fetch else None,
                    'total_items': len(self.data_store)
                }, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved data dump to {filepath}")
        except Exception as e:
            logger.error(f"Error saving data dump: {e}")
    
    async def close(self):
        """Close resources"""
        if hasattr(self.source, 'close'):
            await self.source.close()
