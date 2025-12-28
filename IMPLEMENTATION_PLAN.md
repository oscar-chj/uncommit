# Uncommit: AI-Powered Commit Organizer

A CLI tool that uses Google ADK with Gemini to analyze uncommitted git changes and group them into logical, clean commits.

## Problem

When "vibe coding" with AI assistance, developers accumulate many uncommitted changes that mix unrelated features, fixes, and refactors. Committing everything as one blob defeats version control best practices.

## Solution

An **agentic CLI tool** that:
1. Scans uncommitted changes in a git repository
2. Uses an AI agent to understand the *intent* of each change
3. Groups related changes into proposed commit bundles
4. Lets the user commit them one-by-one with auto-generated messages

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         uncommit CLI                            │
├─────────────────────────────────────────────────────────────────┤
│  Commands:                                                      │
│    analyze     - Parse git diff, output structured JSON         │
│    suggest     - Run AI agent to propose commit groups          │
│    commit      - Stage & commit a specific group                │
│    interactive - TUI for reviewing/editing groups (stretch)     │
├─────────────────────────────────────────────────────────────────┤
│  Flags:                                                         │
│    --json      - Machine-readable output (for GUIs)             │
│    --dry-run   - Preview without committing                     │
│    --model     - Override default model                         │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Categorization Agent (ADK)                  │
├─────────────────────────────────────────────────────────────────┤
│  Model: gemini-2.0-flash (default, configurable)                │
│                                                                 │
│  Tools available to the agent:                                  │
│    • get_file_diff(path) - Get diff for a specific file         │
│    • get_file_content(path) - Read full file for context        │
│    • get_git_log(n) - Recent commit history for style matching  │
│    • get_directory_structure() - Understand project layout       │
├─────────────────────────────────────────────────────────────────┤
│  Agent Instruction:                                             │
│    Analyze the provided changes and group them into logical     │
│    commits. Consider:                                           │
│    - Semantic relationship (same feature/bugfix)                │
│    - Conventional commit types (feat, fix, refactor, docs, etc) │
│    - Minimize dependencies between groups                       │
│    - Generate concise, descriptive commit messages               │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Git Layer (GitPython)                     │
├─────────────────────────────────────────────────────────────────┤
│  • Parse git status and diffs                                   │
│  • Stage specific files/hunks                                   │
│  • Create commits with messages                                 │
│  • Handle edge cases (binary files, renames, etc.)              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
uncommit/
├── pyproject.toml           # Package config, dependencies, CLI entry point
├── README.md                # Usage documentation
├── .env.example             # Example environment variables
├── src/
│   └── uncommit/
│       ├── __init__.py      # Package init, version
│       ├── cli.py           # Typer CLI commands
│       ├── git_ops.py       # Git operations layer
│       ├── agent.py         # ADK agent definition + tools
│       ├── models.py        # Pydantic models for data structures
│       └── config.py        # Configuration management
└── tests/
    ├── __init__.py
    ├── test_git_ops.py
    └── test_agent.py
```

> [!NOTE]
> The agent and tools are co-located in `agent.py` for simplicity. ADK tools are just Python functions with docstrings.

---

## Core Components

### 1. Git Operations (`git_ops.py`)

Handles all git interactions using GitPython.

```python
from git import Repo
from uncommit.models import FileChange, CommitInfo

def get_repo(path: str = ".") -> Repo:
    """Get the git repo at the given path."""

def get_uncommitted_files(repo: Repo) -> list[FileChange]:
    """Get list of all uncommitted file changes (staged + unstaged)."""

def get_diff(repo: Repo, file_path: str | None = None) -> str:
    """Get diff for a specific file or all files."""

def get_file_content(repo: Repo, file_path: str) -> str:
    """Read the current content of a file."""

def get_recent_commits(repo: Repo, n: int = 10) -> list[CommitInfo]:
    """Get recent commit history for style matching."""

def stage_files(repo: Repo, file_paths: list[str]) -> None:
    """Stage specific files for commit."""

def create_commit(repo: Repo, message: str) -> str:
    """Create a commit with the given message. Returns commit hash."""
