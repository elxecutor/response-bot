"""
Scheduler - Periodically triggers data retrieval and response routines
"""

import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timezone, timedelta
import logging
from dataclasses import dataclass

try:
    from .config import SchedulerConfig
except ImportError:
    from config import SchedulerConfig

logger = logging.getLogger(__name__)

@dataclass
class TaskStats:
    """Statistics for a scheduled task"""
    name: str
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    last_run: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_error: Optional[str] = None
    average_duration: float = 0.0

class ScheduledTask:
    """Represents a scheduled task"""
    
    def __init__(self, name: str, func: Callable, interval: int, *args, **kwargs):
        self.name = name
        self.func = func
        self.interval = interval
        self.args = args
        self.kwargs = kwargs
        self.stats = TaskStats(name)
        self.is_running = False
        self.task: Optional[asyncio.Task] = None
    
    async def run_once(self) -> bool:
        """Run the task once"""
        if self.is_running:
            logger.warning(f"Task {self.name} is already running, skipping")
            return False
        
        self.is_running = True
        start_time = datetime.now(timezone.utc)
        
        try:
            logger.debug(f"Starting task: {self.name}")
            
            if asyncio.iscoroutinefunction(self.func):
                await self.func(*self.args, **self.kwargs)
            else:
                self.func(*self.args, **self.kwargs)
            
            # Update stats
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            self.stats.total_runs += 1
            self.stats.successful_runs += 1
            self.stats.last_run = end_time
            self.stats.last_success = end_time
            self.stats.last_error = None
            
            # Update average duration
            if self.stats.successful_runs == 1:
                self.stats.average_duration = duration
            else:
                self.stats.average_duration = (
                    (self.stats.average_duration * (self.stats.successful_runs - 1) + duration) /
                    self.stats.successful_runs
                )
            
            logger.info(f"Task {self.name} completed successfully in {duration:.2f}s")
            return True
            
        except Exception as e:
            end_time = datetime.now(timezone.utc)
            self.stats.total_runs += 1
            self.stats.failed_runs += 1
            self.stats.last_run = end_time
            self.stats.last_error = str(e)
            
            logger.error(f"Task {self.name} failed: {e}")
            return False
        
        finally:
            self.is_running = False
    
    async def run_loop(self, stop_event: asyncio.Event):
        """Run the task in a loop until stopped"""
        logger.info(f"Starting task loop for {self.name} (interval: {self.interval}s)")
        
        while not stop_event.is_set():
            try:
                await self.run_once()
                
                # Wait for the interval or until stop event
                await asyncio.wait_for(stop_event.wait(), timeout=self.interval)
                
            except asyncio.TimeoutError:
                # Normal timeout, continue to next iteration
                continue
            except Exception as e:
                logger.error(f"Unexpected error in task loop {self.name}: {e}")
                # Wait a bit before retrying
                await asyncio.sleep(min(60, self.interval))
        
        logger.info(f"Task loop for {self.name} stopped")
    
    def cancel(self):
        """Cancel the running task"""
        if self.task and not self.task.done():
            self.task.cancel()
            logger.info(f"Cancelled task: {self.name}")

