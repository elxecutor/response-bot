"""
Enhanced Twitter Bot optimized for X's Recommendation Algorithm
Based on analysis of the open-source algorithm repository

Key Algorithm Insights Applied:
1. Text Quality Scoring (50% length, 25% entropy, 10% readability, 10% caps, 5% links)
2. Engagement Signal Prioritization (Replies 10x > Favorites 1x)
3. Temporal Decay (24-hour half-life on engagement)
4. SimClusters community positioning
5. Negative signal avoidance
"""

import os
import requests
import random
import tweepy
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import time
import base64
import json
import re

from google import genai  # Gemini API client (google-genai package)
from google.genai import types  # used for multimodal parts and search grounding
from game_theory import GameTheoryEngine

# Load environment variables from .env
load_dotenv()

# Fetch credentials from .env
api_key = os.getenv('TWITTER_API_KEY')
api_secret = os.getenv('TWITTER_API_SECRET')
bearer_token = os.getenv('TWITTER_READ_BEARER_TOKEN')
cookie = os.getenv('TWITTER_READ_COOKIE')
csrf_token = os.getenv('TWITTER_READ_CSRF_TOKEN')
user_agent = os.getenv('TWITTER_READ_USER_AGENT')
api_url = os.getenv('TWITTER_API_URL')

# Twitter API v2 credentials
client_id = os.getenv('TWITTER_CLIENT_ID')
client_secret = os.getenv('TWITTER_CLIENT_SECRET')
access_token = os.getenv('TWITTER_ACCESS_TOKEN')
access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
bearer_token_write = os.getenv('TWITTER_WRITE_BEARER_TOKEN')

# Gemini API key (used by google-generativeai)
gemini_api_key = os.getenv('GEMINI_API_KEY')
if gemini_api_key:
    client = genai.Client(api_key=gemini_api_key)
else:
    print("Warning: GEMINI_API_KEY not set, AI responses will fail if invoked")
    client = genai.Client()

# JSON file for tracking replied tweets (git-friendly)
HISTORY_FILE = 'bot_history.json'

# Bot's own username (fetched at runtime)
BOT_USERNAME = None

def get_bot_username():
    """Get the bot's own username from Twitter API"""
    global BOT_USERNAME
    if BOT_USERNAME is None:
        try:
            client = tweepy.Client(
                bearer_token=bearer_token_write,
                consumer_key=api_key,
                consumer_secret=api_secret,
                access_token=access_token,
                access_token_secret=access_token_secret
            )
            me = client.get_me()
            BOT_USERNAME = me.data.username
            print(f"Bot username: @{BOT_USERNAME}")
        except Exception as e:
            print(f"Error getting bot username: {e}")
            BOT_USERNAME = None
    return BOT_USERNAME

def load_history():
    """Load bot history from JSON file"""
    base_history = {
        'replied_tweets': [],
        'game_theory': {
            'regret': {},
            'strategy_counts': {},
            'iterations': 0
        }
    }
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            print(f"Warning: Could not load {HISTORY_FILE}, starting fresh")
            return base_history
        if isinstance(data, dict):
            data.setdefault('replied_tweets', [])
            data.setdefault('game_theory', {
                'regret': {},
                'strategy_counts': {},
                'iterations': 0
            })
            return data
        return base_history
    return base_history

def save_history(history):
    """Save bot history to JSON file"""
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except IOError as e:
        print(f"Error saving history: {e}")

def clean_old_history():
    """Clean history entries older than 3 days"""
    history = load_history()
    cutoff_date = datetime.now() - timedelta(days=3)
    
    # Filter replied_tweets
    original_replied_count = len(history.get('replied_tweets', []))
    history['replied_tweets'] = [
        entry for entry in history.get('replied_tweets', [])
        if datetime.fromisoformat(entry['replied_at']) > cutoff_date
    ]
    new_replied_count = len(history['replied_tweets'])
    
    save_history(history)
    print(f"Cleaned history: replied_tweets {original_replied_count} -> {new_replied_count}")

def has_replied_to_tweet(tweet_id):
    """Check if we've already replied to this tweet"""
    history = load_history()
    return any(entry['tweet_id'] == tweet_id for entry in history.get('replied_tweets', []))

