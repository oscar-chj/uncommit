# Uncommit

**AI-powered commit organizer** — group your messy changes into clean, logical commits.

## The Problem

When "vibe coding" with AI assistance, you accumulate many uncommitted changes that mix unrelated features, fixes, and refactors. Committing everything as one blob defeats version control best practices.

## The Solution

Uncommit uses an AI agent (Google ADK + Gemini) to:
1. **Analyze** your uncommitted changes
2. **Understand** the intent of each change
3. **Group** related changes into logical commit bundles
4. **Generate** conventional commit messages

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/uncommit.git
cd uncommit

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

## Setup

Set your Google API key:

```bash
export GOOGLE_API_KEY="your-api-key-here"
```

Or create a config file at `~/.config/uncommit/config.toml`:

```toml
[default]
model = "gemini-2.0-flash"
api_key = "your-api-key-here"
```

## Usage

### Analyze your changes

```bash
# See what files have uncommitted changes
uncommit analyze

# Output as JSON
uncommit analyze --json
```

### Get AI suggestions

```bash
# Let AI suggest how to group your changes
uncommit suggest

# Preview without caching (dry run)
uncommit suggest --dry-run

# Use a different model
uncommit suggest --model gemini-1.5-pro
```

### Commit the groups

```bash
# Commit a specific group by index
uncommit commit 1

# Commit all groups in order
uncommit commit --all

# Override the commit message
uncommit commit 1 --message "custom: my own message"
```

### Other commands

```bash
# Show cached suggestions without re-running AI
uncommit status

# Undo the last commit (keeps changes in working directory)
uncommit undo

# Undo and discard changes (dangerous!)
uncommit undo --hard

# Clear cached suggestions
uncommit clear

# Help
uncommit --help
```

## Example Session

```bash
$ uncommit suggest

🔍 Analyzing 5 changed files...

📦 Proposed Commits

  [1] feat: add user authentication
      └─ src/auth.py
      └─ src/login.py
      Reason: Both files implement the new authentication feature

  [2] fix: resolve null pointer in parser
      └─ src/parser.py
      Reason: Isolated bugfix in parser module

  [3] refactor: clean up unused imports
      └─ src/utils.py
      └─ src/helpers.py
      Reason: Related cleanup across utility modules

Use 'uncommit commit <index>' to commit a group, or 'uncommit commit --all' for all.

$ uncommit commit 1
✓ Committed: feat: add user authentication (abc1234)

$ uncommit commit 2
✓ Committed: fix: resolve null pointer in parser (def5678)
```

## Requirements

- Python 3.11+
- A Google API key with access to Gemini models
- A git repository with uncommitted changes

## License

MIT
