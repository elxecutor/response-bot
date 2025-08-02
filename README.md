# AI Response Bot

A modular AI bot that automatically generates and posts responses to social media content using local LLM models via Ollama.

## 🏗️ Architecture

The bot consists of several modular components:

- **Input Handler**: Retrieves data from sources (Twitter/X)
- **Context Pre-processor**: Cleans and filters post data
- **Ollama LLM Integration**: Generates responses using local LLM models
- **Reply Engine**: Manages response posting and logging
- **Scheduler**: Handles periodic execution of tasks
- **CLI**: Command-line interface for bot management

## 📁 File Structure

```
response-bot/
├── src/
│   ├── __init__.py
│   ├── bot_core.py          # Main bot orchestration
│   ├── config.py            # Configuration management
│   ├── input_handler.py     # Data source handling
│   ├── preprocessor.py      # Content filtering and processing
│   ├── llm_engine.py        # Ollama LLM integration
│   ├── reply_engine.py      # Response posting and logging
│   └── scheduler.py         # Task scheduling
├── cli.py                   # Command-line interface
├── config.example.yaml      # Example configuration
├── .env.example            # Example environment variables
├── requirements.txt         # Python dependencies
├── twitter_scraper.py      # Original Twitter scraper
└── README.md               # This file
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.8+
- [Ollama](https://ollama.ai/) installed and running
- Ollama Python library (included in requirements.txt)
- Access to Twitter/X API or data source

### 2. Installation

```bash
# Clone or navigate to the project directory
cd response-bot

# Install dependencies (includes official Ollama Python library)
pip install -r requirements.txt

# Copy configuration files
cp config.example.yaml config.yaml
cp .env.example .env
```

### 3. Setup Configuration

#### Environment Variables (.env)
```bash
# Edit .env with your actual credentials
TWITTER_API_URL=your_twitter_api_url
TWITTER_BEARER_TOKEN=your_bearer_token
TWITTER_COOKIE=your_cookie_string
TWITTER_USER_AGENT=your_user_agent
TWITTER_CSRF_TOKEN=your_csrf_token
```

#### Configuration File (config.yaml)
Edit `config.yaml` to customize:
- LLM model selection
- Response filters
- Posting frequency
- Rate limits

### 4. Setup Ollama

```bash
# Install Ollama (if not already installed)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model (choose one)
ollama pull llama2        # Meta Llama 2
ollama pull mistral       # Mistral 7B
ollama pull phi           # Microsoft Phi

# Verify Ollama is running
curl http://localhost:11434/api/tags
```

### 5. Run the Bot

```bash
# Test components
python cli.py test

# Create default config (if needed)
python cli.py config --create-default

# Run one cycle manually
python cli.py run-once

# Start the bot (runs continuously)
python cli.py start

# Check status
python cli.py status
```

## 🔧 Configuration Options

### Source Configuration
```yaml
source:
  type: "twitter"                # Source type
  fetch_interval: 300           # Fetch frequency (seconds)
  # API credentials from environment variables
```

### LLM Configuration
```yaml
llm:
  base_url: "http://localhost:11434"
  model: "llama2"               # Available: llama2, mistral, phi, etc.
  temperature: 0.7              # Response randomness (0.0-1.0)
  max_tokens: 150               # Maximum response length
  system_prompt: "Custom prompt..."
```

### Content Filtering
```yaml
filter:
  min_engagement: 5             # Minimum engagement threshold
  keywords_include: []          # Required keywords (empty = all)
  keywords_exclude: ["spam"]    # Blocked keywords
  language: "en"                # Language filter
  max_age_hours: 24            # Maximum post age
```

### Reply Settings
```yaml
reply:
  mode: "log"                   # Options: "log", "post", "both"
  randomize: true               # Apply randomization
  reply_probability: 0.3        # Response probability (0.0-1.0)
  delay_range: [60, 300]       # Random delay before posting
  max_replies_per_hour: 10     # Rate limiting
```

### Scheduler Settings
```yaml
scheduler:
  enabled: true                 # Enable scheduling
  fetch_interval: 300          # Data fetch frequency
  process_interval: 600        # Processing frequency
  cleanup_interval: 3600       # Cleanup frequency