class Scheduler:
    """Main scheduler that manages periodic tasks"""
    
    def __init__(self, config: SchedulerConfig):
        self.config = config
        self.tasks: Dict[str, ScheduledTask] = {}
        self.is_running = False
        self.stop_event = asyncio.Event()
        self.main_task: Optional[asyncio.Task] = None
    
    def add_task(self, name: str, func: Callable, interval: int, *args, **kwargs):
        """Add a new scheduled task"""
        if name in self.tasks:
            logger.warning(f"Task {name} already exists, replacing")
            self.remove_task(name)
        
        task = ScheduledTask(name, func, interval, *args, **kwargs)
        self.tasks[name] = task
        logger.info(f"Added task: {name} (interval: {interval}s)")
        
        # If scheduler is running, start the new task
        if self.is_running:
            task.task = asyncio.create_task(task.run_loop(self.stop_event))
    
    def remove_task(self, name: str):
        """Remove a scheduled task"""
        if name in self.tasks:
            task = self.tasks[name]
            task.cancel()
            del self.tasks[name]
            logger.info(f"Removed task: {name}")
    
    async def start(self):
        """Start the scheduler"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        if not self.config.enabled:
            logger.info("Scheduler is disabled in configuration")
            return
        
        logger.info("Starting scheduler...")
        self.is_running = True
        self.stop_event.clear()
        
        # Start all tasks
        for name, task in self.tasks.items():
            task.task = asyncio.create_task(task.run_loop(self.stop_event))
            logger.debug(f"Started task: {name}")
        
        # Start the main scheduler loop
        self.main_task = asyncio.create_task(self._scheduler_loop())
        
        logger.info(f"Scheduler started with {len(self.tasks)} tasks")
    
    async def stop(self):
        """Stop the scheduler"""
        if not self.is_running:
            return
        
        logger.info("Stopping scheduler...")
        self.is_running = False
        self.stop_event.set()
        
        # Cancel all tasks
        for task in self.tasks.values():
            task.cancel()
        
        # Cancel main task
        if self.main_task and not self.main_task.done():
            self.main_task.cancel()
        
        # Wait for tasks to complete
        tasks_to_wait = [task.task for task in self.tasks.values() if task.task]
        if self.main_task:
            tasks_to_wait.append(self.main_task)
        
        if tasks_to_wait:
            await asyncio.gather(*tasks_to_wait, return_exceptions=True)
        
        logger.info("Scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler monitoring loop"""
        while not self.stop_event.is_set():
            try:
                # Check for failed tasks and restart them
                for name, task in self.tasks.items():
                    if task.task and task.task.done() and not self.stop_event.is_set():
                        logger.warning(f"Task {name} has stopped, restarting...")
                        task.task = asyncio.create_task(task.run_loop(self.stop_event))
                
                # Log stats periodically
                self._log_scheduler_stats()
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(60)
    
    def _log_scheduler_stats(self):
        """Log scheduler statistics"""
        if not self.tasks:
            return
        
        stats_summary = []
        for name, task in self.tasks.items():
            stats = task.stats
            success_rate = (stats.successful_runs / stats.total_runs * 100) if stats.total_runs > 0 else 0
            stats_summary.append(f"{name}: {stats.total_runs} runs, {success_rate:.1f}% success")
        
        logger.debug(f"Scheduler stats: {'; '.join(stats_summary)}")
    
    async def run_task_now(self, name: str) -> bool:
        """Run a specific task immediately"""
        if name not in self.tasks:
            logger.error(f"Task {name} not found")
            return False
        
        task = self.tasks[name]
        return await task.run_once()
    
    def get_task_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all tasks"""
        stats = {}
        for name, task in self.tasks.items():
            task_stats = task.stats
            stats[name] = {
                'total_runs': task_stats.total_runs,
                'successful_runs': task_stats.successful_runs,
                'failed_runs': task_stats.failed_runs,
                'success_rate': (task_stats.successful_runs / task_stats.total_runs * 100) if task_stats.total_runs > 0 else 0,
                'last_run': task_stats.last_run.isoformat() if task_stats.last_run else None,
                'last_success': task_stats.last_success.isoformat() if task_stats.last_success else None,
                'last_error': task_stats.last_error,
                'average_duration': round(task_stats.average_duration, 2),
                'is_running': task.is_running,
                'interval': task.interval
            }
        return stats
    
    def get_status(self) -> Dict[str, Any]:
        """Get overall scheduler status"""
        return {
            'is_running': self.is_running,
            'enabled': self.config.enabled,
            'total_tasks': len(self.tasks),
            'active_tasks': sum(1 for task in self.tasks.values() if task.task and not task.task.done()),
            'uptime': (datetime.now(timezone.utc) - datetime.now(timezone.utc)).total_seconds() if self.is_running else 0
        }