def mark_tweet_as_replied(tweet_id, user, action):
    """Mark a tweet as replied to"""
    history = load_history()
    
    # Check if already exists (shouldn't happen, but just in case)
    if not any(entry['tweet_id'] == tweet_id for entry in history.get('replied_tweets', [])):
        history['replied_tweets'].append({
            'tweet_id': tweet_id,
            'user': user,
            'replied_at': datetime.now().isoformat(),
            'action': action
        })
        save_history(history)

def get_reply_stats():
    """Get statistics on bot activity"""
    history = load_history()
    replied_tweets = history.get('replied_tweets', [])
    
    # Total replies
    total = len(replied_tweets)
    
    # Replies by action
    by_action = {}
    for entry in replied_tweets:
        action = entry.get('action', 'unknown')
        by_action[action] = by_action.get(action, 0) + 1
    
    # Replies today
    today = datetime.now().date().isoformat()
    today_count = sum(1 for entry in replied_tweets if entry.get('replied_at', '').startswith(today))
    
    return {
        'total': total,
        'by_action': by_action,
        'today': today_count
    }

def extract_image_urls(legacy_tweet):
    """Return a list of photo URLs from tweet legacy entities"""
    if not legacy_tweet:
        return []
    media_entities = legacy_tweet.get('extended_entities', {}).get('media')
    if not media_entities:
        media_entities = legacy_tweet.get('entities', {}).get('media', [])
    image_urls = []
    for media in media_entities or []:
        if media.get('type') == 'photo':
            url = media.get('media_url_https') or media.get('media_url') or media.get('url')
            if url:
                image_urls.append(url)
    return image_urls

# Headers for the request (mimicking a browser to avoid blocks)
headers = {
    'Authorization': f'Bearer {bearer_token}',
    'Cookie': cookie,
    'X-Csrf-Token': csrf_token,
    'User-Agent': user_agent,
    'Content-Type': 'application/json',
    'Referer': 'https://x.com/home',
    'Origin': 'https://x.com',
    'x-twitter-active-user': 'yes',
    'x-twitter-auth-type': 'OAuth2Session',
    'x-twitter-client-language': 'en',
}
headers = {
    'Authorization': f'Bearer {bearer_token}',
    'Cookie': cookie,
    'X-Csrf-Token': csrf_token,
    'User-Agent': user_agent,
    'Content-Type': 'application/json',
    'Referer': 'https://x.com/home',
    'Origin': 'https://x.com',
    'x-twitter-active-user': 'yes',
    'x-twitter-auth-type': 'OAuth2Session',
    'x-twitter-client-language': 'en',
}

