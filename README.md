# Automated Lead Gen

This is an automated Reddit lead alert system built around continuous background monitoring. It scans hundreds of subreddits for new posts and classifies them into three categories: **hiring**, **job seeking**, and **others**.

A post is labeled **Hiring** when the system detects that the author is looking to hire someone. **Job Seeking** is used when someone is looking for work. Everything else falls into **Others**. This makes the system useful for finding potential clients, studying the market, and collecting examples when writing self-introductions for hiring subreddits.

The system collects and stores all posts as I want to create a local dataset and fine tune more specific models like DeBERTa on them.

# Installation

```bash
# Clone the repository
git clone https://github.com/ShahabAthar25/automated-lead-gen.git
cd automated-lead-gen

# Install dependencies
poetry install

# Configure your settings
cp .env.template .env

# Fill in the .env and edit config.toml with your preferences
```

# Configurations

* Enable the RSS feed for your Reddit account, copy the feed URL, and set it in `.env`.
* Set up a Discord server and create a webhook in one of its channels. Copy the webhook URL into `.env`.
* Get a Gemini API key, Groq API key, or both and add them to `.env`. The model used by the system is selected through `config.toml`.
* If you only use the Groq model, the Gemini API key is optional.

# Notes

This project is about finding potential jobs and leads without constantly hitting Reddit's API and getting rate limited. It was built around my own workflow, so reliability matters more than raw speed.

The system follows three main principles:

* **Free** — No paid services are required to run the system.
* **Reliable** — Prefer collecting all potential leads instead of aggressively filtering down to only the "best" ones.
* **24/7** — Run continuously in the background with minimal resource usage.

## No Cost

The system is designed to run without a paid API subscription. If an LLM provider reaches its rate limit, the system can switch to another configured provider. Local models can also be used as providers.

A paid API key works as well, but the system does not depend on one.

## Reliable

The system follows a **"quantity over quality"** approach by default. Instead of trying to select only the best matches, it attempts to capture every potentially relevant hiring post and lets the classification layer determine how useful each one is.

The filtering strategy can be configured through `config.toml`. Local filtering removes obvious non-leads before an LLM is used, reducing unnecessary requests while keeping the pipeline broad.

## 24/7

The system is designed to sit in the background without constantly consuming CPU. During periods of low subreddit activity, the listener can sleep for several minutes before checking again.

Smart polling also adjusts the polling frequency based on subreddit activity and rate limits. Active subreddits are checked more frequently, while quiet ones are allowed to wait.

# Key Decisions

## RSS Over API

In mid-2023, Reddit introduced several API restrictions that made frequent API access considerably more difficult, even for legitimate applications. RSS feeds provided another way to monitor subreddit activity, although they contain less information than the API.

The tradeoff was clear: RSS made ingestion possible, but it was slower and still had to be polled carefully.

Rate limiting therefore became one of the main architectural constraints. Rather than constantly polling every feed at a fixed interval, the system uses adaptive polling and backs off when activity is low or limits become a concern.

## Slower and Smarter Than Faster

The goal was never to make the system query Reddit as frequently as possible. That would only create more requests and make the system less reliable.

Instead, the project uses smart polling, asynchronous ingestion, local filtering, provider fallbacks, and background workers to reduce unnecessary work.

A quiet subreddit might not need another request for several minutes. An active one does.

The system adapts to that difference.

## LLM Classification

Keyword matching alone is not enough to determine whether someone is actually hiring. A post might contain words like "developer" or "looking" without being a genuine lead.

The system therefore uses a multi-layered classification pipeline. Local rules and metadata filtering remove obvious non-leads first. Posts that remain can then be passed to an LLM for deeper classification.

The LLM layer is provider-based, so Gemini, Groq, and local models can be used without changing the rest of the pipeline.

## Discord as the Interface

I wanted the final workflow to require as little interaction as possible. Instead of building another dashboard that I would have to constantly check, the system sends qualified leads directly to Discord.

A new lead arrives as a notification. I open it and decide whether to act.

**One click. That's the idea.**

# Project Structure

```text
.
├── config.toml              # Configuration file
├── debug_post.py            # Debug a single post
├── main.py                  # Entry point
├── poetry.lock
├── pyproject.toml
├── README.md
├── scripts/                 # Useful debugging scripts
└── src/
    └── reddit_lead_gen/
        ├── adapters/        # Database, Discord, and Reddit clients
        ├── core/            # Classification, listener, and main pipelines
        ├── db/              # SQL models for leads
        ├── models/          # Pydantic models for posts and analysis
        ├── providers/       # LLM provider implementations
        └── settings.py      # Environment and configuration loading
```

# Contributions

Contributions are welcome. The project is actively updated as my workflow and operational requirements change, so improvements to reliability, new providers, and better filtering are always useful.

# License

Feel free to use any part of this project as your own. It is licensed under the MIT License.
