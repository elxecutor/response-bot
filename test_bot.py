#!/usr/bin/env python3
"""
Test script for AI Response Bot components
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from config import ConfigManager
from input_handler import InputHandler
from preprocessor import ContextPreprocessor
from llm_engine import LLMEngine
from reply_engine import ReplyEngine

async def test_basic_setup():
    """Test basic bot setup and configuration"""
    print("🧪 Testing Basic Setup")
    print("-" * 30)
    
    # Test configuration loading
    try:
        config_manager = ConfigManager("config.example.yaml")
        config = config_manager.load_config()
        print("✅ Configuration loading works")
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return False
    
    return True

async def test_ollama_connection():
    """Test Ollama connection and model availability"""
    print("\n🔗 Testing Ollama Connection")
    print("-" * 30)
    
    try:
        # Create basic config for testing
        config_manager = ConfigManager("config.example.yaml")
        config = config_manager.load_config()
        
        llm_engine = LLMEngine(config.llm)
        
        # Test connection
        is_healthy = await llm_engine.client.check_health()
        if is_healthy:
            print("✅ Ollama service is running")
        else:
            print("❌ Ollama service is not running")
            return False
        
        # Test model availability
        models = await llm_engine.client.list_models()
        if models:
            print(f"✅ Available models: {', '.join(models)}")
            
            # Check if configured model is available
            if config.llm.model in models:
                print(f"✅ Configured model '{config.llm.model}' is available")
            else:
                print(f"⚠️ Configured model '{config.llm.model}' not found")
                print(f"   Available models: {', '.join(models)}")
        else:
            print("❌ No models available")
            return False
        
        await llm_engine.close()
        return True
        
    except Exception as e:
        print(f"❌ Ollama connection test failed: {e}")
        return False

async def test_components():
    """Test individual components"""
    print("\n🔧 Testing Components")
    print("-" * 30)
    
    try:
        config_manager = ConfigManager("config.example.yaml")
        config = config_manager.load_config()
        
        # Test preprocessor
        preprocessor = ContextPreprocessor(config.filter)
        print("✅ Preprocessor initialized")
        
        # Test reply engine
        reply_engine = ReplyEngine(config.reply)
        print("✅ Reply engine initialized")
        
        # Test with mock data
        mock_posts = [
            {
                'id': 'test_1',
                'text': 'This is a test post for the AI bot!',
                'created_at': 'Mon Jan 01 12:00:00 +0000 2024',
                'user': {
                    'id_str': 'test_user',
                    'screen_name': 'testuser',
                    'name': 'Test User',
                    'followers_count': 100
                },
                'engagement': {
                    'retweet_count': 5,
                    'favorite_count': 10,
                    'reply_count': 2,
                    'quote_count': 1
                },
                'metadata': {
                    'source': 'test',
                    'lang': 'en',
                    'possibly_sensitive': False
                }
            }
        ]
        
        # Test preprocessing
        processed_posts = preprocessor.process_posts(mock_posts)
        if processed_posts:
            print(f"✅ Preprocessor processed {len(processed_posts)} posts")
        else:
            print("⚠️ No posts passed preprocessing filters")
        
        return True
        
    except Exception as e:
        print(f"❌ Component test failed: {e}")
        return False

async def test_llm_generation():
    """Test LLM response generation"""
    print("\n🤖 Testing LLM Generation")
    print("-" * 30)
    
    try:
        config_manager = ConfigManager("config.example.yaml")
        config = config_manager.load_config()
        
        llm_engine = LLMEngine(config.llm)
        
        # Initialize LLM engine
        if not await llm_engine.initialize():
            print("❌ Failed to initialize LLM engine")
            return False
        
        # Test simple generation
        test_prompt = "Generate a friendly response to: 'Just finished my morning run! Feeling great!'"
        response = await llm_engine.client.generate_response(test_prompt)
        
        if response:
            print("✅ LLM response generation works")
            print(f"   Sample response: {response[:100]}...")
        else:
            print("❌ LLM response generation failed")
            await llm_engine.close()
            return False
        
        await llm_engine.close()
        return True
        
    except Exception as e:
        print(f"❌ LLM generation test failed: {e}")
        return False

async def test_full_pipeline():
    """Test the full processing pipeline"""
    print("\n🔄 Testing Full Pipeline")
    print("-" * 30)
    
    try:
        config_manager = ConfigManager("config.example.yaml")
        config = config_manager.load_config()
        
        # Initialize components
        preprocessor = ContextPreprocessor(config.filter)
        llm_engine = LLMEngine(config.llm)
        reply_engine = ReplyEngine(config.reply)
        
        if not await llm_engine.initialize():
            print("❌ Failed to initialize LLM engine")
            return False
        
        # Mock data
        mock_posts = [
            {
                'id': 'pipeline_test_1',
                'text': 'Just discovered this amazing AI tool! Has anyone tried it?',
                'created_at': 'Mon Jan 01 12:00:00 +0000 2024',
                'user': {
                    'id_str': 'test_user',
                    'screen_name': 'techuser',
                    'name': 'Tech Enthusiast',
                    'followers_count': 500
                },
                'engagement': {
                    'retweet_count': 15,
                    'favorite_count': 25,
                    'reply_count': 8,
                    'quote_count': 3
                },
                'metadata': {
                    'source': 'test',
                    'lang': 'en',
                    'possibly_sensitive': False
                }
            }
        ]
        
        # Process through pipeline
        processed_posts = preprocessor.process_posts(mock_posts)
        if not processed_posts:
            print("❌ No posts passed preprocessing")
            await llm_engine.close()
            return False
        
        # Generate responses
        responses = await llm_engine.generate_batch_responses(processed_posts)
        if not responses:
            print("❌ No responses generated")
            await llm_engine.close()
            return False
        
        # Process through reply engine
        results = await reply_engine.process_responses(responses, processed_posts)
        
        print("✅ Full pipeline test completed")
        print(f"   Processed: {len(processed_posts)} posts")
        print(f"   Generated: {len(responses)} responses")
        print(f"   Logged: {len(results.get('logged', []))}")
        
        await llm_engine.close()
        return True
        
    except Exception as e:
        print(f"❌ Full pipeline test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 AI Response Bot - Component Tests")
    print("=" * 50)
    
    tests = [
        ("Basic Setup", test_basic_setup),
        ("Ollama Connection", test_ollama_connection),
        ("Components", test_components),
        ("LLM Generation", test_llm_generation),
        ("Full Pipeline", test_full_pipeline),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False
    
    # Summary
    print("\n📊 Test Summary")
    print("=" * 50)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Bot is ready to use.")
        return 0
    else:
        print("⚠️ Some tests failed. Please check the setup.")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