def fetch_home_timeline():
    """
    Fetch home timeline with enhanced metadata for algorithm-aware selection
    """
    try:
        # Payload for HomeLatestTimeline POST request
        payload = {
            "variables": {
                "count": 40,  # Increased from 20 for better selection
                "includePromotedContent": False,
                "latestControlAvailable": True,
                "requestContext": "launch"
            },
            "features": {
                "rweb_video_screen_enabled": False,
                "payments_enabled": False,
                "profile_label_improvements_pcf_label_in_post_enabled": True,
                "responsive_web_profile_redirect_enabled": False,
                "rweb_tipjar_consumption_enabled": True,
                "verified_phone_label_enabled": False,
                "creator_subscriptions_tweet_preview_api_enabled": True,
                "responsive_web_graphql_timeline_navigation_enabled": True,
                "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                "premium_content_api_read_enabled": False,
                "communities_web_enable_tweet_community_results_fetch": True,
                "c9s_tweet_anatomy_moderator_badge_enabled": True,
                "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
                "responsive_web_grok_analyze_post_followups_enabled": True,
                "responsive_web_jetfuel_frame": True,
                "responsive_web_grok_share_attachment_enabled": True,
                "articles_preview_enabled": True,
                "responsive_web_edit_tweet_api_enabled": True,
                "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
                "view_counts_everywhere_api_enabled": True,
                "longform_notetweets_consumption_enabled": True,
                "responsive_web_twitter_article_tweet_consumption_enabled": True,
                "tweet_awards_web_tipping_enabled": False,
                "responsive_web_grok_show_grok_translated_post": False,
                "responsive_web_grok_analysis_button_from_backend": True,
                "creator_subscriptions_quote_tweet_preview_enabled": False,
                "freedom_of_speech_not_reach_fetch_enabled": True,
                "standardized_nudges_misinfo": True,
                "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
                "longform_notetweets_rich_text_read_enabled": True,
                "longform_notetweets_inline_media_enabled": True,
                "responsive_web_grok_image_annotation_enabled": True,
                "responsive_web_grok_imagine_annotation_enabled": True,
                "responsive_web_grok_community_note_auto_translation_is_enabled": False,
                "responsive_web_enhance_cards_enabled": False
            },
            "queryId": "rA4kQTNf-wOA063umfp08Q"
        }
        
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        tweets = []
        # Parse the GraphQL response with enhanced metadata
        instructions = data.get('data', {}).get('home', {}).get('home_timeline_urt', {}).get('instructions', [])
        for instruction in instructions:
            if instruction.get('type') == 'TimelineAddEntries':
                entries = instruction.get('entries', [])
                for entry in entries:
                    content = entry.get('content', {})
                    
                    # Skip promoted content - comprehensive ad filtering
                    if 'promotedMetadata' in content:
                        print(f"⊘ Skipping promoted tweet (has promotedMetadata)")
                        continue
                    
                    # Skip entries that are marked as promoted/ads
                    if content.get('entryType') == 'TimelineTimelineModule':
                        # Sometimes ads come in modules
                        continue
                    
                    # Skip if entry ID contains 'promoted'
                    entry_id = entry.get('entryId', '')
                    if 'promoted' in entry_id.lower() or 'ad-' in entry_id.lower():
                        print(f"⊘ Skipping promoted entry: {entry_id}")
                        continue
                    
                    tweet = content.get('itemContent', {}).get('tweet_results', {}).get('result', {})
                    if tweet and tweet.get('__typename') == 'Tweet':
                        legacy = tweet.get('legacy', {})
                        tweet_id = tweet.get('rest_id')
                        full_text = legacy.get('full_text')
                        user_result = tweet.get('core', {}).get('user_results', {}).get('result', {})
                        user = user_result.get('core', {}).get('screen_name')
                        
                        # Skip if user has promoted/ad indicators
                        if user_result.get('is_promoted', False):
                            print(f"⊘ Skipping tweet from promoted user: @{user}")
                            continue
                        
                        # Skip retweets
                        if legacy.get('retweeted_status'):
                            continue
                        
                        if tweet_id and full_text and user:
                            # Extract engagement metrics (Algorithm uses these for ranking)
                            engagement_data = {
                                'favorite_count': legacy.get('favorite_count', 0),
                                'reply_count': legacy.get('reply_count', 0),
                                'retweet_count': legacy.get('retweet_count', 0),
                                'quote_count': legacy.get('quote_count', 0),
                            }
                            
                            media_entities = legacy.get('extended_entities', {}).get('media')
                            if not media_entities:
                                media_entities = legacy.get('entities', {}).get('media', [])

                            # Check for media (algorithm favors visual content)
                            has_media = bool(media_entities)
                            has_video = any(m.get('type') == 'video' for m in media_entities)
                            image_urls = extract_image_urls(legacy)
                            
                            # Check for question (algorithm detects and favors questions)
                            has_question = '?' in full_text
                            
                            tweets.append({
                                'id': tweet_id,
                                'text': full_text,
                                'user': user,
                                'engagement': engagement_data,
                                'has_media': has_media,
                                'has_video': has_video,
                                'has_question': has_question,
                                'created_at': legacy.get('created_at'),
                                'media_urls': image_urls,
                            })
        
        return tweets
    except requests.RequestException as e:
        print(f"Error fetching timeline: {e}")
        return []

