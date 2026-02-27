# MGR4SMB Conversation Agent

Multi-agent email conversation system for SMB management.

## Overview

This project provides an intelligent email conversation system powered by Google Gemini AI, designed to handle customer communications for small to medium businesses.

## Features

- Gmail API integration for email management
- Google Gemini AI for intelligent response generation
- MongoDB Atlas for data persistence
- Async email processing with motor
- Email parsing and HTML to text conversion
- RESTful API with authentication and rate limiting

## Requirements

- Python >= 3.11
- MongoDB Atlas account
- Google Cloud Platform account (for Gmail API and Gemini AI)

## Installation

1. Clone the repository
2. Copy `.env.example` to `.env.local` and configure your credentials
3. Install dependencies:
   ```bash
   uv sync
   ```

## Configuration

See `.env.example` for required environment variables:
- MongoDB connection settings
- Google API credentials
- Gemini AI API key
- Gmail API credentials

## Development

Install development dependencies:
```bash
uv sync --group dev
```

Run tests:
```bash
pytest
```

Format code:
```bash
black src/
ruff check src/
```

## License

Proprietary - All rights reserved
