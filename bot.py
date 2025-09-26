import os
import requests
import random
import tweepy
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Fetch credentials from .env
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
    'Referer': 'https://x.com/',
}

def fetch_home_timeline():
    try:
        response = requests.get(api_url, headers=headers)
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
                    if tweet:
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
    prompt = f"Generate a witty and engaging reply to this tweet: '{tweet_text}'. Keep it under 280 characters."
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

def reply_to_tweet(tweet_id, reply_text):
    # Initialize Tweepy client
    client = tweepy.Client(
        bearer_token=bearer_token_write,
        consumer_key=client_id,
        consumer_secret=client_secret,
        access_token=access_token,
        access_token_secret=access_token_secret
    )
    try:
        client.create_tweet(text=reply_text, in_reply_to_tweet_id=tweet_id)
        print(f"Replied to tweet {tweet_id} with: {reply_text}")
    except tweepy.TweepyException as e:
        print(f"Error replying to tweet: {e}")

if __name__ == "__main__":
    tweets = fetch_home_timeline()
    if tweets:
        # Pick a random tweet
        random_tweet = random.choice(tweets)
        print(f"Selected tweet: {random_tweet['text']} by @{random_tweet['user']}")
        
        # Generate reply using Gemini
        reply = "really?" #generate_reply(random_tweet['text'])
        print(f"Generated reply: {reply}")
        
        # Reply to the tweet
        reply_to_tweet(random_tweet['id'], reply)
    else:
        print("No tweets fetched.")