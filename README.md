# Twitter Bot using Ollama

A Python bot that connects to Twitter API v2, tracks specific tweets, and automatically generates and posts intelligent replies using local Ollama models.

## ✨ Features

- **Twitter API v2 Integration**: Uses official `tweepy` library for reliable Twitter access
- **Local AI Processing**: Powered by Ollama running locally (`mistral:latest` recommended)
- **Smart Tweet Selection**: Multiple strategies (random, engagement-based, selective)
- **Rate Limit Compliance**: Built-in Twitter API rate limiting to avoid restrictions
- **Duplicate Prevention**: Automatic tracking of replied tweets to prevent double-replies
- **Configurable Tracking**: Track keywords, hashtags, or specific users
- **Response Filtering**: Content filters and engagement thresholds
- **Comprehensive Logging**: Full audit trail of all bot activities

## 🚀 Quick Setup

### 1. Prerequisites

- Python 3.8+
- [Ollama](https://ollama.ai) installed and running locally
- Twitter Developer Account with API v2 access

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Twitter API Setup

1. Go to [Twitter Developer Portal](https://developer.twitter.com/)
2. Create a new app and get your credentials:
   - API Key
   - API Secret Key
   - Access Token
   - Access Token Secret
   - Bearer Token

### 4. Configure the Bot

Copy the example configuration:
```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your Twitter API credentials:

```yaml
source:
  type: twitter
  # Twitter API v2 credentials
  api_key: "your_twitter_api_key_here"
  api_secret: "your_twitter_api_secret_here"
  access_token: "your_access_token_here"
  access_token_secret: "your_access_token_secret_here"
  bearer_token: "your_bearer_token_here"
  
  # What to track
  track_keywords:
    - "AI"
    - "machine learning"
    - "python"
  track_users:
    - "elonmusk"
    - "OpenAI"
  track_hashtags:
    - "#AI"
    - "#MachineLearning"
  
  # How to select tweets
  selection_strategy: "engagement_based"  # random, selective, engagement_based
  max_tweets_per_fetch: 20
```

### 5. Setup Ollama

Make sure Ollama is running with the mistral model:
```bash
ollama run mistral:latest
```

### 6. Run the Bot

Test components first:
```bash
python3 cli.py test
```

Run one cycle manually:
```bash
python3 cli.py run-once
```

Start the bot continuously:
```bash
python3 cli.py start
```

## 📋 Configuration Options

### Tweet Tracking

- **track_keywords**: Keywords to search for in tweets
- **track_users**: Specific Twitter usernames to monitor
- **track_hashtags**: Hashtags to track
- **selection_strategy**: How to choose tweets to reply to:
  - `random`: Randomly select tweets
  - `engagement_based`: Prioritize high-engagement tweets
  - `selective`: Custom scoring based on user verification, recency, engagement

### Response Behavior

```yaml
reply:
  mode: "log"  # Options: "log", "post", "both"
  reply_probability: 0.3  # 30% chance to reply to eligible tweets
  max_replies_per_hour: 10  # Rate limiting
  delay_range: [60, 300]  # Random delay before posting (seconds)
```

### Content Filtering

```yaml
filter:
  min_engagement: 5  # Minimum likes + retweets + replies
  keywords_exclude: ["spam", "bot", "fake"]  # Skip tweets with these words
  max_age_hours: 24  # Only reply to tweets less than 24 hours old
```

### LLM Configuration

```yaml
llm:
  model: "mistral:latest"  # Ollama model to use
  temperature: 0.7  # Response creativity (0.0-1.0)
  max_tokens: 150  # Maximum response length
  system_prompt: "You are a helpful AI assistant that generates engaging social media responses."
```

## 🛠️ CLI Commands

```bash
# Test all components
python3 cli.py test

# Show current status
python3 cli.py status

# Run one processing cycle
python3 cli.py run-once

# Start continuous operation
python3 cli.py start

# Show configuration
python3 cli.py config --show

# Create default config
python3 cli.py config --create-default
```

## 🔒 Environment Variables

For security, you can set credentials via environment variables:

```bash
# Create .env file
cp .env.example .env

# Edit .env with your credentials

# REQUIRED: Write credentials (for posting tweets)
TWITTER_API_KEY=your_twitter_api_key_here
TWITTER_API_SECRET=your_twitter_api_secret_here
TWITTER_ACCESS_TOKEN=your_access_token_here
TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret_here
TWITTER_WRITE_BEARER_TOKEN=your_write_bearer_token_here

# OPTIONAL: Read credentials (for better rate limiting)
TWITTER_READ_BEARER_TOKEN=your_read_bearer_token_here
TWITTER_READ_COOKIE=your_cookie_here
TWITTER_READ_CSRF_TOKEN=your_csrf_token_here
TWITTER_READ_USER_AGENT=your_user_agent_here
TWITTER_READ_API_URL=your_api_url_here
```

> **Note**: If you have separate bearer tokens for reading and writing (to prevent conflicts), use the read credentials. Otherwise, the bot will use write credentials for both operations.

## 📊 Monitoring

### Real-time Status
```bash
python3 cli.py status
```

### View Recent Activity
```bash
python3 cli.py status --json | jq '.reply_engine'
```

### Log Files
- `bot.log`: Application logs
- `response_dump.json`: Fetched tweets data
- `replied_tweets.json`: Track of replied tweets
- `responses.log`: All generated responses

## 🔄 How It Works

1. **Fetch Tweets**: Bot searches Twitter for tweets matching your keywords/users
2. **Filter Content**: Applies engagement thresholds and content filters
3. **Select Tweets**: Uses your chosen strategy to pick tweets to reply to
4. **Generate Responses**: Sends tweet context to Ollama for AI-generated replies
5. **Post Replies**: Posts responses via Twitter API (respecting rate limits)
6. **Track Activity**: Logs all actions and prevents duplicate replies

## ⚠️ Safety Features

- **Rate Limiting**: Respects Twitter API limits (configurable buffer)
- **Duplicate Prevention**: Tracks replied tweets to avoid spam
- **Content Filtering**: Excludes inappropriate content
- **Engagement Thresholds**: Only replies to tweets with minimum engagement
- **Random Delays**: Adds human-like delays between responses
- **Dry Run Mode**: Test with `mode: "log"` before enabling posting

## 🎯 Tweet Selection Strategies

### Random
Randomly selects from eligible tweets.

### Engagement-Based
Prioritizes tweets with high engagement (likes + retweets + replies + quotes).

### Selective
Custom scoring considering:
- Verified users (higher priority)
- Tweet recency (newer = better)
- Engagement metrics
- User influence

## 🐛 Troubleshooting

### Common Issues

1. **Twitter API Errors**
   - Check your credentials in `config.yaml`
   - Verify API access levels in Twitter Developer Portal
   - Ensure rate limits aren't exceeded

2. **Ollama Connection Failed**
   - Make sure Ollama is running: `ollama serve`
   - Check if model is available: `ollama list`
   - Pull model if needed: `ollama pull mistral:latest`

3. **No Tweets Found**
   - Check your tracking keywords/users
   - Verify tweets meet engagement thresholds
   - Check if tweets are too old (max_age_hours)

### Debug Mode
```bash
python3 cli.py --log-level DEBUG test
```

## 📝 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## ⚡ Performance Tips

- Use specific keywords to reduce API calls
- Set appropriate engagement thresholds
- Monitor rate limits in logs
- Use `selection_strategy: "engagement_based"` for quality
- Start with `mode: "log"` to test before posting

---

**Happy Tweeting! 🐦🤖**
