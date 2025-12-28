"""CLI commands for uncommit."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.spinner import Spinner
from rich.live import Live

from uncommit.config import load_config
from uncommit.git_ops import (
    get_repo,
    get_uncommitted_files,
    get_diff,
    stage_files,
    create_commit,
    unstage_all,
    GitError,
    get_repo_root,
)
from uncommit.models import CommitGroup, SuggestionResult

app = typer.Typer(
    name="uncommit",
    help="AI-powered commit organizer - group your changes into clean commits",
    no_args_is_help=True,
)
console = Console()

# Cache file name (stored in repo root)
CACHE_FILENAME = ".uncommit_cache.json"


def _get_cache_path() -> Path:
    """Get the path to the cache file in the current repo."""
    try:
        repo = get_repo()
        return get_repo_root(repo) / CACHE_FILENAME
    except GitError:
        return Path.cwd() / CACHE_FILENAME


def _load_cached_suggestions() -> SuggestionResult | None:
    """Load cached suggestions from disk."""
    cache_path = _get_cache_path()
    if not cache_path.exists():
        return None
    try:
        with open(cache_path, "r") as f:
            data = json.load(f)
            return SuggestionResult(**data)
    except Exception:
        return None


def _save_cached_suggestions(result: SuggestionResult) -> None:
    """Save suggestions to disk cache."""
    cache_path = _get_cache_path()
    try:
        with open(cache_path, "w") as f:
            json.dump(result.model_dump(), f, indent=2)
    except Exception:
        pass  # Silently fail if we can't write cache


def _clear_cache() -> None:
    """Clear the cache file."""
    cache_path = _get_cache_path()
    try:
        if cache_path.exists():
            cache_path.unlink()
    except Exception:
        pass


def _print_error(message: str) -> None:
    """Print an error message and exit."""
    console.print(f"[red]✗[/red] {message}")
    raise typer.Exit(1)


def _print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


@app.command()
def analyze(
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Analyze uncommitted changes and list them."""
    try:
        repo = get_repo()
        changes = get_uncommitted_files(repo)
    except GitError as e:
        _print_error(str(e))
        return

    if not changes:
        if json_output:
            print(json.dumps({"files": [], "count": 0}))
        else:
            console.print("[yellow]No uncommitted changes found.[/yellow]")
        return

    if json_output:
        output = {
            "files": [{"path": c.path, "status": c.status} for c in changes],
            "count": len(changes),
        }
        print(json.dumps(output, indent=2))
    else:
        table = Table(title=f"📂 Uncommitted Changes ({len(changes)} files)")
        table.add_column("Status", style="cyan", width=10)
        table.add_column("File", style="white")

        status_colors = {
            "added": "green",
            "modified": "yellow",
            "deleted": "red",
            "renamed": "blue",
        }

        for change in changes:
            color = status_colors.get(change.status, "white")
            table.add_row(f"[{color}]{change.status}[/{color}]", change.path)

        console.print(table)


async def _run_agent_async(changes: list, model_override: str | None, config_model: str) -> str:
    """Run the agent using google-genai directly for more reliable CLI usage."""
    import google.genai as genai
    from uncommit.agent import root_agent
    from uncommit.config import load_config
    
    # Get API key
    config = load_config()
    
    # Configure the client
    client = genai.Client(api_key=config.api_key)
    
    # Determine model
    model_name = model_override or config_model or "gemini-2.0-flash"
    
    # Build the file list as context
    file_list = "\n".join([f"- {c.path} ({c.status})" for c in changes])
    
    # Get diffs for each file
    from uncommit.git_ops import get_repo, get_diff
    repo = get_repo()
    diffs = []
    for c in changes:
        try:
            diff = get_diff(repo, c.path)
            if diff and len(diff) > 2000:
                diff = diff[:2000] + "\n... [truncated]"
            diffs.append(f"### {c.path}\n```diff\n{diff}\n```")
        except Exception:
            diffs.append(f"### {c.path}\n[diff unavailable]")
    
    diff_context = "\n\n".join(diffs)
    
    # Build the full prompt
    prompt = f"""Analyze these uncommitted git changes and group them into logical commits.

## Changed Files
{file_list}

## Diffs
{diff_context}

{root_agent.instruction}"""
    
    # Call the model
    response = await client.aio.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    
    return response.text


