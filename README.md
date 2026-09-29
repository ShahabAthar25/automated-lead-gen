# Automated Lead Alert System

An intelligent, automated alert system that monitors job opportunities and alerts users when relevant openings are posted. Designed to bypass strict Reddit API limits by leveraging RSS feeds for real-time job market intelligence.

## Overview

This project solves the challenge of manual job search by automating the discovery and filtering of job postings from Reddit communities. Instead of relying on the restricted Reddit API, it uses RSS feeds to ingest job postings passively, applies a sophisticated multi-layered filtering strategy, and delivers targeted alerts to users.

## Key Features

- **RSS-Based Data Ingestion**: Bypasses Reddit API restrictions by using RSS feeds for reliable, continuous access to job postings
- **Multi-Layered Filtering Strategy**: Employs sophisticated filtering mechanisms to identify the most relevant job opportunities
- **Passive Post Ingestion Pipelines**: Automatically ingests and processes posts without manual intervention
- **Real-Time Alerts**: Notifies users immediately when matching job opportunities are detected
- **Customizable Filtering**: Configure filters based on job title, location, salary range, and other criteria

## Architecture

The system consists of several key components:

1. **RSS Feed Ingestion**: Continuously monitors RSS feeds from job-related subreddits
2. **Multi-Layer Filter Pipeline**: 
   - Initial keyword filtering
   - Advanced pattern matching
   - Relevance scoring
   - Duplicate detection
3. **Post Processing Engine**: Parses, cleans, and enriches job posting data
4. **Alert Dispatcher**: Sends notifications to users based on their preferences
5. **Data Storage**: Maintains a repository of processed jobs and user preferences

## Why RSS Over Reddit API?

The official Reddit API has strict rate limits that make it challenging for real-time monitoring. By leveraging RSS feeds, this project:
- Eliminates API call restrictions
- Provides reliable, continuous access to job postings
- Reduces infrastructure overhead
- Ensures consistent availability

## Use Cases

- **Job Seekers**: Automate job search across multiple communities simultaneously
- **Recruiters**: Monitor hiring trends and identify potential talent pools
- **Career Researchers**: Analyze job market data and trends over time
- **Passive Opportunity Discovery**: Stay informed without actively checking job boards

## Installation

```bash
# Clone the repository
git clone https://github.com/ShahabAthar25/automated-lead-gen.git
cd automated-lead-gen

# Install dependencies
pip install -r requirements.txt

# Configure your settings
cp config.example.py config.py
# Edit config.py with your preferences
```

## Configuration

Update `config.py` with:
- RSS feed URLs to monitor
- Filter criteria and keywords
- User alert preferences
- Notification settings

## Usage

```bash
# Run the automated alert system
python main.py

# Run with specific configuration
python main.py --config config.py
```

## Project Structure

```
automated-lead-gen/
├── README.md
├── requirements.txt
├── config.py              # Configuration settings
├── main.py               # Entry point
├── src/
│   ├── feed_ingestion/   # RSS feed processing
│   ├── filters/          # Multi-layer filtering logic
│   ├── processing/       # Post processing pipeline
│   ├── alerts/           # Alert dispatcher
│   └── storage/          # Data storage utilities
└── tests/                # Unit tests
```

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This project is intended for personal use and educational purposes. Users are responsible for complying with Reddit's Terms of Service and any applicable laws and regulations regarding web scraping and data usage.

---

**Status**: Active Development
