"""
Reply Engine - Sends or logs responses based on configuration
"""

import json
import random
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path
import logging

try:
    from .config import ReplyConfig
    from .preprocessor import ProcessedPost
except ImportError:
    from config import ReplyConfig
    from preprocessor import ProcessedPost

logger = logging.getLogger(__name__)

class ResponseLogger:
    """Handles logging of responses"""
    
    def __init__(self, log_file: str = "responses.jsonl"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log_response(self, post: ProcessedPost, response: str, metadata: Optional[Dict[str, Any]] = None):
        """Log a response to file"""
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'post_id': post.id,
            'original_post': post.original_text,
            'user': post.user_info.get('screen_name', 'unknown'),
            'response': response,
            'engagement_score': post.engagement_score,
            'tags': post.tags,
            'metadata': metadata or {}
        }
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            logger.debug(f"Logged response for post {post.id}")
        except Exception as e:
            logger.error(f"Error logging response: {e}")
    
    def get_recent_logs(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent log entries"""
        if not self.log_file.exists():
            return []
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_logs = []
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entry_time = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                        if entry_time > cutoff_time:
                            recent_logs.append(entry)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
        
        return recent_logs

class RateLimiter:
    """Handles rate limiting for responses"""
    
    def __init__(self, max_per_hour: int = 10):
        self.max_per_hour = max_per_hour
        self.responses = []
    
    def can_respond(self) -> bool:
        """Check if we can send another response"""
        self._clean_old_responses()
        return len(self.responses) < self.max_per_hour
    
    def record_response(self):
        """Record that a response was sent"""
        self.responses.append(datetime.now(timezone.utc))
    
    def _clean_old_responses(self):
        """Remove responses older than 1 hour"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        self.responses = [r for r in self.responses if r > cutoff]
    
    def time_until_next_allowed(self) -> int:
        """Get seconds until next response is allowed"""
        if self.can_respond():
            return 0
        
        if not self.responses:
            return 0
        
        oldest_response = min(self.responses)
        next_allowed = oldest_response + timedelta(hours=1)
        time_diff = (next_allowed - datetime.now(timezone.utc)).total_seconds()
        
        return max(0, int(time_diff))

class ResponseFilter:
    """Filters responses based on various criteria"""
    
    def __init__(self, config: ReplyConfig):
        self.config = config
        self.blacklisted_words = [
            'hate', 'spam', 'scam', 'fake', 'bot', 'automated',
            'violence', 'harassment', 'abuse'
        ]
    
    def should_send_response(self, post: ProcessedPost, response: str) -> bool:
        """Determine if a response should be sent"""
        # Check if randomization allows it
        if self.config.randomize:
            if random.random() > self.config.reply_probability:
                logger.debug(f"Response filtered out by randomization for post {post.id}")
                return False
        
        # Check response quality
        if not self._is_quality_response(response):
            logger.debug(f"Response filtered out due to quality for post {post.id}")
            return False
        
        # Check if response is appropriate
        if not self._is_appropriate_response(response, post):
            logger.debug(f"Response filtered out as inappropriate for post {post.id}")
            return False
        
        return True
    
    def _is_quality_response(self, response: str) -> bool:
        """Check if response meets quality standards"""
        if not response or len(response.strip()) < 10:
            return False
        
        # Check for repetitive content
        words = response.lower().split()
        if len(set(words)) < len(words) * 0.5:  # Too many repeated words
            return False
        
        # Check for blacklisted words
        for word in self.blacklisted_words:
            if word in response.lower():
                return False
        
        return True
    
    def _is_appropriate_response(self, response: str, post: ProcessedPost) -> bool:
        """Check if response is appropriate for the post"""
        # Don't respond to potentially sensitive content
        if post.metadata.get('possibly_sensitive', False):
            return False
        
        # Don't respond to very low engagement posts unless they're high priority
        if post.engagement_score < 1 and post.priority < 5:
            return False
        
        # Don't respond with generic responses to high-engagement posts
        generic_responses = ['thanks', 'great', 'nice', 'cool', 'awesome']
        if (post.engagement_score > 20 and 
            any(generic in response.lower() for generic in generic_responses) and
            len(response) < 20):
            return False
        
        return True

class MockPoster:
    """Mock implementation for posting responses (for testing)"""
    
    def __init__(self):
        self.posted_responses = []
    
    async def post_response(self, post: ProcessedPost, response: str) -> bool:
        """Mock posting a response"""
        # Simulate API delay
        await asyncio.sleep(random.uniform(1, 3))
        
        # Simulate occasional failures
        if random.random() < 0.05:  # 5% failure rate
            logger.warning(f"Mock posting failed for post {post.id}")
            return False
        
        self.posted_responses.append({
            'post_id': post.id,
            'response': response,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"Mock posted response to {post.id}: {response[:50]}...")
        return True

class ReplyEngine:
    """Main reply engine that coordinates response sending/logging"""
    
    def __init__(self, config: ReplyConfig, input_handler=None):
        self.config = config
        self.logger = ResponseLogger()
        self.rate_limiter = RateLimiter(config.max_replies_per_hour)
        self.filter = ResponseFilter(config)
        self.input_handler = input_handler  # For Twitter posting
        self.poster = MockPoster()  # Fallback for when no input_handler provided
        self.stats = {
            'total_processed': 0,
            'responses_generated': 0,
            'responses_sent': 0,
            'responses_logged': 0,
            'filtered_out': 0
        }
    
    async def process_responses(self, responses: Dict[str, str], posts: List[ProcessedPost]) -> Dict[str, Any]:
        """Process a batch of responses"""
        results = {
            'sent': [],
            'logged': [],
            'filtered': [],
            'failed': []
        }
        
        # Create lookup for posts
        post_lookup = {post.id: post for post in posts}
        
        for post_id, response in responses.items():
            post = post_lookup.get(post_id)
            if not post:
                continue
            
            self.stats['total_processed'] += 1
            
            try:
                await self._process_single_response(post, response, results)
            except Exception as e:
                logger.error(f"Error processing response for post {post_id}: {e}")
                results['failed'].append({
                    'post_id': post_id,
                    'error': str(e)
                })
        
        self._log_processing_stats(results)
        return results
    
    async def _process_single_response(self, post: ProcessedPost, response: str, results: Dict[str, Any]):
        """Process a single response"""
        # Apply filters
        if not self.filter.should_send_response(post, response):
            results['filtered'].append({
                'post_id': post.id,
                'response': response,
                'reason': 'filtered'
            })
            self.stats['filtered_out'] += 1
            return
        
        self.stats['responses_generated'] += 1
        
        # Always log the response
        if self.config.mode in ['log', 'both']:
            self.logger.log_response(post, response, {
                'mode': self.config.mode,
                'rate_limited': not self.rate_limiter.can_respond()
            })
            results['logged'].append({
                'post_id': post.id,
                'response': response
            })
            self.stats['responses_logged'] += 1
        
        # Send response if configured and rate limit allows
        if self.config.mode in ['post', 'both'] and self.rate_limiter.can_respond():
            # Add random delay
            if self.config.delay_range:
                delay = random.uniform(*self.config.delay_range)
                await asyncio.sleep(delay)
            
            # Use Twitter API if input_handler available, otherwise use mock poster
            if self.input_handler:
                success = await self.input_handler.post_reply(post.id, response)
            else:
                success = await self.poster.post_response(post, response)
            
            if success:
                self.rate_limiter.record_response()
                results['sent'].append({
                    'post_id': post.id,
                    'response': response
                })
                self.stats['responses_sent'] += 1
                logger.info(f"Successfully sent response to post {post.id}")
            else:
                results['failed'].append({
                    'post_id': post.id,
                    'error': 'posting_failed'
                })
        elif self.config.mode in ['post', 'both']:
            # Rate limited
            results['filtered'].append({
                'post_id': post.id,
                'response': response,
                'reason': 'rate_limited'
            })
            logger.warning(f"Rate limited - cannot send response to post {post.id}")
    
    def _log_processing_stats(self, results: Dict[str, Any]):
        """Log processing statistics"""
        logger.info(f"Processing complete: "
                   f"sent={len(results['sent'])}, "
                   f"logged={len(results['logged'])}, "
                   f"filtered={len(results['filtered'])}, "
                   f"failed={len(results['failed'])}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics"""
        recent_logs = self.logger.get_recent_logs(24)
        
        return {
            **self.stats,
            'recent_responses_24h': len(recent_logs),
            'rate_limit_remaining': self.config.max_replies_per_hour - len(self.rate_limiter.responses),
            'time_until_next_allowed': self.rate_limiter.time_until_next_allowed(),
            'posted_responses': len(self.poster.posted_responses)
        }
    
    def get_recent_responses(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent responses"""
        return self.logger.get_recent_logs(hours)
    
    async def cleanup_old_data(self, days: int = 7):
        """Clean up old response data"""
        # This could be enhanced to actually clean up old log files
        # For now, just log the action
        logger.info(f"Cleanup requested for data older than {days} days")
        
        # Clean up mock poster data
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        original_count = len(self.poster.posted_responses)
        
        self.poster.posted_responses = [
            resp for resp in self.poster.posted_responses
            if datetime.fromisoformat(resp['timestamp'].replace('Z', '+00:00')) > cutoff
        ]
        
        cleaned_count = original_count - len(self.poster.posted_responses)
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old posted responses")