```

### 2. Data Models (`models.py`)

Pydantic models for type safety and validation.

```python
from pydantic import BaseModel

class FileChange(BaseModel):
    path: str
    status: str  # "added", "modified", "deleted", "renamed"
    diff: str | None = None

class CommitInfo(BaseModel):
    hash: str
    message: str
    author: str
    date: str

class CommitGroup(BaseModel):
    index: int
    message: str
    type: str  # feat, fix, refactor, docs, chore, style, test
    files: list[str]
    reasoning: str  # Why these files are grouped together

class SuggestionResult(BaseModel):
    groups: list[CommitGroup]
    warnings: list[str] | None = None
```

### 3. Agent (`agent.py`)

ADK agent with tools for analyzing git changes.

```python
from google.adk.agents import Agent
from uncommit.git_ops import get_repo, get_diff, get_file_content, get_recent_commits

# Tools are plain Python functions with Google-style docstrings
def get_file_diff(file_path: str) -> dict:
    """Get the git diff for a specific file.
    
    Args:
        file_path: Path to the file relative to repo root.
    
    Returns:
        dict: {"status": "success", "diff": "..."} or {"status": "error", "error_message": "..."}
    """
    try:
        repo = get_repo()
        diff = get_diff(repo, file_path)
        return {"status": "success", "diff": diff}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def get_file_contents(file_path: str) -> dict:
    """Read the full content of a file for additional context.
    
    Args:
        file_path: Path to the file relative to repo root.
    
    Returns:
        dict: {"status": "success", "content": "..."} or {"status": "error", "error_message": "..."}
    """
    try:
        repo = get_repo()
        content = get_file_content(repo, file_path)
        return {"status": "success", "content": content}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def get_git_history(count: int = 10) -> dict:
    """Get recent commit history to understand the project's commit style.
    
    Args:
        count: Number of recent commits to retrieve.
    
    Returns:
        dict: {"status": "success", "commits": [...]} or {"status": "error", "error_message": "..."}
    """
    try:
        repo = get_repo()
        commits = get_recent_commits(repo, count)
        return {"status": "success", "commits": [c.model_dump() for c in commits]}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}

def get_directory_structure() -> dict:
    """Get the project's directory structure for context.
    
    Returns:
        dict: {"status": "success", "structure": "..."} or {"status": "error", "error_message": "..."}
    """
    # Implementation: walk directories, return tree representation
    pass

# The root agent (required export for ADK)
root_agent = Agent(
    name="commit_categorizer",
    model="gemini-2.0-flash",
    description="Analyzes git changes and groups them into logical commits",
    instruction="""You are an expert at organizing code changes into clean git commits.

Your task:
1. First, call get_file_diff for each changed file to understand the changes
2. Optionally call get_git_history to understand the project's commit style
3. Group related changes into logical commit bundles
4. Generate conventional commit messages (feat:, fix:, refactor:, docs:, chore:, etc.)

Guidelines:
- Each group should represent a single logical change
- Minimize dependencies between groups (earlier commits shouldn't depend on later ones)
- Match the project's existing commit style if visible in history
- Be concise but descriptive in commit messages

Return your analysis as a JSON object with this structure:
{
    "groups": [
        {
            "index": 1,
            "message": "feat: add user authentication",
            "type": "feat",
            "files": ["src/auth.py", "src/login.py"],
            "reasoning": "These files implement the new auth feature together"
        }
    ],
    "warnings": ["Optional warnings about potential issues"]
}
""",
    tools=[get_file_diff, get_file_contents, get_git_history, get_directory_structure],
)
```

### 4. CLI (`cli.py`)

Typer-based CLI with Rich for pretty output.

```python
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="AI-powered commit organizer")
console = Console()

@app.command()
def analyze(json_output: bool = typer.Option(False, "--json", help="Output as JSON")):
    """Analyze uncommitted changes and list them."""
    pass

@app.command()
def suggest(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without committing"),
    model: str = typer.Option(None, "--model", help="Override default model"),
):
    """Use AI to suggest commit groups for your changes."""
    pass

