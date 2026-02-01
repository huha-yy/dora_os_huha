# Chatbot

A WebSocket-based chatbot server.

## Installation

```bash
# Create virtual environment with uv
uv venv

# Activate the environment
source .venv/bin/activate

# Install the package
uv pip install -e .

# Or install dependencies only
uv pip install -r requirements.txt
```

## Usage

```bash
# Run the chatbot server
chatbot --log-level INFO

# Or run directly
python main.py --log-level INFO
```

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .
```
