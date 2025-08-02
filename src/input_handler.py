"""
Twitter Input Handler - Retrieves tweets using custom GraphQL API and posts via Twitter API v2
"""

import tweepy
import httpx
import json
import asyncio
import random
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
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
    """Twitter data source using custom GraphQL API for reading and Twitter API v2 for writing"""
    
    def __init__(self, config: SourceConfig):
        self.config = config
        self.api = None  # For posting tweets
        self.http_client = None  # For GraphQL API requests
        self.replied_tweets = set()  # Track tweets we've already replied to
        self.replied_tweets_file = Path("replied_tweets.json")
        self._load_replied_tweets()
        
        # Initialize Twitter API clients
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Twitter API clients with separate read/write capabilities"""
        try:
            # Initialize HTTP client for GraphQL API (reading tweets)
            if self.config.read_bearer_token and self.config.read_cookie and self.config.read_csrf_token:
                headers = {
                    "Authorization": f"Bearer {self.config.read_bearer_token}",
                    "Cookie": self.config.read_cookie,
                    "User-Agent": self.config.read_user_agent or "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                    "X-Csrf-Token": self.config.read_csrf_token,
                    "Referer": "https://x.com/home"
                }
                self.http_client = httpx.AsyncClient(headers=headers, timeout=30.0)
                logger.info("GraphQL API client initialized for reading tweets")
            else:
                logger.warning("Read credentials incomplete - GraphQL API unavailable")
            
            # Initialize Twitter API v1.1 for posting (requires full OAuth credentials)
            if not all([self.config.api_key, self.config.api_secret, 
                       self.config.access_token, self.config.access_token_secret]):
                raise ValueError("Missing required OAuth credentials for posting tweets")
                
            auth = tweepy.OAuth1UserHandler(
                self.config.api_key,
                self.config.api_secret,
                self.config.access_token,
                self.config.access_token_secret
            )
            self.api = tweepy.API(auth, wait_on_rate_limit=True)
            
            logger.info("Twitter API initialized for posting tweets")
            
        except Exception as e:
            logger.error(f"Failed to initialize Twitter API clients: {e}")
            raise
    
    def _load_replied_tweets(self):
        """Load previously replied tweet IDs from file"""
        try:
            if self.replied_tweets_file.exists():
                with open(self.replied_tweets_file, 'r') as f:
                    data = json.load(f)
                    self.replied_tweets = set(data.get('replied_tweets', []))
                logger.info(f"Loaded {len(self.replied_tweets)} previously replied tweet IDs")
        except Exception as e:
            logger.error(f"Error loading replied tweets: {e}")
            self.replied_tweets = set()
    
    def _save_replied_tweets(self):
        """Save replied tweet IDs to file"""
        try:
            data = {
                'replied_tweets': list(self.replied_tweets),
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            with open(self.replied_tweets_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving replied tweets: {e}")
    
    async def fetch_data(self) -> List[Dict[str, Any]]:
        """Fetch tweets from Twitter GraphQL API"""
        try:
            if not self.http_client:
                logger.error("GraphQL API client not available - check read credentials")
                return []
            
            tweets = []
            
            # Use the GraphQL API URL from config or fallback to default timeline
            api_url = getattr(self.config, 'read_api_url', None)
            if not api_url:
                logger.warning("No GraphQL API URL configured, cannot fetch tweets")
                return []
            
            # Fetch tweets from GraphQL API
            graphql_tweets = await self._fetch_from_graphql(api_url)
            tweets.extend(graphql_tweets)
            
            # Remove duplicates and filter
            unique_tweets = self._remove_duplicates(tweets)
            filtered_tweets = self._apply_selection_strategy(unique_tweets)
            
            logger.info(f"Fetched {len(filtered_tweets)} tweets from GraphQL API")
            return filtered_tweets
            
        except Exception as e:
            logger.error(f"Error fetching Twitter data: {e}")
            return []
    
    async def _fetch_from_graphql(self, api_url: str) -> List[Dict[str, Any]]:
        """Fetch tweets from Twitter GraphQL API"""
        tweets = []
        
        try:
            logger.info(f"Fetching tweets from GraphQL API...")
            response = await self.http_client.get(api_url)
            
            if response.status_code == 200:
                data = response.json()
                logger.info("Successfully fetched data from GraphQL API")
                
                # Parse the Twitter GraphQL response format
                tweets = self._parse_graphql_response(data)
                logger.info(f"Parsed {len(tweets)} tweets from GraphQL response")
                
            else:
                logger.error(f"GraphQL API request failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error fetching from GraphQL API: {e}")
        
        return tweets
    
    def _parse_graphql_response(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse Twitter GraphQL API response into standard tweet format"""
        tweets = []
        
        try:
            # Navigate through the GraphQL response structure
            timeline_data = data.get('data', {}).get('home', {}).get('home_timeline_urt', {})
            instructions = timeline_data.get('instructions', [])
            
            for instruction in instructions:
                if instruction.get('type') == 'TimelineAddEntries':
                    entries = instruction.get('entries', [])
                    
                    for entry in entries:
                        entry_id = entry.get('entryId', '')
                        
                        # Only process tweet entries (skip promoted, cursor, etc.)
                        if entry_id.startswith('tweet-'):
                            tweet_data = self._extract_tweet_from_entry(entry)
                            if tweet_data and tweet_data['id'] not in self.replied_tweets:
                                tweets.append(tweet_data)
                        
                        # Also handle conversation entries
                        elif entry_id.startswith('home-conversation-'):
                            conversation_tweets = self._extract_conversation_tweets(entry)
                            for tweet_data in conversation_tweets:
                                if tweet_data and tweet_data['id'] not in self.replied_tweets:
                                    tweets.append(tweet_data)
                                    
        except Exception as e:
            logger.error(f"Error parsing GraphQL response: {e}")
            
        return tweets
    
    def _extract_tweet_from_entry(self, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract tweet data from a timeline entry"""
        try:
            content = entry.get('content', {})
            if content.get('entryType') != 'TimelineTimelineItem':
                return None
                
            item_content = content.get('itemContent', {})
            if item_content.get('itemType') != 'TimelineTweet':
                return None
                
            tweet_results = item_content.get('tweet_results', {})
            result = tweet_results.get('result', {})
            
            if result.get('__typename') != 'Tweet':
                return None
            
            # Extract tweet data
            legacy = result.get('legacy', {})
            user_result = result.get('core', {}).get('user_results', {}).get('result', {})
            user_core = user_result.get('core', {})
            user_legacy = user_result.get('legacy', {})
            
            tweet_id = legacy.get('id_str')
            if not tweet_id:
                return None
            
            tweet_data = {
                'id': tweet_id,
                'text': legacy.get('full_text', ''),
                'author_id': user_result.get('rest_id', ''),
                'author_username': user_core.get('screen_name', 'unknown'),
                'author_name': user_core.get('name', 'Unknown'),
                'author_verified': user_legacy.get('verified', False),
                'created_at': legacy.get('created_at', ''),
                'conversation_id': legacy.get('conversation_id_str', tweet_id),
                'metrics': {
                    'retweet_count': legacy.get('retweet_count', 0),
                    'like_count': legacy.get('favorite_count', 0),
                    'reply_count': legacy.get('reply_count', 0),
                    'quote_count': legacy.get('quote_count', 0)
                },
                'source': 'graphql_timeline'
            }
            
            return tweet_data
            
        except Exception as e:
            logger.error(f"Error extracting tweet from entry: {e}")
            return None
    
    def _extract_conversation_tweets(self, entry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract tweets from conversation entries"""
        tweets = []
        
        try:
            content = entry.get('content', {})
            if content.get('entryType') != 'TimelineTimelineModule':
                return tweets
                
            items = content.get('items', [])
            for item in items:
                item_content = item.get('item', {}).get('itemContent', {})
                if item_content.get('itemType') == 'TimelineTweet':
                    fake_entry = {'content': {'itemContent': item_content}}
                    tweet_data = self._extract_tweet_from_entry(fake_entry)
                    if tweet_data:
                        tweets.append(tweet_data)
                        
        except Exception as e:
            logger.error(f"Error extracting conversation tweets: {e}")
            
        return tweets
    
    def _remove_duplicates(self, tweets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate tweets by ID"""
        seen_ids = set()
        unique_tweets = []
        
        for tweet in tweets:
            if tweet['id'] not in seen_ids:
                seen_ids.add(tweet['id'])
                unique_tweets.append(tweet)
        
        return unique_tweets
    
    def _apply_selection_strategy(self, tweets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply tweet selection strategy"""
        if not tweets:
            return tweets
        
        if self.config.selection_strategy == "random":
            # Randomly select tweets
            return random.sample(tweets, min(len(tweets), self.config.max_tweets_per_fetch))
        
        elif self.config.selection_strategy == "engagement_based":
            # Sort by total engagement (likes + retweets + replies + quotes)
            tweets.sort(key=lambda t: (
                t['metrics']['like_count'] + 
                t['metrics']['retweet_count'] + 
                t['metrics']['reply_count'] + 
                t['metrics']['quote_count']
            ), reverse=True)
            
            return tweets[:self.config.max_tweets_per_fetch]
        
        elif self.config.selection_strategy == "selective":
            # Custom selection logic - prioritize verified users and recent tweets
            def selection_score(tweet):
                score = 0
                
                # Bonus for verified users
                if tweet['author_verified']:
                    score += 100
                
                # Bonus for recent tweets
                tweet_time = datetime.fromisoformat(tweet['created_at'].replace('Z', '+00:00'))
                hours_old = (datetime.now(timezone.utc) - tweet_time).total_seconds() / 3600
                score += max(0, 24 - hours_old)  # More recent = higher score
                
                # Engagement score
                engagement = (
                    tweet['metrics']['like_count'] + 
                    tweet['metrics']['retweet_count'] * 2 +  # Retweets worth more
                    tweet['metrics']['reply_count'] + 
                    tweet['metrics']['quote_count']
                )
                score += engagement
                
                return score
            
            tweets.sort(key=selection_score, reverse=True)
            return tweets[:self.config.max_tweets_per_fetch]
        
        else:
            # Default: return all tweets
            return tweets[:self.config.max_tweets_per_fetch]
    
    def mark_as_replied(self, tweet_id: str):
        """Mark a tweet as replied to"""
        self.replied_tweets.add(tweet_id)
        self._save_replied_tweets()
        logger.info(f"Marked tweet {tweet_id} as replied")
    
    async def post_reply(self, tweet_id: str, reply_text: str) -> bool:
        """Post a reply to a tweet"""
        try:
            # Use API v1.1 for posting replies
            response = self.api.update_status(
                status=reply_text,
                in_reply_to_status_id=tweet_id,
                auto_populate_reply_metadata=True
            )
            
            logger.info(f"Posted reply to tweet {tweet_id}: {reply_text[:50]}...")
            self.mark_as_replied(tweet_id)
            return True
            
        except Exception as e:
            logger.error(f"Error posting reply to tweet {tweet_id}: {e}")
            return False
            
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
class InputHandler:
    """Main input handler that manages Twitter data sources"""
    
    def __init__(self, config: SourceConfig):
        self.config = config
        self.source = TwitterSource(config)
        self.data_store = []
        self.last_fetch = None
        self.data_dump_file = Path("response_dump.json")
        self._load_data_dump()
    
    def _load_data_dump(self):
        """Load previously saved data dump"""
        try:
            if self.data_dump_file.exists():
                with open(self.data_dump_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.data_store = data.get('data', [])
                    last_fetch_str = data.get('last_fetch')
                    if last_fetch_str:
                        self.last_fetch = datetime.fromisoformat(last_fetch_str)
                logger.info(f"Loaded {len(self.data_store)} items from data dump")
        except Exception as e:
            logger.error(f"Error loading data dump: {e}")
            self.data_store = []
    
    async def fetch_new_data(self) -> List[Dict[str, Any]]:
        """Fetch new tweets from Twitter"""
        logger.info("Fetching new tweets...")
        
        try:
            new_tweets = await self.source.fetch_data()
            
            # Filter out duplicates
            existing_ids = {item.get('id') for item in self.data_store}
            new_items = [item for item in new_tweets if item.get('id') not in existing_ids]
            
            # Add to data store
            self.data_store.extend(new_items)
            self.last_fetch = datetime.now(timezone.utc)
            
            # Keep only recent tweets (last 24 hours)
            self.clear_old_data(24)
            
            logger.info(f"Added {len(new_items)} new tweets to data store")
            return new_items
            
        except Exception as e:
            logger.error(f"Error fetching new tweets: {e}")
            return []
    
    def get_stored_data(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get stored tweets with optional limit"""
        if limit:
            return self.data_store[-limit:]
        return self.data_store.copy()
    
    def clear_old_data(self, max_age_hours: int = 24) -> None:
        """Remove old tweets from storage"""
        if not self.data_store:
            return
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        
        filtered_data = []
        for item in self.data_store:
            try:
                # Parse created_at timestamp (ISO format from Twitter API v2)
                created_at = item.get('created_at')
                if created_at:
                    item_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    if item_time > cutoff_time:
                        filtered_data.append(item)
            except Exception:
                # Keep item if we can't parse timestamp
                filtered_data.append(item)
        
        removed_count = len(self.data_store) - len(filtered_data)
        self.data_store = filtered_data
        
        if removed_count > 0:
            logger.info(f"Removed {removed_count} old tweets from data store")
    
    async def save_data_dump(self, filepath: Optional[str] = None) -> None:
        """Save current data store to file"""
        try:
            if filepath is None:
                filepath = self.data_dump_file
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'data': self.data_store,
                    'last_fetch': self.last_fetch.isoformat() if self.last_fetch else None,
                    'total_items': len(self.data_store),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved data dump to {filepath}")
        except Exception as e:
            logger.error(f"Error saving data dump: {e}")
    
    def mark_tweet_as_replied(self, tweet_id: str):
        """Mark a tweet as replied to (delegate to TwitterSource)"""
        self.source.mark_as_replied(tweet_id)
    
    async def post_reply(self, tweet_id: str, reply_text: str) -> bool:
        """Post a reply to a tweet (delegate to TwitterSource)"""
        return await self.source.post_reply(tweet_id, reply_text)
    
    async def close(self):
        """Close resources"""
        # Save data before closing
        await self.save_data_dump()
        
        # Close Twitter client connections
        if hasattr(self.source, 'client') and self.source.client:
            # tweepy clients don't need explicit closing
            pass