def select_optimal_tweet(tweets):
    """
    Select tweet using algorithm-aware scoring:
    - Prioritize tweets with engagement potential (questions, discussions)
    - Avoid tweets likely to generate negative signals
    - Consider recency (temporal decay in algorithm)
    - Skip tweets we've already replied to
    - Skip our own tweets
    """
    if not tweets:
        return None
    
    scored_tweets = []
    bot_username = get_bot_username()
    
    for tweet in tweets:
        # Skip if we've already replied to this tweet
        if has_replied_to_tweet(tweet['id']):
            continue
        
        # Skip our own tweets
        if bot_username and tweet.get('user') == bot_username:
            print(f"⊘ Skipping own tweet from @{tweet['user']}")
            continue
        

        score = 0
        
        # Favor tweets with questions (generate reply signals - 10x weight in algorithm)
        if tweet.get('has_question'):
            score += 50
        
        # Favor tweets with moderate engagement (not too viral, not dead)
        engagement = tweet.get('engagement', {})
        total_engagement = (
            engagement.get('reply_count', 0) * 10 +  # Replies weighted 10x in algorithm
            engagement.get('favorite_count', 0) +
            engagement.get('quote_count', 0) * 5 +
            engagement.get('retweet_count', 0) * 3
        )
        
        # Sweet spot: some engagement but not overwhelming
        if 10 < total_engagement < 1000:
            score += 30
        elif total_engagement <= 10:
            score += 20  # Still good for early engagement
        
        # Media is now a neutral/positive signal; we no longer penalize images
        # (the bot will even fetch them for Gemini).  A small bonus keeps them
        # competitive when sorting, but it's not required.
        if tweet.get('has_media'):
            score += 5  # gentle encouragement for visual content
        
        # Text length consideration (easier to respond to substantial tweets)
        text_len = len(tweet.get('text', ''))
        if 50 < text_len < 280:
            score += 15
        
        # Add some randomness to avoid patterns
        score += random.randint(0, 20)
        
        scored_tweets.append((score, tweet))
    
    # Sort by score and pick from top 5 to maintain some randomness
    scored_tweets.sort(reverse=True, key=lambda x: x[0])
    top_candidates = scored_tweets[:5]
    
    if top_candidates:
        selected = random.choice(top_candidates)[1]
        print(f"Tweet selection score: {scored_tweets[0][0]}")
        return selected
    
    return random.choice(tweets)

def generate_reply(tweet_text, tweet_metadata=None):
    """
    Generate reply optimized for X's text quality algorithm
    
    Algorithm scoring weights:
    - Length: 50% (optimal 100-200 chars)
    - Entropy: 25% (diverse vocabulary)
    - Readability: 10% (clear language)
    - Shout: 10% (minimal caps)
    - Links: 5% (strategic use)
    """
    # Build prompt for Gemini with casual persona and negative constraints
    prompt = f"""You are a casual, slightly cynical, but insightful Twitter user. Write a human-like reply to the tweet below.
    
    Rules for your human flair:
    - Keep it under 100 characters. Short and punchy.
    - Vary your tone: you can be sarcastic, ask a rhetorical question, or just make a blunt observation.
    - Feel free to use all lowercase letters for a more casual, internet-native vibe.
    - NEVER start with AI filler like "That's a great point", "I agree", or "Interesting take". 
    - Return ONLY the plain response text. DO NOT use emojis, hashtags, or markdown.

    Tweet: '{tweet_text}'
    Response:"""

    try:
        # build multimodal contents list; include image if available
        contents = [types.Part.from_text(text=prompt)]
        if tweet_metadata:
            urls = tweet_metadata.get('media_urls', [])
            if urls:
                try:
                    img_resp = requests.get(urls[0], timeout=10)
                    img_resp.raise_for_status()
                    mime = img_resp.headers.get('Content-Type', 'image/jpeg')
                    contents.append(
                        types.Part.from_bytes(data=img_resp.content, mime_type=mime)
                    )
                except Exception as dl_err:
                    print(f"⚠️ Could not download media for prompt: {dl_err}")
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],
                temperature=0.95,  # increased randomness
                system_instruction="You are a highly opinionated, casual internet user. You hate sounding like a corporate AI."
            ),
        )
        reply = resp.text.strip()

        # Remove quotes if AI added them
        reply = reply.strip('"\'')

        # Remove any markdown formatting that slipped through
        reply = re.sub(r'\*([^*]+)\*', r'\1', reply)  # Remove *bold*
        reply = re.sub(r'_([^_]+)_', r'\1', reply)    # Remove _italic_
        reply = re.sub(r'`([^`]+)`', r'\1', reply)    # Remove `code`

        # Remove hashtags (replace with plain text)
        reply = re.sub(r'#(\w+)', r'\1', reply)

        # Remove emojis
        reply = re.sub(r'[^\x00-\x7F]+', '', reply)

        # Validate and optimize length
        if len(reply) > 280:
            reply = reply[:277] + "..."

        print(f"\n{'='*60}")
        print(f"Generated Reply: {reply}")
        print(f"Length: {len(reply)} chars")
        print(f"{'='*60}\n")

        return reply
    except Exception as e:
        print(f"Exception in generate_reply: {e}")
        return None

