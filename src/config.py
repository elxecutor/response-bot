"""
AI Response Bot Configuration
"""

import yaml
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class SourceConfig:
    """Configuration for data source"""
    type: str = "twitter"
    api_url: str = ""
    bearer_token: str = ""
    cookie: str = ""
    user_agent: str = ""
    csrf_token: str = ""
    fetch_interval: int = 300  # seconds

@dataclass
class LLMConfig:
    """Configuration for Ollama LLM"""
    base_url: str = "http://localhost:11434"
    model: str = "llama2"
    temperature: float = 0.7
    max_tokens: int = 150
    system_prompt: str = "You are a helpful AI assistant that generates engaging social media responses."

@dataclass
class FilterConfig:
    """Configuration for post filtering"""
    min_engagement: int = 5
    keywords_include: list = None
    keywords_exclude: list = None
    language: str = "en"
    max_age_hours: int = 24

@dataclass
class ReplyConfig:
    """Configuration for reply engine"""
    mode: str = "log"  # "log", "post", "both"
    randomize: bool = True
    reply_probability: float = 0.3
    delay_range: list = None  # seconds - will be set to [60, 300] in __post_init__
    max_replies_per_hour: int = 10
    
    def __post_init__(self):
        if self.delay_range is None:
            self.delay_range = [60, 300]

@dataclass
class SchedulerConfig:
    """Configuration for scheduler"""
    enabled: bool = True
    fetch_interval: int = 300  # seconds
    process_interval: int = 600  # seconds
    cleanup_interval: int = 3600  # seconds

@dataclass
class BotConfig:
    """Main bot configuration"""
    source: SourceConfig
    llm: LLMConfig
    filter: FilterConfig
    reply: ReplyConfig
    scheduler: SchedulerConfig
    
    def __post_init__(self):
        if self.filter.keywords_include is None:
            self.filter.keywords_include = []
        if self.filter.keywords_exclude is None:
            self.filter.keywords_exclude = ["spam", "bot", "fake"]

class ConfigManager:
    """Manages bot configuration loading and saving"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config: Optional[BotConfig] = None
    
    def load_config(self) -> BotConfig:
        """Load configuration from file or create default"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            # Convert nested dicts to dataclass instances
            source = SourceConfig(**config_data.get('source', {}))
            llm = LLMConfig(**config_data.get('llm', {}))
            filter_cfg = FilterConfig(**config_data.get('filter', {}))
            reply = ReplyConfig(**config_data.get('reply', {}))
            scheduler = SchedulerConfig(**config_data.get('scheduler', {}))
            
            self.config = BotConfig(
                source=source,
                llm=llm,
                filter=filter_cfg,
                reply=reply,
                scheduler=scheduler
            )
        else:
            self.config = self._create_default_config()
            self.save_config()
        
        return self.config
    
    def save_config(self) -> None:
        """Save current configuration to file"""
        if self.config is None:
            self.config = self._create_default_config()
        
        config_dict = asdict(self.config)
        with open(self.config_path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)
    
    def _create_default_config(self) -> BotConfig:
        """Create default configuration"""
        return BotConfig(
            source=SourceConfig(),
            llm=LLMConfig(),
            filter=FilterConfig(),
            reply=ReplyConfig(),
            scheduler=SchedulerConfig()
        )
    
    def update_from_env(self) -> None:
        """Update configuration from environment variables"""
        if self.config is None:
            self.load_config()
        
        # Update source config from environment
        if os.getenv('TWITTER_API_URL'):
            self.config.source.api_url = os.getenv('TWITTER_API_URL')
        if os.getenv('TWITTER_BEARER_TOKEN'):
            self.config.source.bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        if os.getenv('TWITTER_COOKIE'):
            self.config.source.cookie = os.getenv('TWITTER_COOKIE')
        if os.getenv('TWITTER_USER_AGENT'):
            self.config.source.user_agent = os.getenv('TWITTER_USER_AGENT')
        if os.getenv('TWITTER_CSRF_TOKEN'):
            self.config.source.csrf_token = os.getenv('TWITTER_CSRF_TOKEN')
        
        # Update LLM config from environment
        if os.getenv('OLLAMA_BASE_URL'):
            self.config.llm.base_url = os.getenv('OLLAMA_BASE_URL')
        if os.getenv('OLLAMA_MODEL'):
            self.config.llm.model = os.getenv('OLLAMA_MODEL')
