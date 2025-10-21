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
   python bot.py
   ```

3. For automated execution, set up GitHub Actions secrets and the workflow will run every 20 minutes.

## File Overview
- `bot.py` - Main bot script with timeline fetching, AI response generation, and posting logic
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
