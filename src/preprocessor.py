"""
Context Pre-processor - Cleans and structures post data
"""

import re
import html
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import logging
from dataclasses import dataclass

try:
    from .config import FilterConfig
except ImportError:
    from config import FilterConfig

logger = logging.getLogger(__name__)

@dataclass
class ProcessedPost:
    """Structured representation of a processed post"""
    id: str
    original_text: str
    cleaned_text: str
    user_info: Dict[str, Any]
    engagement_score: float
    metadata: Dict[str, Any]
    tags: List[str]
    sentiment: Optional[str] = None
    priority: int = 0

class TextCleaner:
    """Handles text cleaning and normalization"""
    
    def __init__(self):
        # Compile regex patterns for efficiency
        self.url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        self.mention_pattern = re.compile(r'@\w+')
        self.hashtag_pattern = re.compile(r'#\w+')
        self.extra_whitespace = re.compile(r'\s+')
        self.emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002700-\U000027BF\U0001f900-\U0001f9ff\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f1e0-\U0001f1ff]+')
    
    def clean_text(self, text: str, preserve_mentions: bool = True, preserve_hashtags: bool = True) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Decode HTML entities
        text = html.unescape(text)
        
        # Remove URLs
        text = self.url_pattern.sub('', text)
        
        # Handle mentions and hashtags based on preferences
        if not preserve_mentions:
            text = self.mention_pattern.sub('', text)
        if not preserve_hashtags:
            text = self.hashtag_pattern.sub('', text)
        
        # Normalize whitespace
        text = self.extra_whitespace.sub(' ', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract mentions, hashtags, and URLs from text"""
        return {
            'mentions': self.mention_pattern.findall(text),
            'hashtags': self.hashtag_pattern.findall(text),
            'urls': self.url_pattern.findall(text)
        }
    
    def remove_emojis(self, text: str) -> str:
        """Remove emojis from text"""
        return self.emoji_pattern.sub('', text)

class ContentFilter:
    """Filters content based on various criteria"""
    
    def __init__(self, config: FilterConfig):
        self.config = config
        self.include_keywords = [kw.lower() for kw in config.keywords_include]
        self.exclude_keywords = [kw.lower() for kw in config.keywords_exclude]
    
    def should_process(self, post: Dict[str, Any]) -> bool:
        """Determine if a post should be processed"""
        # Check age
        if not self._is_recent_enough(post):
            return False
        
        # Check language
        if not self._matches_language(post):
            return False
        
        # Check engagement threshold
        if not self._meets_engagement_threshold(post):
            return False
        
        # Check keyword filters
        if not self._passes_keyword_filter(post):
            return False
        
        return True
    
    def _is_recent_enough(self, post: Dict[str, Any]) -> bool:
        """Check if post is recent enough"""
        try:
            created_at = post.get('created_at')
            if not created_at:
                return True  # Allow if no timestamp
            
            # Handle Twitter API v2 ISO format
            post_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            age_hours = (datetime.now(timezone.utc) - post_time).total_seconds() / 3600
            
            return age_hours <= self.config.max_age_hours
        except Exception as e:
            logger.debug(f"Error parsing timestamp {created_at}: {e}")
            return True  # Allow if parsing fails
    
    def _matches_language(self, post: Dict[str, Any]) -> bool:
        """Check if post matches language requirement"""
        if not self.config.language:
            return True
        
        # For Twitter API v2, language detection would need to be done separately
        # For now, we assume English tweets based on our search query
        return True
    
    def _meets_engagement_threshold(self, post: Dict[str, Any]) -> bool:
        """Check if post meets minimum engagement"""
        metrics = post.get('metrics', {})
        total_engagement = (
            metrics.get('retweet_count', 0) +
            metrics.get('like_count', 0) +
            metrics.get('reply_count', 0) +
            metrics.get('quote_count', 0)
        )
        
        return total_engagement >= self.config.min_engagement
    
    def _passes_keyword_filter(self, post: Dict[str, Any]) -> bool:
        """Check if post passes keyword filters"""
        text = post.get('text', '').lower()
        
        # Check exclude keywords first
        if self.exclude_keywords:
            for keyword in self.exclude_keywords:
                if keyword in text:
                    return False
        
        # Check include keywords
        if self.include_keywords:
            for keyword in self.include_keywords:
                if keyword in text:
                    return True
            return False  # None of the required keywords found
        
        return True  # No include filter specified

class EngagementCalculator:
    """Calculates engagement scores for posts"""
    
    @staticmethod
    def calculate_score(post: Dict[str, Any]) -> float:
        """Calculate engagement score for a post (updated for Twitter API v2)"""
        metrics = post.get('metrics', {})
        
        # Base engagement metrics from Twitter API v2
        retweets = metrics.get('retweet_count', 0)
        likes = metrics.get('like_count', 0)
        replies = metrics.get('reply_count', 0)
        quotes = metrics.get('quote_count', 0)
        
        # Calculate weighted score
        # Replies are weighted higher as they indicate more meaningful engagement
        raw_score = (retweets * 2) + (likes * 1) + (replies * 3) + (quotes * 2)
        
        # Simple normalization since we don't have follower count in current implementation
        # Could be enhanced to fetch user details separately if needed
        normalized_score = raw_score
        
        # Bonus for verified users
        if post.get('author_verified', False):
            normalized_score *= 1.2
        
        return round(normalized_score, 2)

class ContextPreprocessor:
    """Main preprocessor that coordinates cleaning and filtering"""
    
    def __init__(self, config: FilterConfig):
        self.config = config
        self.text_cleaner = TextCleaner()
        self.content_filter = ContentFilter(config)
        self.engagement_calculator = EngagementCalculator()
    
    def process_posts(self, raw_posts: List[Dict[str, Any]]) -> List[ProcessedPost]:
        """Process a list of raw posts"""
        processed_posts = []
        
        for post in raw_posts:
            try:
                # Filter first to save processing time
                if not self.content_filter.should_process(post):
                    continue
                
                processed_post = self._process_single_post(post)
                if processed_post:
                    processed_posts.append(processed_post)
                    
            except Exception as e:
                logger.error(f"Error processing post {post.get('id', 'unknown')}: {e}")
                continue
        
        # Sort by engagement score (highest first)
        processed_posts.sort(key=lambda x: x.engagement_score, reverse=True)
        
        logger.info(f"Processed {len(processed_posts)} posts from {len(raw_posts)} raw posts")
        return processed_posts
    
    def _process_single_post(self, post: Dict[str, Any]) -> Optional[ProcessedPost]:
        """Process a single tweet from Twitter API v2"""
        try:
            original_text = post.get('text', '')
            if not original_text:
                return None
            
            # Clean text
            cleaned_text = self.text_cleaner.clean_text(original_text)
            if not cleaned_text:
                return None
            
            # Extract entities
            entities = self.text_cleaner.extract_entities(original_text)
            
            # Calculate engagement score
            engagement_score = self.engagement_calculator.calculate_score(post)
            
            # Prepare user info in the expected format
            user_info = {
                'id': post.get('author_id', ''),
                'screen_name': post.get('author_username', ''),
                'name': post.get('author_name', ''),
                'followers_count': 0,  # Not available in current API response
                'verified': post.get('author_verified', False)
            }
            
            # Generate tags
            tags = self._generate_tags(post, entities, user_info)
            
            # Determine priority
            priority = self._calculate_priority(engagement_score, post)
            
            return ProcessedPost(
                id=post.get('id', ''),
                original_text=original_text,
                cleaned_text=cleaned_text,
                user_info=user_info,
                engagement_score=engagement_score,
                metadata={
                    'created_at': post.get('created_at'),
                    'conversation_id': post.get('conversation_id'),
                    'source': post.get('source', 'twitter'),
                    'metrics': post.get('metrics', {}),
                    'entities': entities,
                    'processed_at': datetime.now(timezone.utc).isoformat()
                },
                tags=tags,
                priority=priority
            )
            
        except Exception as e:
            logger.error(f"Error processing single post: {e}")
            return None
    
    def _generate_tags(self, post: Dict[str, Any], entities: Dict[str, List[str]], user_info: Dict[str, Any]) -> List[str]:
        """Generate tags for categorizing posts"""
        tags = []
        
        # Add engagement level tag
        metrics = post.get('metrics', {})
        total_engagement = (
            metrics.get('like_count', 0) +
            metrics.get('retweet_count', 0) +
            metrics.get('reply_count', 0) +
            metrics.get('quote_count', 0)
        )
        
        if total_engagement > 100:
            tags.append('high-engagement')
        elif total_engagement > 10:
            tags.append('medium-engagement')
        else:
            tags.append('low-engagement')
        
        # Add content type tags
        if entities.get('hashtags'):
            tags.append('has-hashtags')
        if entities.get('mentions'):
            tags.append('has-mentions')
        if entities.get('urls'):
            tags.append('has-links')
        
        # Add user type tags
        if user_info.get('verified'):
            tags.append('verified-user')
        
        # Add source tag
        source = post.get('source', '')
        if 'keywords' in source:
            tags.append('keyword-match')
        elif 'user:' in source:
            tags.append('tracked-user')
        
        return tags
    
    def _calculate_priority(self, engagement_score: float, post: Dict[str, Any]) -> int:
        """Calculate priority score (1-10, 10 being highest)"""
        # Base priority on engagement score
        if engagement_score > 50:
            priority = 9
        elif engagement_score > 20:
            priority = 7
        elif engagement_score > 10:
            priority = 5
        elif engagement_score > 5:
            priority = 3
        else:
            priority = 1
        
        # Boost priority for verified users or high follower counts
        user = post.get('user', {})
        if user.get('verified', False):
            priority = min(10, priority + 1)
        
        followers = user.get('followers_count', 0)
        if followers > 50000:
            priority = min(10, priority + 1)
        
        return priority