@app.command()
def commit(
    group_index: int = typer.Argument(..., help="Index of the group to commit"),
    all_groups: bool = typer.Option(False, "--all", help="Commit all groups sequentially"),
):
    """Commit a specific group or all groups."""
    pass

if __name__ == "__main__":
    app()
```

### 5. Configuration (`config.py`)

Configuration with priority: CLI flags > env vars > config file > defaults.

```python
import os
from pathlib import Path
from pydantic import BaseModel
import tomllib

class Config(BaseModel):
    model: str = "gemini-2.0-flash"
    api_key: str | None = None

def load_config() -> Config:
    """Load configuration from env vars and config file."""
    config_path = Path.home() / ".config" / "uncommit" / "config.toml"
    
    config_data = {}
    if config_path.exists():
        with open(config_path, "rb") as f:
            config_data = tomllib.load(f).get("default", {})
    
    # Env vars override config file
    if api_key := os.getenv("GOOGLE_API_KEY"):
        config_data["api_key"] = api_key
    if model := os.getenv("UNCOMMIT_MODEL"):
        config_data["model"] = model
    
    return Config(**config_data)
```

---

## Dependencies

```toml
[project]
name = "uncommit"
version = "0.1.0"
description = "AI-powered commit organizer using Google ADK"
requires-python = ">=3.11"
dependencies = [
    "google-adk>=1.0.0",
    "gitpython>=3.1.0",
    "typer>=0.9.0",
    "pydantic>=2.0.0",
    "rich>=13.0.0",
]

[project.scripts]
uncommit = "uncommit.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## Environment Setup

```bash
# .env.example
GOOGLE_API_KEY=your-api-key-here
UNCOMMIT_MODEL=gemini-2.0-flash  # optional, this is the default
```

---

## Usage

```bash
# Install the package
pip install -e .

# Set up your API key
export GOOGLE_API_KEY="your-api-key"

# Analyze your changes (shows what files are modified)
uncommit analyze

# Get AI suggestions for grouping commits
uncommit suggest

# Preview without actually committing
uncommit suggest --dry-run

# Commit a specific group
uncommit commit 1

# Commit all groups in order
uncommit commit --all
```

### Example Session

```bash
$ uncommit suggest

🔍 Analyzing 5 changed files...

📦 Proposed Commits:

  [1] feat: Add user authentication
      └─ src/auth.ts (+45, -12)
      └─ src/api/login.ts (+30, -0)
      Reason: Both files implement the new authentication feature

  [2] fix: Resolve null pointer in parser
      └─ src/parser.ts (+3, -1)
      Reason: Isolated bugfix in parser module

  [3] refactor: Clean up unused imports
      └─ src/utils.ts (+0, -15)
      └─ src/helpers.ts (+0, -8)
      Reason: Related cleanup across utility modules

$ uncommit commit 1
✅ Committed: feat: Add user authentication (abc1234)

$ uncommit commit 2
✅ Committed: fix: Resolve null pointer in parser (def5678)
```

---

## Implementation Order

1. **Phase 1: Foundation**
   - [ ] Set up project with `pyproject.toml`
   - [ ] Implement `models.py` (data structures)
   - [ ] Implement `config.py` (configuration loading)

2. **Phase 2: Git Layer**
   - [ ] Implement `git_ops.py` (all git operations)
   - [ ] Test git operations manually

3. **Phase 3: Agent**
   - [ ] Implement `agent.py` (tools + agent definition)
   - [ ] Test agent with ADK dev UI (`adk web`)

4. **Phase 4: CLI**
   - [ ] Implement `cli.py` (`analyze` command)
   - [ ] Implement `cli.py` (`suggest` command)
   - [ ] Implement `cli.py` (`commit` command)

5. **Phase 5: Polish**
   - [ ] Add error handling and edge cases
   - [ ] Add `--json` output format
   - [ ] Write README with installation instructions

---

## Verification Plan

### Manual Testing

1. **Test git_ops.py**: Create a test repo with uncommitted changes and verify each function works
2. **Test agent**: Run `adk web` to interact with the agent in a browser UI
3. **Test CLI**: Run commands in a real repo with uncommitted changes

### Stretch: Unit Tests

```bash
# If we add tests later
pytest tests/
```
