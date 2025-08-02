"""
Ollama LLM Integration - Queries local LLM models via Ollama
"""

import ollama
import asyncio
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime, timezone
import logging

try:
    from .config import LLMConfig
    from .preprocessor import ProcessedPost
except ImportError:
    from config import LLMConfig
    from preprocessor import ProcessedPost

logger = logging.getLogger(__name__)

class OllamaClient:
    """Client for interacting with Ollama using the official Python library"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        # Parse host from base_url
        if '://' in config.base_url:
            self.host = config.base_url
        else:
            self.host = f"http://{config.base_url}"
        
        # Initialize Ollama client
        self.client = ollama.Client(host=self.host)
    
    async def check_health(self) -> bool:
        """Check if Ollama service is running"""
        try:
            # Use a synchronous call in an executor to avoid blocking
            loop = asyncio.get_event_loop()
            models = await loop.run_in_executor(None, self.client.list)
            return True
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
    
    async def list_models(self) -> List[str]:
        """List available models"""
        try:
            loop = asyncio.get_event_loop()
            models_response = await loop.run_in_executor(None, self.client.list)
            
            # Extract model names from the response
            models = []
            if hasattr(models_response, 'models'):
                for model in models_response.models:
                    if hasattr(model, 'model'):
                        models.append(model.model)
            
            return models
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []
    
    async def generate_response(self, prompt: str, system_prompt: Optional[str] = None) -> Optional[str]:
        """Generate a response using the configured model"""
        try:
            messages = []
            
            # Add system message if provided
            if system_prompt:
                messages.append({
                    'role': 'system',
                    'content': system_prompt
                })
            elif self.config.system_prompt:
                messages.append({
                    'role': 'system',
                    'content': self.config.system_prompt
                })
            
            # Add user prompt
            messages.append({
                'role': 'user',
                'content': prompt
            })
            
            # Generate response using chat interface
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.chat(
                    model=self.config.model,
                    messages=messages,
                    options={
                        'temperature': self.config.temperature,
                        'num_predict': self.config.max_tokens
                    }
                )
            )
            
            return response['message']['content'].strip()
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return None
    
    async def generate_stream(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Generate a streaming response"""
        try:
            messages = []
            
            # Add system message if provided
            if system_prompt:
                messages.append({
                    'role': 'system',
                    'content': system_prompt
                })
            elif self.config.system_prompt:
                messages.append({
                    'role': 'system',
                    'content': self.config.system_prompt
                })
            
            # Add user prompt
            messages.append({
                'role': 'user',
                'content': prompt
            })
            
            # Generate streaming response
            loop = asyncio.get_event_loop()
            
            def _stream_generator():
                return self.client.chat(
                    model=self.config.model,
                    messages=messages,
                    stream=True,
                    options={
                        'temperature': self.config.temperature,
                        'num_predict': self.config.max_tokens
                    }
                )
            
            stream = await loop.run_in_executor(None, _stream_generator)
            
            for chunk in stream:
                if 'message' in chunk and 'content' in chunk['message']:
                    yield chunk['message']['content']
                    
        except Exception as e:
            logger.error(f"Error in streaming generation: {e}")
    
    async def close(self):
        """Close the client (no-op for Ollama client)"""
        pass

class PromptBuilder:
    """Builds prompts for different types of responses"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
    
    def build_response_prompt(self, post: ProcessedPost, context: Optional[str] = None) -> str:
        """Build a prompt for generating a response to a post"""
        prompt_parts = [
            "Generate a thoughtful and engaging response to the following social media post.",
            "",
            f"Original Post: \"{post.cleaned_text}\"",
            f"Author: @{post.user_info.get('screen_name', 'unknown')}",
            f"Engagement Score: {post.engagement_score}",
        ]
        
        if post.tags:
            prompt_parts.append(f"Tags: {', '.join(post.tags)}")
        
        if context:
            prompt_parts.extend([
                "",
                f"Additional Context: {context}"
            ])
        
        prompt_parts.extend([
            "",
            "Guidelines for the response:",
            "- Keep it concise (under 280 characters)",
            "- Be helpful and engaging",
            "- Match the tone of the original post",
            "- Add value to the conversation",
            "- Avoid controversial topics",
            "- Don't repeat the original post content",
            "",
            "Response:"
        ])
        
        return "\n".join(prompt_parts)
    
    def build_analysis_prompt(self, post: ProcessedPost) -> str:
        """Build a prompt for analyzing a post"""
        return f"""