```

## 📖 CLI Commands

### Basic Commands
```bash
# Start the bot (continuous operation)
python cli.py start

# Run one processing cycle
python cli.py run-once

# Show current status
python cli.py status

# Test all components
python cli.py test
```

### Configuration Management
```bash
# Show current configuration
python cli.py config --show

# Create default configuration
python cli.py config --create-default

# Use custom config file
python cli.py --config custom.yaml start
```

### Logging and Debugging
```bash
# Enable verbose output
python cli.py --verbose start

# Set log level
python cli.py --log-level DEBUG start

# JSON status output
python cli.py status --json
```

## 🔌 Ollama Integration

### Supported Models

The bot supports any model available in Ollama:

- **llama2**: Meta's Llama 2 (7B, 13B, 70B)
- **mistral**: Mistral 7B
- **phi**: Microsoft Phi-2
- **codellama**: Code-focused Llama
- **orca-mini**: Smaller, faster model
- **neural-chat**: Conversational model

### Model Management
```bash
# List available models
ollama list

# Pull a new model
ollama pull mistral

# Remove a model
ollama rm model_name

# Update configuration to use different model
# Edit config.yaml -> llm.model: "mistral"
```

### Performance Tuning
```yaml
llm:
  temperature: 0.7      # Higher = more creative, Lower = more focused
  max_tokens: 150       # Longer responses = more processing time
  system_prompt: "..."  # Customize behavior
```

## 📊 Monitoring and Logs

### Log Files
- `bot.log`: General application logs
- `responses.jsonl`: Detailed response logs (JSON Lines format)

### Status Monitoring
```bash
# Real-time status
python cli.py status

# JSON format for scripts
python cli.py status --json
```

### Response Analytics
The bot logs detailed information about each response:
- Original post content
- Generated response
- Engagement metrics
- Processing timestamps
- Success/failure status

## 🛡️ Safety Features

### Content Filtering
- Keyword-based filtering (include/exclude lists)
- Engagement threshold filtering
- Language filtering
- Age-based filtering
- Sensitive content detection

### Rate Limiting
- Configurable responses per hour
- Random delays between responses
- Automatic backoff on errors

### Quality Controls
- Response length validation
- Repetition detection
- Inappropriate content filtering
- Blacklisted word filtering

## 🔧 Customization

### Adding New Data Sources
1. Create a new class inheriting from `DataSource` in `input_handler.py`
2. Implement the `fetch_data()` method
3. Update the source factory in `InputHandler`

### Custom Response Filters
1. Extend the `ResponseFilter` class in `reply_engine.py`
2. Add custom filtering logic
3. Update configuration schema if needed

### Custom LLM Prompts
1. Modify `PromptBuilder` in `llm_engine.py`
2. Create specialized prompts for different post types
3. Add prompt templates to configuration

## 🐛 Troubleshooting

### Common Issues

**Ollama Connection Failed**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama if not running
ollama serve
```

**Model Not Found**
```bash
# List available models
ollama list

# Pull the required model
ollama pull llama2
```

**No Posts Fetched**
- Check Twitter API credentials in `.env`
- Verify API URL is correct
- Check network connectivity

**No Responses Generated**
- Verify Ollama is running and accessible
- Check if posts pass filtering criteria
- Review LLM configuration

### Debug Mode
```bash
# Enable debug logging
python cli.py --log-level DEBUG start

# Run single cycle with verbose output
python cli.py --verbose run-once
```

## 📈 Performance Optimization

### For High Volume
- Increase `max_replies_per_hour` limit
- Reduce `process_interval` for faster cycles
- Use smaller, faster LLM models (e.g., `phi`)

### For Quality
- Use larger models (e.g., `llama2:13b`)
- Increase `min_engagement` threshold
- Customize `system_prompt` for better responses

### For Resource Efficiency
- Use `orca-mini` or similar compact models
- Increase processing intervals
- Reduce `max_tokens` for shorter responses

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is provided as-is for educational and research purposes. Please ensure compliance with the terms of service of any APIs or services you use.

## ⚠️ Disclaimer

- This bot is for educational purposes
- Ensure compliance with platform terms of service
- Use responsibly and ethically
- Monitor bot behavior and responses
- Consider rate limiting and API costs
