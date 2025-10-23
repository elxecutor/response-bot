# Response Bot

[![Scheduled Bot Run](https://github.com/elxecutor/response-bot/actions/workflows/bot-schedule.yml/badge.svg)](https://github.com/elxecutor/response-bot/actions/workflows/bot-schedule.yml)

A smart Twitter bot that automatically engages with your timeline by generating contextual replies or quote tweets using Google's Gemini AI.

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [File Overview](#file-overview)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Features
- **Automated Timeline Monitoring**: Fetches tweets from your home timeline
- **AI-Powered Responses**: Uses Gemini 2.0 Flash to generate sharp, concise responses
- **Dual Engagement Modes**: Randomly chooses between replying or quote tweeting
- **Git-Based History Tracking**: Tracks replied tweets in `bot_history.json` (no database needed!)
- **Algorithm-Optimized**: Implements insights from Twitter's open-source recommendation algorithm
- **Rate Limit Safe**: Runs every 20 minutes, staying well under Twitter's 100 tweets per 15-minute limit
- **Scheduled Execution**: Automated via GitHub Actions

## Installation
Clone the repository and install dependencies:

```bash
git clone https://github.com/elxecutor/response-bot.git
cd response-bot
pip install -r requirements.txt
```

## Usage
1. Set up your environment variables in a `.env` file:
   ```env
   TWITTER_API_KEY=your_api_key
   TWITTER_API_SECRET=your_api_secret
   TWITTER_READ_BEARER_TOKEN=your_read_bearer_token
   TWITTER_READ_COOKIE=your_cookie
   TWITTER_READ_CSRF_TOKEN=your_csrf_token
   TWITTER_READ_USER_AGENT=your_user_agent
   TWITTER_API_URL=your_api_url
   TWITTER_CLIENT_ID=your_client_id
   TWITTER_CLIENT_SECRET=your_client_secret
   TWITTER_ACCESS_TOKEN=your_access_token
   TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
   TWITTER_WRITE_BEARER_TOKEN=your_write_bearer_token
   GEMINI_API_KEY=your_gemini_api_key
   ```

2. Run the bot locally:
   ```bash
   python bot_enhanced.py
   ```

3. For automated execution with GitHub Actions:
   - Set up repository secrets for all environment variables
   - The workflow will run every 20 minutes
   - After each run, the bot commits updated `bot_history.json` back to the repository
   - This ensures duplicate tweets are never replied to, even across multiple workflow runs

### How History Tracking Works
The bot uses a simple JSON file (`bot_history.json`) to track which tweets it has replied to. This file is:
- ✅ Committed to git (tracked in version control)
- ✅ Automatically updated after each run
- ✅ Shared across all workflow runs (no database needed!)
- ✅ Human-readable and easy to inspect

When running via GitHub Actions, make sure your workflow:
1. Checks out the repository
2. Runs the bot
3. Commits and pushes `bot_history.json` if it changed

## File Overview
- `bot_enhanced.py` - Main bot script with algorithm-optimized selection and AI response generation
- `bot.py` - Original bot script (legacy)
- `bot_history.json` - Tracks replied tweets (git-friendly, no database!)
- `requirements.txt` - Python dependencies
- `.github/workflows/bot-schedule.yml` - GitHub Actions workflow for automated execution
- `README.md` - Project documentation
- `LICENSE` - Project license
- `CONTRIBUTING.md` - Contribution guidelines
- `CODE_OF_CONDUCT.md` - Code of conduct

## Contributing
We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) for details.

## License
This project is licensed under the [MIT License](LICENSE).

## Contact
For questions or support, please open an issue or contact the maintainer via [X](https://x.com/elxecutor/).