def generate_quote(tweet_text, tweet_metadata=None):
    """
    Generate quote tweet optimized for algorithm scoring
    Quote tweets are high-value engagement signals
    """
    # Build prompt for Gemini with persona and negative constraints
    prompt = f"""You are a witty and slightly edgy Twitter user. Write a quote tweet response that adds a sharp observation or funny spin to the original tweet.
    
    Rules for your human flair:
    - Keep it under 120 characters.
    - Sound like a real person quote-tweeting their timeline. Use internet slang naturally if it fits.
    - DO NOT be overly formal or helpful. Be opinionated. 
    - Return ONLY the plain response text. DO NOT use emojis, hashtags, or markdown.

    Tweet: '{tweet_text}'
    Response:"""

    try:
        contents = [types.Part.from_text(text=prompt)]
        if tweet_metadata:
            urls = tweet_metadata.get('media_urls', [])
            if urls:
                try:
                    img_resp = requests.get(urls[0], timeout=10)
                    img_resp.raise_for_status()
                    mime = img_resp.headers.get('Content-Type', 'image/jpeg')
                    contents.append(
                        types.Part.from_bytes(data=img_resp.content, mime_type=mime)
                    )
                except Exception as dl_err:
                    print(f"⚠️ Could not download media for quote prompt: {dl_err}")
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],
                temperature=0.95,  # increased randomness
                system_instruction="You are a highly opinionated, casual internet user. You hate sounding like a corporate AI."
            ),
        )
        quote = resp.text.strip()

        # Remove quotes if AI added them
        quote = quote.strip('"\'')

        # Remove any markdown formatting that slipped through
        quote = re.sub(r'\*([^*]+)\*', r'\1', quote)  # Remove *bold*
        quote = re.sub(r'_([^_]+)_', r'\1', quote)    # Remove _italic_
        quote = re.sub(r'`([^`]+)`', r'\1', quote)    # Remove `code`

        # Remove hashtags (replace with plain text)
        quote = re.sub(r'#(\w+)', r'\1', quote)

        # Remove emojis
        quote = re.sub(r'[^\x00-\x7F]+', '', quote)

        # Validate length
        if len(quote) > 280:
            quote = quote[:277] + "..."

        print(f"\n{'='*60}")
        print(f"Generated Quote: {quote}")
        print(f"Length: {len(quote)} chars")
        print(f"{'='*60}\n")

        return quote
    except Exception as e:
        print(f"Exception in generate_quote: {e}")
        return None

def reply_to_tweet(tweet_id, reply_text, user):
    """Reply to tweet - generates reply engagement signal (10x value in algorithm)"""
    client = tweepy.Client(
        bearer_token=bearer_token_write,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )
    try:
        client.create_tweet(text=reply_text, in_reply_to_tweet_id=tweet_id)
        mark_tweet_as_replied(tweet_id, user, 'reply')
        print(f"✓ Successfully replied to tweet {tweet_id}")
        print(f"  Reply: {reply_text}")
        return True
    except Exception as e:
        print(f"✗ Error replying to tweet: {e}")
        return False

