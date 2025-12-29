# Uncommit

[![Tests](https://github.com/oscar-chj/uncommit/actions/workflows/tests.yml/badge.svg)](https://github.com/oscar-chj/uncommit/actions/workflows/tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AI-powered commit organizer** — group your messy changes into clean, logical commits.

## The Problem

When "vibe coding" with AI assistance, you accumulate many uncommitted changes that mix unrelated features, fixes, and refactors. Committing everything as one blob defeats version control best practices.

## The Solution

Uncommit uses Gemini to:
1. **Analyze** your uncommitted changes
2. **Understand** the intent of each change
3. **Group** related changes into logical commit bundles
4. **Generate** conventional commit messages

## Installation

```bash
# Clone the repository
git clone https://github.com/oscar-chj/uncommit.git
cd uncommit

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

## Setup

Get a Google API key from [AI Studio](https://aistudio.google.com/apikey) and set it:

```bash
export GOOGLE_API_KEY="your-api-key-here"
```

Or create `.env.local` in your project:

```
GOOGLE_API_KEY=your-api-key-here
```

## Usage

### Analyze your changes

```bash
uncommit analyze          # List uncommitted files
uncommit analyze --json   # Output as JSON
```

### Get AI suggestions

```bash
uncommit suggest              # Group changes into commits
uncommit suggest --dry-run    # Preview without caching
uncommit suggest --model gemini-1.5-pro  # Use different model
```

### Commit the groups

```bash
uncommit commit 1             # Commit group #1
uncommit commit --all         # Commit all groups
uncommit commit 1 -m "custom" # Override message
```

### Other commands

```bash
uncommit status       # Show cached suggestions
uncommit undo         # Undo last commit (keep changes)
uncommit undo --soft  # Undo, keep changes staged
uncommit undo --hard  # Undo and discard (dangerous!)
uncommit clear        # Clear cached suggestions
```

## Example Session

```bash
$ uncommit suggest

⠋ Analyzing 5 changed files...

📦 Proposed Commits

  [1] feat: add user authentication
      └─ src/auth.py
      └─ src/login.py
      Reason: Both files implement the new authentication feature

  [2] fix: resolve null pointer in parser
      └─ src/parser.py
      Reason: Isolated bugfix in parser module

$ uncommit commit 1
✓ Committed: feat: add user authentication (abc1234)

$ uncommit commit 2
✓ Committed: fix: resolve null pointer in parser (def5678)
```

## Development

```bash
# Install with dev dependencies
uv sync --dev

# Run tests
uv run pytest

# Or activate venv and run directly
source .venv/Scripts/activate  # Windows
pytest
```

## Requirements

- Python 3.11+
- Google API key ([get one here](https://aistudio.google.com/apikey))
- A git repository with uncommitted changes

## License

MIT