@app.command()
def suggest(
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview without caching results"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override default model"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
) -> None:
    """Use AI to suggest commit groups for your changes."""

    # Load config
    config = load_config()
    if not config.api_key:
        _print_error(
            "GOOGLE_API_KEY not set. Please set it in your environment or config file.\n"
            "  export GOOGLE_API_KEY='your-api-key'"
        )
        return

    # Check for changes
    try:
        repo = get_repo()
        changes = get_uncommitted_files(repo)
    except GitError as e:
        _print_error(str(e))
        return

    if not changes:
        if json_output:
            print(json.dumps({"groups": [], "message": "No uncommitted changes found"}))
        else:
            console.print("[yellow]No uncommitted changes found.[/yellow]")
        return

    # Run the agent with spinner (Docker-style dots)
    try:
        if not json_output:
            console.print()
            with Live(
                Spinner("dots", text=f"[cyan]Analyzing {len(changes)} changed files...[/cyan]"),
                console=console,
                transient=True,
            ) as live:
                response_text = asyncio.run(_run_agent_async(changes, model, config.model))
        else:
            response_text = asyncio.run(_run_agent_async(changes, model, config.model))
        
        # Parse the JSON response from the agent
        json_start = response_text.find("{")
        json_end = response_text.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            _print_error("Agent did not return valid JSON. Response:\n" + response_text[:500])
            return
            
        json_str = response_text[json_start:json_end]
        result_data = json.loads(json_str)
        result = SuggestionResult(**result_data)

    except ImportError as e:
        _print_error(f"Failed to import ADK components: {e}\nMake sure google-adk is installed: pip install google-adk")
        return
    except json.JSONDecodeError as e:
        _print_error(f"Failed to parse agent response as JSON: {e}")
        return
    except Exception as e:
        _print_error(f"Agent error: {e}")
        return

    # Cache results unless dry-run
    if not dry_run:
        _save_cached_suggestions(result)

    # Output results
    if json_output:
        print(json.dumps(result.model_dump(), indent=2))
    else:
        _print_suggestions(result)


def _print_suggestions(result: SuggestionResult) -> None:
    """Pretty-print the suggestion results."""
    console.print(Panel.fit("📦 [bold]Proposed Commits[/bold]", border_style="blue"))
    console.print()

    for group in result.groups:
        # Group header
        type_colors = {
            "feat": "green",
            "fix": "red",
            "refactor": "yellow",
            "docs": "blue",
            "chore": "magenta",
            "style": "cyan",
            "test": "white",
            "perf": "green",
            "ci": "magenta",
            "build": "yellow",
        }
        color = type_colors.get(group.type, "white")
        
        console.print(f"  [bold]\\[{group.index}][/bold] [{color}]{group.message}[/{color}]")
        
        # Files in this group
        for file in group.files:
            console.print(f"      └─ {file}")
        
        # Reasoning (dimmed)
        console.print(f"      [dim]Reason: {group.reasoning}[/dim]")
        console.print()

    # Warnings if any
    if result.warnings:
        console.print("[yellow]⚠ Warnings:[/yellow]")
        for warning in result.warnings:
            console.print(f"  • {warning}")
        console.print()

    # Usage hint
    console.print("[dim]Use 'uncommit commit <index>' to commit a group, or 'uncommit commit --all' for all.[/dim]")


@app.command()
def commit(
    group_index: Optional[int] = typer.Argument(None, help="Index of the group to commit (1-based)"),
    all_groups: bool = typer.Option(False, "--all", "-a", help="Commit all groups sequentially"),
    message: Optional[str] = typer.Option(None, "--message", "-m", help="Override commit message"),
) -> None:
    """Commit a specific group or all groups."""
    cached_suggestions = _load_cached_suggestions()

    if cached_suggestions is None:
        _print_error("No suggestions cached. Run 'uncommit suggest' first.")
        return

    if not all_groups and group_index is None:
        _print_error("Please specify a group index or use --all")
        return

    try:
        repo = get_repo()
    except GitError as e:
        _print_error(str(e))
        return

    groups_to_commit: list[CommitGroup] = []

    if all_groups:
        groups_to_commit = list(cached_suggestions.groups)
    else:
        # Find the group by index
        group = next((g for g in cached_suggestions.groups if g.index == group_index), None)
        if group is None:
            _print_error(f"Group {group_index} not found. Available: {[g.index for g in cached_suggestions.groups]}")
            return
        groups_to_commit = [group]

    # Commit each group
    for group in groups_to_commit:
        try:
            # Unstage everything first
            unstage_all(repo)
            
            # Stage files in this group
            stage_files(repo, group.files)
            
            # Commit with the message
            commit_message = message if message else group.message
            commit_hash = create_commit(repo, commit_message)
            
            _print_success(f"Committed: {commit_message} ([cyan]{commit_hash}[/cyan])")
            
            # Remove this group from cached suggestions and save
            cached_suggestions.groups = [g for g in cached_suggestions.groups if g.index != group.index]
            _save_cached_suggestions(cached_suggestions)
            
        except GitError as e:
            _print_error(f"Failed to commit group {group.index}: {e}")
            return

    # Clear cache if all groups committed
    if not cached_suggestions.groups:
        _clear_cache()
        console.print("\n[green]All groups committed![/green]")


@app.command()
def clear() -> None:
    """Clear cached suggestions."""
    _clear_cache()
    _print_success("Cached suggestions cleared")


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