def quote_tweet(tweet_id, quote_text, user):
    """Quote tweet - high-value engagement signal for algorithm"""
    client = tweepy.Client(
        bearer_token=bearer_token_write,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )
    try:
        client.create_tweet(text=quote_text, quote_tweet_id=tweet_id)
        mark_tweet_as_replied(tweet_id, user, 'quote')
        print(f"✓ Successfully quote tweeted {tweet_id}")
        print(f"  Quote: {quote_text}")
        return True
    except Exception as e:
        print(f"✗ Error quote tweeting: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("Twitter Bot - Algorithm-Optimized Version")
    print("="*60 + "\n")
    
    # Get bot username early
    bot_username = get_bot_username()
    if bot_username:
        print(f"Running as: @{bot_username}")
        # prune old history entries every run
        clean_old_history()
    print()
    
    # Show stats
    stats = get_reply_stats()
    print(f"📊 Bot Stats:")
    print(f"   Total interactions: {stats['total']}")
    print(f"   Today: {stats['today']}")
    if stats['by_action']:
        for action, count in stats['by_action'].items():
            print(f"   {action.capitalize()}s: {count}")
    print()

    game_engine = GameTheoryEngine(load_history, save_history, actions=("reply", "quote"))
    print("🎮 Game-theory regrets:")
    for action_name, value in game_engine.diagnostics().items():
        print(f"   {action_name}: {value}")
    print()
    
    baseline_payoffs = game_engine.baseline_payoffs()
    action, base_distribution = game_engine.select_action(baseline_payoffs)

    print(f"🎯 INITIAL ACTION ROLL: {action.upper()}")
    for action_name in game_engine.actions:
        payoff_val = baseline_payoffs.get(action_name, 0.0)
        weight_val = base_distribution.get(action_name, 0.0)
        print(f"   • {action_name:<12} base_payoff={payoff_val:>5.2f}  weight={weight_val:>5.2f}")
    print()

    print("Fetching home timeline...")
    tweets = fetch_home_timeline()
    print(f"✓ Fetched {len(tweets)} tweets\n")

    if not tweets:
        print("✗ No tweets fetched")
        game_engine.penalize_failure(action)
    else:
        selected_tweet = select_optimal_tweet(tweets)

        if not selected_tweet:
            print("No suitable tweet selected")
            game_engine.penalize_failure(action)
        else:
            print(f"{'='*60}")
            print(f"SELECTED TWEET")
            print(f"{'='*60}")
            print(f"User: @{selected_tweet['user']}")
            print(f"Text: {selected_tweet['text']}")
            print(f"Engagement: {selected_tweet['engagement']}")
            print(f"Has Media: {selected_tweet['has_media']}")
            print(f"Has Question: {selected_tweet['has_question']}")
            print(f"{'='*60}\n")

            payoffs = game_engine.estimate_payoffs(selected_tweet)
            distribution = game_engine.mixed_strategy(payoffs)

            print(f"📊 ACTION (game-theory mixed strategy): {action.upper()}")
            for action_name in game_engine.actions:
                payoff_val = payoffs.get(action_name, 0.0)
                weight_val = distribution.get(action_name, 0.0)
                marker = "<" if action_name == action else " "
                print(f"{marker}  {action_name:<11} payoff={payoff_val:>5.2f}  weight={weight_val:>5.2f}")
            print()

            success = False
            if action == 'reply':
                reply = generate_reply(selected_tweet['text'], selected_tweet)
                if reply:
                    success = reply_to_tweet(selected_tweet['id'], reply, selected_tweet['user'])
                else:
                    print("⚠️ Failed to generate reply - skipping")
            elif action == 'quote':
                quote = generate_quote(selected_tweet['text'], selected_tweet)
                if quote:
                    success = quote_tweet(selected_tweet['id'], quote, selected_tweet['user'])
                else:
                    print("⚠️ Failed to generate quote - skipping")

            if success:
                game_engine.update_regret(payoffs, action)
            else:
                print(f"⚠️ Action {action} failed - applying regret penalty")
                game_engine.penalize_failure(action)
    
    print("\n" + "="*60)
    print("Bot execution complete")
    print("="*60 + "\n")
