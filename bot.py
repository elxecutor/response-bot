import os
import requests
import random
import tweepy
from dotenv import load_dotenv

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

# Gemini API key
gemini_key = os.getenv('GEMINI_API_KEY')

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

def fetch_home_timeline():
    try:
        # Payload for HomeLatestTimeline POST request
        payload = {
            "variables": {
                "count": 20,
                "includePromotedContent": True,
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
        response.raise_for_status()  # Raise error for bad status codes
        data = response.json()
        
        tweets = []
        # Parse the GraphQL response
        instructions = data.get('data', {}).get('home', {}).get('home_timeline_urt', {}).get('instructions', [])
        for instruction in instructions:
            if instruction.get('type') == 'TimelineAddEntries':
                entries = instruction.get('entries', [])
                for entry in entries:
                    tweet = entry.get('content', {}).get('itemContent', {}).get('tweet_results', {}).get('result', {})
                    if tweet and tweet.get('__typename') == 'Tweet':
                        tweet_id = tweet.get('rest_id')
                        full_text = tweet.get('legacy', {}).get('full_text')
                        user = tweet.get('core', {}).get('user_results', {}).get('result', {}).get('core', {}).get('screen_name')
                        if tweet_id and full_text and user:
                            tweets.append({
                                'id': tweet_id,
                                'text': full_text,
                                'user': user
                            })
        
        return tweets
    except requests.RequestException as e:
        print(f"Error fetching timeline: {e}")
        return []

def generate_reply(tweet_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
    prompt = f"Respond to the tweet with a single, sharp sentence that cuts straight to the point. No prefaces like ‘agree’ or ‘disagree’—just the insight or jab itself. Be concise, direct, and, if it fits, clever. '{tweet_text}'. Keep it under 280 characters."
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    response = requests.post(url, json=data)
    if response.status_code == 200:
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text'].strip()
    else:
        print(f"Error generating reply: {response.status_code} {response.text}")
        return "Sorry, couldn't generate a reply."

def generate_quote(tweet_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
    prompt = f"Quote the tweet with a single, sharp sentence that delivers the insight or jab. No prefaces, no fluff—just one clean, cutting line. '{tweet_text}'. Keep it under 280 characters."
    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }
    response = requests.post(url, json=data)
    if response.status_code == 200:
        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text'].strip()
    else:
        print(f"Error generating quote: {response.status_code} {response.text}")
        return "Interesting take! 🤔"

def reply_to_tweet(tweet_id, reply_text):
    # Initialize Tweepy client
    client = tweepy.Client(
        bearer_token=bearer_token_write,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )
    client.create_tweet(text=reply_text, in_reply_to_tweet_id=tweet_id)
    print(f"Replied to tweet {tweet_id} with: {reply_text}")

def quote_tweet(tweet_id, quote_text):
    # Initialize Tweepy client
    client = tweepy.Client(
        bearer_token=bearer_token_write,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
        wait_on_rate_limit=True
    )
    # Use the proper quote_tweet_id parameter
    response = client.create_tweet(text=quote_text, quote_tweet_id=tweet_id)
    print(f"Quote tweeted {tweet_id} with: {quote_text}")
    return response

if __name__ == "__main__":
    tweets = fetch_home_timeline()
    if tweets:
        # Pick a random tweet
        random_tweet = random.choice(tweets)
        print(f"Selected tweet: {random_tweet['text']} by @{random_tweet['user']}")
        
        # Randomly choose between replying or quoting
        action = random.choice(['reply', 'quote'])
        print(f"\nAction: {action.upper()}")
        
        if action == 'reply':
            # Generate reply using Gemini
            reply = generate_reply(random_tweet['text'])
            print(f"Generated reply: {reply}")
            
            # Reply to the tweet
            reply_to_tweet(random_tweet['id'], reply)
        else:  # action == 'quote'
            # Generate quote tweet using Gemini
            quote = generate_quote(random_tweet['text'])
            print(f"Generated quote: {quote}")
            
            # Quote tweet
            quote_tweet(random_tweet['id'], quote)
    else:
        print("No tweets fetched.")