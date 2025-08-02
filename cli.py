#!/usr/bin/env python3
"""
Response Bot CLI - Command Line Interface
"""

import asyncio
import argparse
import json
import sys
import logging
from pathlib import Path
from typing import Dict, Any

from src.bot_core import ResponseBot
from src.config import ConfigManager

def setup_logging(level: str = "INFO"):
    """Setup logging configuration"""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('bot.log')
        ]
    )

def print_status(status: Dict[str, Any]):
    """Pretty print bot status"""
    print("\n📊 Bot Status")
    print("=" * 50)
    
    bot_status = status.get('bot', {})
    print(f"Initialized: {'✅' if bot_status.get('initialized') else '❌'}")
    print(f"Running: {'✅' if bot_status.get('running') else '❌'}")
    
    if bot_status.get('uptime'):
        uptime_hours = bot_status['uptime'] / 3600
        print(f"Uptime: {uptime_hours:.1f} hours")
    
    stats = bot_status.get('stats', {})
    if stats.get('total_cycles', 0) > 0:
        success_rate = stats['successful_cycles'] / stats['total_cycles'] * 100
        print(f"Cycles: {stats['total_cycles']} total, {success_rate:.1f}% success")
    
    # Reply engine stats
    reply_stats = status.get('reply_engine', {})
    if reply_stats:
        print(f"\n💬 Reply Engine")
        print(f"Responses sent: {reply_stats.get('responses_sent', 0)}")
        print(f"Responses logged: {reply_stats.get('responses_logged', 0)}")
        print(f"Rate limit remaining: {reply_stats.get('rate_limit_remaining', 0)}")
    
    # Input handler stats
    input_stats = status.get('input_handler', {})
    if input_stats:
        print(f"\n📥 Input Handler")
        print(f"Stored posts: {input_stats.get('stored_posts', 0)}")
        if input_stats.get('last_fetch'):
            print(f"Last fetch: {input_stats['last_fetch']}")
    
    # Scheduler stats
    scheduler_status = status.get('scheduler', {})
    if scheduler_status:
        print(f"\n⏰ Scheduler")
        print(f"Enabled: {'✅' if scheduler_status.get('enabled') else '❌'}")
        print(f"Active tasks: {scheduler_status.get('active_tasks', 0)}")
    
    # Task stats
    task_stats = status.get('tasks', {})
    if task_stats:
        print(f"\n📋 Tasks")
        for task_name, task_info in task_stats.items():
            success_rate = task_info.get('success_rate', 0)
            status_icon = '✅' if success_rate > 80 else '⚠️' if success_rate > 50 else '❌'
            print(f"  {status_icon} {task_name}: {task_info.get('total_runs', 0)} runs, {success_rate:.1f}% success")

async def cmd_start(bot: ResponseBot, args):
    """Start the bot"""
    print("🚀 Starting bot...")
    
    if not await bot.initialize():
        print("❌ Failed to initialize bot")
        return 1
    
    await bot.start()
    
    try:
        print("✅ Bot started successfully. Press Ctrl+C to stop.")
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(10)
            
            # Optionally print status updates
            if args.verbose:
                status = bot.get_status()
                cycles = status.get('bot', {}).get('stats', {}).get('total_cycles', 0)
                if cycles > 0 and cycles % 10 == 0:  # Every 10 cycles
                    print(f"📊 Completed {cycles} cycles")
    
    except KeyboardInterrupt:
        print("\n🛑 Stopping bot...")
        await bot.stop()
        print("✅ Bot stopped")
        return 0

async def cmd_run_once(bot: ResponseBot, args):
    """Run one cycle"""
    print("🔄 Running one cycle...")
    
    if not await bot.initialize():
        print("❌ Failed to initialize bot")
        return 1
    
    results = await bot.run_once()
    
    print("✅ Cycle completed")
    print(f"📊 Results:")
    print(f"  Posts fetched: {results['posts_fetched']}")
    print(f"  Posts processed: {results['posts_processed']}")
    print(f"  Responses generated: {results['responses_generated']}")
    print(f"  Responses sent: {results['responses_sent']}")
    print(f"  Responses logged: {results['responses_logged']}")
    
    if results['errors']:
        print("❌ Errors:")
        for error in results['errors']:
            print(f"  {error}")
    
    await bot.stop()
    return 0

async def cmd_status(bot: ResponseBot, args):
    """Show bot status"""
    try:
        if not await bot.initialize():
            print("❌ Failed to initialize bot")
            return 1
        
        status = bot.get_status()
        
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print_status(status)
        
        await bot.stop()
        return 0
        
    except Exception as e:
        print(f"❌ Error getting status: {e}")
        return 1

async def cmd_test(bot: ResponseBot, args):
    """Test bot components"""
    print("🧪 Testing bot components...")
    
    if not await bot.initialize():
        print("❌ Failed to initialize bot")
        return 1
    
    results = await bot.test_components()
    
    print("🧪 Component Test Results:")
    for component, status in results.items():
        icon = '✅' if status else '❌'
        print(f"  {icon} {component}")
    
    all_passed = all(results.values())
    if all_passed:
        print("✅ All components passed")
    else:
        print("❌ Some components failed")
    
    await bot.stop()
    return 0 if all_passed else 1

async def cmd_config(bot: ResponseBot, args):
    """Manage configuration"""
    config_manager = ConfigManager(args.config)
    
    if args.show:
        config = config_manager.load_config()
        print("📋 Current Configuration:")
        print(json.dumps(config.__dict__, indent=2, default=str))
    
    elif args.create_default:
        print("📝 Creating default configuration...")
        config_manager.load_config()  # This creates default if not exists
        config_manager.save_config()
        print(f"✅ Default configuration saved to {args.config}")
    
    return 0

def create_parser():
    """Create argument parser"""
    parser = argparse.ArgumentParser(
        description="AI Response Bot - Automated social media response generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s start                    # Start the bot
  %(prog)s run-once                 # Run one cycle
  %(prog)s status                   # Show status
  %(prog)s test                     # Test components
  %(prog)s config --show            # Show configuration
  %(prog)s config --create-default  # Create default config
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file path (default: config.yaml)'
    )
    
    parser.add_argument(
        '--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Log level (default: INFO)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Start command
    start_parser = subparsers.add_parser('start', help='Start the bot')
    
    # Run once command
    once_parser = subparsers.add_parser('run-once', help='Run one cycle and exit')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show bot status')
    status_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test bot components')
    
    # Config command
    config_parser = subparsers.add_parser('config', help='Manage configuration')
    config_group = config_parser.add_mutually_exclusive_group(required=True)
    config_group.add_argument('--show', action='store_true', help='Show current configuration')
    config_group.add_argument('--create-default', action='store_true', help='Create default configuration')
    
    return parser

async def main():
    """Main CLI function"""
    parser = create_parser()
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    # Show help if no command
    if not args.command:
        parser.print_help()
        return 0
    
    # Create bot instance
    bot = ResponseBot(args.config)
    
    # Command dispatch
    commands = {
        'start': cmd_start,
        'run-once': cmd_run_once,
        'status': cmd_status,
        'test': cmd_test,
        'config': cmd_config
    }
    
    command_func = commands.get(args.command)
    if command_func:
        try:
            return await command_func(bot, args)
        except KeyboardInterrupt:
            print("\n🛑 Interrupted")
            return 1
        except Exception as e:
            print(f"❌ Error: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
