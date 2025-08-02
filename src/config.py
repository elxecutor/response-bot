"""
AI Response Bot Configuration
"""

import yaml
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file automatically
load_dotenv()

@dataclass
class SourceConfig:
    """Configuration for Twitter data source"""
    type: str = "twitter"
    
    # Twitter API v2 credentials for writing (posting tweets)
    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    access_token_secret: str = ""
    write_bearer_token: str = ""
    
    # Twitter credentials for reading data (fetching tweets)
    read_bearer_token: str = ""
    read_cookie: str = ""
    read_csrf_token: str = ""
    read_user_agent: str = ""
    read_api_url: str = ""
    
    # Tweet tracking configuration
    track_keywords: list = None
    track_users: list = None
    track_hashtags: list = None
    
    # Tweet selection strategy
    selection_strategy: str = "engagement_based"  # random, selective, engagement_based
    max_tweets_per_fetch: int = 20
    fetch_interval: int = 300  # seconds
    
    # Rate limiting
    rate_limit_buffer: float = 0.8  # Use 80% of rate limit
    
    def __post_init__(self):
        if self.track_keywords is None:
            self.track_keywords = ["AI", "machine learning", "python"]
        if self.track_users is None:
            self.track_users = []
        if self.track_hashtags is None:
            self.track_hashtags = ["#AI", "#MachineLearning"]

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
        """Load configuration from file and environment variables"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)
        else:
            # Create default config data if file doesn't exist
            config_data = {}
        
        # Merge environment variables into source config
        source_data = config_data.get('source', {})
        self._merge_env_vars(source_data)
        
        # Convert nested dicts to dataclass instances
        source = SourceConfig(**source_data)
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
        
        # Validate that we have required credentials
        self._validate_credentials()
        
        return self.config
    
    def _merge_env_vars(self, source_data: Dict[str, Any]) -> None:
        """Merge environment variables into source configuration"""
        env_mapping = {
            # Twitter write credentials (for posting)
            'api_key': 'TWITTER_API_KEY',
            'api_secret': 'TWITTER_API_SECRET', 
            'access_token': 'TWITTER_ACCESS_TOKEN',
            'access_token_secret': 'TWITTER_ACCESS_TOKEN_SECRET',
            'write_bearer_token': 'TWITTER_WRITE_BEARER_TOKEN',
            
            # Twitter read credentials (for fetching data)
            'read_bearer_token': 'TWITTER_READ_BEARER_TOKEN',
            'read_cookie': 'TWITTER_READ_COOKIE',
            'read_csrf_token': 'TWITTER_READ_CSRF_TOKEN',
            'read_user_agent': 'TWITTER_READ_USER_AGENT',
            'read_api_url': 'TWITTER_API_URL'  # Map TWITTER_API_URL to read_api_url
        }
        
        for config_key, env_key in env_mapping.items():
            env_value = os.getenv(env_key)
            if env_value:
                source_data[config_key] = env_value
    
    def _validate_credentials(self) -> None:
        """Validate that required credentials are present"""
        if not self.config:
            return
        
        # Check Twitter write credentials (required for posting)
        write_creds = ['api_key', 'api_secret', 'access_token', 'access_token_secret']
        missing_write_creds = []
        
        for cred in write_creds:
            if not getattr(self.config.source, cred, ''):
                missing_write_creds.append(cred)
        
        # Check bearer tokens (at least one required)
        write_bearer = getattr(self.config.source, 'write_bearer_token', '')
        read_bearer = getattr(self.config.source, 'read_bearer_token', '')
        
        if not write_bearer and not read_bearer:
            missing_write_creds.append('write_bearer_token or read_bearer_token')
        
        # Check read credentials (optional but recommended for better rate limiting)
        read_creds = ['read_bearer_token', 'read_cookie', 'read_csrf_token']
        missing_read_creds = []
        read_provided = 0
        
        for cred in read_creds:
            if getattr(self.config.source, cred, ''):
                read_provided += 1
            else:
                missing_read_creds.append(cred)
        
        # Report validation results
        if missing_write_creds:
            env_vars = [f"TWITTER_{cred.upper()}" for cred in missing_write_creds if cred != 'write_bearer_token or read_bearer_token']
            if 'write_bearer_token or read_bearer_token' in missing_write_creds:
                env_vars.extend(['TWITTER_WRITE_BEARER_TOKEN', 'TWITTER_READ_BEARER_TOKEN'])
            print(f"⚠️  Missing Twitter API credentials: {', '.join(missing_write_creds)}")
            print(f"💡 Set these environment variables in .env file: {', '.join(env_vars)}")
            print(f"📖 Or add them to {self.config_path}")
        
        if 0 < read_provided < len(read_creds):
            print(f"⚠️  Partial read credentials provided: {read_provided}/{len(read_creds)}")
            print(f"💡 For optimal performance, provide all read credentials: {', '.join(missing_read_creds)}")
            print("🔄 The bot will fall back to write credentials for reading data")
        elif read_provided == 0 and write_bearer:
            print("ℹ️  Using write credentials for both reading and writing data")
            print("💡 Consider setting up separate read credentials for better rate limit management")
    
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
        """Update configuration from environment variables (legacy method - now automatic)"""
        if self.config is None:
            self.load_config()
        
        # Environment variables are now automatically loaded in load_config()
        # This method is kept for backward compatibility
        
        # Update LLM config from environment (non-credential settings)
        if os.getenv('OLLAMA_BASE_URL'):
            self.config.llm.base_url = os.getenv('OLLAMA_BASE_URL')
        if os.getenv('OLLAMA_MODEL'):
            self.config.llm.model = os.getenv('OLLAMA_MODEL')