Analyze the following social media post and provide insights:

Post: "{post.cleaned_text}"
Author: @{post.user_info.get('screen_name', 'unknown')}
Engagement: {post.engagement_score}
Tags: {', '.join(post.tags)}

Please provide:
1. Sentiment (positive/negative/neutral)
2. Key topics discussed
3. Potential response strategies
4. Engagement potential (high/medium/low)

Analysis:
"""
    
    def build_summary_prompt(self, posts: List[ProcessedPost]) -> str:
        """Build a prompt for summarizing multiple posts"""
        post_summaries = []
        for i, post in enumerate(posts[:5], 1):  # Limit to top 5 posts
            post_summaries.append(f"{i}. @{post.user_info.get('screen_name', 'unknown')}: {post.cleaned_text[:100]}...")
        
        return f"""
Summarize the key trends and topics from these recent social media posts:

{chr(10).join(post_summaries)}

Provide:
1. Main topics/themes
2. Overall sentiment
3. Notable patterns
4. Recommended response strategy

Summary:
"""

class LLMEngine:
    """Main LLM engine that coordinates response generation"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = OllamaClient(config)
        self.prompt_builder = PromptBuilder(config)
        self.response_cache = {}
        self.cache_ttl = 3600  # 1 hour cache
    
    async def initialize(self) -> bool:
        """Initialize the LLM engine"""
        logger.info(f"Initializing LLM engine with model: {self.config.model}")
        
        # Check if Ollama is running
        if not await self.client.check_health():
            logger.error("Ollama service is not running")
            return False
        
        # Check if model is available
        available_models = await self.client.list_models()
        if self.config.model not in available_models:
            logger.warning(f"Model {self.config.model} not found. Available models: {available_models}")
            if available_models:
                logger.info(f"Consider using one of: {', '.join(available_models)}")
            return False
        
        logger.info("LLM engine initialized successfully")
        return True
    
    async def check_health(self) -> bool:
        """Check if the LLM engine is healthy"""
        return await self.client.check_health()
    
    async def generate_response(self, post: ProcessedPost, context: Optional[str] = None) -> Optional[str]:
        """Generate a response to a post"""
        # Check cache first
        cache_key = f"response_{post.id}_{hash(context or '')}"
        cached_response = self._get_cached_response(cache_key)
        if cached_response:
            logger.debug(f"Using cached response for post {post.id}")
            return cached_response
        
        # Build prompt
        prompt = self.prompt_builder.build_response_prompt(post, context)
        
        # Generate response
        response = await self.client.generate_response(prompt)
        
        if response:
            # Clean up response
            response = self._clean_response(response)
            
            # Cache the response
            self._cache_response(cache_key, response)
            
            logger.info(f"Generated response for post {post.id}: {response[:50]}...")
            return response
        
        logger.warning(f"Failed to generate response for post {post.id}")
        return None
    
    async def analyze_post(self, post: ProcessedPost) -> Optional[Dict[str, Any]]:
        """Analyze a post and return insights"""
        prompt = self.prompt_builder.build_analysis_prompt(post)
        analysis = await self.client.generate_response(prompt)
        
        if analysis:
            # Parse analysis into structured data
            return self._parse_analysis(analysis)
        
        return None
    
    async def summarize_posts(self, posts: List[ProcessedPost]) -> Optional[str]:
        """Summarize multiple posts"""
        if not posts:
            return None
        
        prompt = self.prompt_builder.build_summary_prompt(posts)
        summary = await self.client.generate_response(prompt)
        
        return summary
    
    async def generate_batch_responses(self, posts: List[ProcessedPost]) -> Dict[str, str]:
        """Generate responses for multiple posts"""
        responses = {}
        
        # Process posts in parallel (with concurrency limit)
        semaphore = asyncio.Semaphore(3)  # Limit concurrent requests
        
        async def process_post(post):
            async with semaphore:
                response = await self.generate_response(post)
                if response:
                    responses[post.id] = response
        
        tasks = [process_post(post) for post in posts]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"Generated {len(responses)} responses from {len(posts)} posts")
        return responses
    
    def _clean_response(self, response: str) -> str:
        """Clean and format response"""
        # Remove common prefixes
        prefixes_to_remove = [
            "Response:",
            "Reply:",
            "Answer:",
            "Here's a response:",
            "I would respond with:",
            "I would say:",
            "My response:",
            "Tweet:",
        ]
        
        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        # Remove surrounding quotation marks (single or double)
        response = response.strip()
        if (response.startswith('"') and response.endswith('"')) or \
           (response.startswith("'") and response.endswith("'")):
            response = response[1:-1].strip()
        
        # Handle cases where quotes are only at the beginning or end
        if response.startswith('"') and not response.endswith('"'):
            response = response[1:].strip()
        elif response.endswith('"') and not response.startswith('"'):
            response = response[:-1].strip()
        
        # Remove additional unwanted formatting
        response = response.replace('\"', '"')  # Fix escaped quotes
        response = response.replace("\\'", "'")  # Fix escaped single quotes
        response = response.replace('\\n', ' ')  # Convert escaped newlines to spaces
        
        # Remove extra whitespace
        response = ' '.join(response.split())
        
        # Remove any trailing periods that might be artifacts
        if response.endswith('."') and not response.endswith('..."'):
            response = response[:-2] + '"'
        elif response.endswith(".'") and not response.endswith("...'"):
            response = response[:-2] + "'"
        
        # Ensure it's not too long (Twitter limit)
        if len(response) > 280:
            response = response[:277] + "..."
        
        return response
    
    def _parse_analysis(self, analysis: str) -> Dict[str, Any]:
        """Parse analysis text into structured data"""
        # Simple parsing - could be enhanced with more sophisticated NLP
        result = {
            'sentiment': 'neutral',
            'topics': [],
            'engagement_potential': 'medium',
            'strategies': [],
            'raw_analysis': analysis
        }
        
        analysis_lower = analysis.lower()
        
        # Extract sentiment
        if 'positive' in analysis_lower:
            result['sentiment'] = 'positive'
        elif 'negative' in analysis_lower:
            result['sentiment'] = 'negative'
        
        # Extract engagement potential
        if 'high' in analysis_lower and 'engagement' in analysis_lower:
            result['engagement_potential'] = 'high'
        elif 'low' in analysis_lower and 'engagement' in analysis_lower:
            result['engagement_potential'] = 'low'
        
        return result
    
    def _get_cached_response(self, cache_key: str) -> Optional[str]:
        """Get response from cache if not expired"""
        if cache_key in self.response_cache:
            cached_data = self.response_cache[cache_key]
            if (datetime.now().timestamp() - cached_data['timestamp']) < self.cache_ttl:
                return cached_data['response']
            else:
                del self.response_cache[cache_key]
        return None
    
    def _cache_response(self, cache_key: str, response: str):
        """Cache a response"""
        self.response_cache[cache_key] = {
            'response': response,
            'timestamp': datetime.now().timestamp()
        }
        
        # Clean old cache entries periodically
        if len(self.response_cache) > 100:
            self._clean_cache()
    
    def _clean_cache(self):
        """Remove expired cache entries"""
        current_time = datetime.now().timestamp()
        expired_keys = [
            key for key, data in self.response_cache.items()
            if (current_time - data['timestamp']) >= self.cache_ttl
        ]
        
        for key in expired_keys:
            del self.response_cache[key]
    
    async def close(self):
        """Close resources"""
        await self.client.close()
