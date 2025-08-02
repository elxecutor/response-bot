"""
Main Bot Core - Orchestrates all components
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

try:
    from .config import ConfigManager, BotConfig
    from .input_handler import InputHandler
    from .preprocessor import ContextPreprocessor
    from .llm_engine import LLMEngine
    from .reply_engine import ReplyEngine
    from .scheduler import Scheduler
except ImportError:
    from config import ConfigManager, BotConfig
    from input_handler import InputHandler
    from preprocessor import ContextPreprocessor
    from llm_engine import LLMEngine
    from reply_engine import ReplyEngine
    from scheduler import Scheduler

logger = logging.getLogger(__name__)

class ResponseBot:
    """Main bot class that orchestrates all components"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_manager = ConfigManager(config_path)
        self.config: Optional[BotConfig] = None
        
        # Components
        self.input_handler: Optional[InputHandler] = None
        self.preprocessor: Optional[ContextPreprocessor] = None
        self.llm_engine: Optional[LLMEngine] = None
        self.reply_engine: Optional[ReplyEngine] = None
        self.scheduler: Optional[Scheduler] = None
        
        # State
        self.is_initialized = False
        self.is_running = False
        self.stats = {
            'start_time': None,
            'total_cycles': 0,
            'successful_cycles': 0,
            'failed_cycles': 0,
            'last_cycle': None
        }
    
    async def initialize(self) -> bool:
        """Initialize the bot and all its components"""
        try:
            logger.info("Initializing Response Bot...")
            
            # Load configuration
            self.config = self.config_manager.load_config()
            self.config_manager.update_from_env()
            
            # Initialize components
            self.input_handler = InputHandler(self.config.source)
            self.preprocessor = ContextPreprocessor(self.config.filter)
            self.llm_engine = LLMEngine(self.config.llm)
            self.reply_engine = ReplyEngine(self.config.reply)
            self.scheduler = Scheduler(self.config.scheduler)
            
            # Initialize LLM engine (requires connection to Ollama)
            if not await self.llm_engine.initialize():
                logger.error("Failed to initialize LLM engine")
                return False
            
            # Set up scheduled tasks
            self._setup_scheduled_tasks()
            
            self.is_initialized = True
            logger.info("Response Bot initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing bot: {e}")
            return False
    
    def _setup_scheduled_tasks(self):
        """Setup scheduled tasks"""
        # Main processing cycle
        self.scheduler.add_task(
            "main_cycle",
            self._run_main_cycle,
            self.config.scheduler.process_interval
        )
        
        # Data fetching (can be more frequent than processing)
        self.scheduler.add_task(
            "fetch_data",
            self._fetch_data_task,
            self.config.scheduler.fetch_interval
        )
        
        # Cleanup old data
        self.scheduler.add_task(
            "cleanup",
            self._cleanup_task,
            self.config.scheduler.cleanup_interval
        )
    
    async def start(self):
        """Start the bot"""
        if not self.is_initialized:
            logger.error("Bot not initialized. Call initialize() first.")
            return
        
        if self.is_running:
            logger.warning("Bot is already running")
            return
        
        logger.info("Starting Response Bot...")
        self.is_running = True
        self.stats['start_time'] = datetime.now(timezone.utc)
        
        # Start scheduler
        await self.scheduler.start()
        
        logger.info("Response Bot started successfully")
    
    async def stop(self):
        """Stop the bot"""
        if not self.is_running:
            return
        
        logger.info("Stopping Response Bot...")
        self.is_running = False
        
        # Stop scheduler
        if self.scheduler:
            await self.scheduler.stop()
        
        # Close resources
        if self.input_handler:
            await self.input_handler.close()
        if self.llm_engine:
            await self.llm_engine.close()
        
        logger.info("Response Bot stopped")
    
    async def run_once(self) -> Dict[str, Any]:
        """Run one complete cycle manually"""
        if not self.is_initialized:
            raise RuntimeError("Bot not initialized")
        
        logger.info("Running manual cycle...")
        return await self._run_main_cycle()
    
    async def _run_main_cycle(self) -> Dict[str, Any]:
        """Run one complete processing cycle"""
        cycle_start = datetime.now(timezone.utc)
        results = {
            'cycle_start': cycle_start.isoformat(),
            'posts_fetched': 0,
            'posts_processed': 0,
            'responses_generated': 0,
            'responses_sent': 0,
            'responses_logged': 0,
            'errors': []
        }
        
        try:
            self.stats['total_cycles'] += 1
            
            # Get stored data (recent posts)
            stored_posts = self.input_handler.get_stored_data(limit=50)
            if not stored_posts:
                logger.info("No posts available for processing")
                return results
            
            results['posts_fetched'] = len(stored_posts)
            
            # Process posts
            processed_posts = self.preprocessor.process_posts(stored_posts)
            if not processed_posts:
                logger.info("No posts passed filtering")
                return results
            
            results['posts_processed'] = len(processed_posts)
            
            # Generate responses for top posts
            top_posts = processed_posts[:10]  # Limit to top 10 posts
            responses = await self.llm_engine.generate_batch_responses(top_posts)
            results['responses_generated'] = len(responses)
            
            if not responses:
                logger.info("No responses generated")
                return results
            
            # Process responses through reply engine
            reply_results = await self.reply_engine.process_responses(responses, top_posts)
            results['responses_sent'] = len(reply_results['sent'])
            results['responses_logged'] = len(reply_results['logged'])
            
            # Update stats
            self.stats['successful_cycles'] += 1
            self.stats['last_cycle'] = cycle_start
            
            cycle_duration = (datetime.now(timezone.utc) - cycle_start).total_seconds()
            logger.info(f"Cycle completed successfully in {cycle_duration:.2f}s: "
                       f"{results['posts_processed']} posts processed, "
                       f"{results['responses_generated']} responses generated, "
                       f"{results['responses_sent']} sent")
            
            return results
            
        except Exception as e:
            self.stats['failed_cycles'] += 1
            error_msg = f"Error in main cycle: {e}"
            logger.error(error_msg)
            results['errors'].append(error_msg)
            return results
    
    async def _fetch_data_task(self):
        """Fetch new data from sources"""
        try:
            new_posts = await self.input_handler.fetch_new_data()
            if new_posts:
                logger.info(f"Fetched {len(new_posts)} new posts")
            
            # Save data dump periodically
            await self.input_handler.save_data_dump()
            
        except Exception as e:
            logger.error(f"Error in fetch data task: {e}")
    
    async def _cleanup_task(self):
        """Clean up old data"""
        try:
            # Clean old posts from input handler
            self.input_handler.clear_old_data(self.config.filter.max_age_hours)
            
            # Clean old response data
            await self.reply_engine.cleanup_old_data(days=7)
            
            logger.debug("Cleanup task completed")
            
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive bot status"""
        status = {
            'bot': {
                'initialized': self.is_initialized,
                'running': self.is_running,
                'uptime': None,
                'stats': self.stats.copy()
            }
        }
        
        if self.stats['start_time']:
            uptime = (datetime.now(timezone.utc) - self.stats['start_time']).total_seconds()
            status['bot']['uptime'] = round(uptime, 2)
        
        # Add component statuses
        if self.scheduler:
            status['scheduler'] = self.scheduler.get_status()
            status['tasks'] = self.scheduler.get_task_stats()
        
        if self.reply_engine:
            status['reply_engine'] = self.reply_engine.get_stats()
        
        if self.input_handler:
            stored_data = self.input_handler.get_stored_data()
            status['input_handler'] = {
                'stored_posts': len(stored_data),
                'last_fetch': self.input_handler.last_fetch.isoformat() if self.input_handler.last_fetch else None
            }
        
        return status
    
    async def run_task(self, task_name: str) -> bool:
        """Run a specific scheduled task manually"""
        if not self.scheduler:
            logger.error("Scheduler not initialized")
            return False
        
        return await self.scheduler.run_task_now(task_name)
    
    def reload_config(self):
        """Reload configuration from file"""
        try:
            self.config = self.config_manager.load_config()
            self.config_manager.update_from_env()
            logger.info("Configuration reloaded")
        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")
    
    async def test_components(self) -> Dict[str, bool]:
        """Test all components"""
        results = {}
        
        # Test LLM engine
        try:
            if self.llm_engine:
                results['llm_engine'] = await self.llm_engine.check_health()
            else:
                results['llm_engine'] = False
        except Exception:
            results['llm_engine'] = False
        
        # Test input handler
        try:
            # Try to fetch a small amount of data
            test_data = await self.input_handler.fetch_new_data() if self.input_handler else []
            results['input_handler'] = True
        except Exception:
            results['input_handler'] = False
        
        # Test other components
        results['preprocessor'] = self.preprocessor is not None
        results['reply_engine'] = self.reply_engine is not None
        results['scheduler'] = self.scheduler is not None
        
        return results
