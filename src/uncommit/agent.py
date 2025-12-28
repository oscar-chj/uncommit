"""ADK Agent for analyzing and categorizing git changes."""

from __future__ import annotations

import json
from typing import Any

from google.adk.agents import Agent

from uncommit.git_ops import (
    get_repo,
    get_diff,
    get_file_content,
    get_recent_commits,
    get_directory_structure,
    get_uncommitted_files,
    GitError,
)


def get_changed_files() -> dict[str, Any]:
    """Get a list of all uncommitted files in the repository.
    
    Returns:
        dict: A dictionary with:
            - status: "success" or "error"
            - files: List of file changes with path, status, and diff (on success)
            - error_message: Error description (on error)
    """
    try:
        repo = get_repo()
        changes = get_uncommitted_files(repo)
        
        # Add diffs to each file change
        files_with_diffs = []
        for change in changes:
            try:
                diff = get_diff(repo, change.path)
                files_with_diffs.append({
                    "path": change.path,
                    "status": change.status,
                    "diff": diff[:2000] if len(diff) > 2000 else diff,  # Truncate large diffs
                })
            except GitError:
                files_with_diffs.append({
                    "path": change.path,
                    "status": change.status,
                    "diff": "[diff unavailable]",
                })
        
        return {"status": "success", "files": files_with_diffs}
    except GitError as e:
        return {"status": "error", "error_message": str(e)}
    except Exception as e:
        return {"status": "error", "error_message": f"Unexpected error: {e}"}


def get_file_diff(file_path: str) -> dict[str, Any]:
    """Get the git diff for a specific file.
    
    Args:
        file_path: Path to the file relative to the repository root.
    
    Returns:
        dict: A dictionary with:
            - status: "success" or "error"
            - diff: The diff content (on success)
            - error_message: Error description (on error)
    """
    try:
        repo = get_repo()
        diff = get_diff(repo, file_path)
        return {"status": "success", "diff": diff}
    except GitError as e:
        return {"status": "error", "error_message": str(e)}
    except Exception as e:
        return {"status": "error", "error_message": f"Unexpected error: {e}"}


def get_file_contents(file_path: str) -> dict[str, Any]:
    """Read the full content of a file for additional context.
    
    Use this when you need more context than just the diff provides.
    
    Args:
        file_path: Path to the file relative to the repository root.
    
    Returns:
        dict: A dictionary with:
            - status: "success" or "error"
            - content: The file content (on success), truncated if very large
            - error_message: Error description (on error)
    """
    try:
        repo = get_repo()
        content = get_file_content(repo, file_path)
        # Truncate very large files to avoid overwhelming the model
        if len(content) > 10000:
            content = content[:10000] + "\n\n[... truncated, file too large ...]"
        return {"status": "success", "content": content}
    except GitError as e:
        return {"status": "error", "error_message": str(e)}
    except Exception as e:
        return {"status": "error", "error_message": f"Unexpected error: {e}"}


def get_git_history(count: int = 10) -> dict[str, Any]:
    """Get recent commit history to understand the project's commit style.
    
    Use this to match the existing commit message conventions in the project.
    
    Args:
        count: Number of recent commits to retrieve (default: 10).
    
    Returns:
        dict: A dictionary with:
            - status: "success" or "error"
            - commits: List of recent commits with hash, message, author, date (on success)
            - error_message: Error description (on error)
    """
    try:
        repo = get_repo()
        commits = get_recent_commits(repo, count)
        return {
            "status": "success",
            "commits": [c.model_dump() for c in commits],
        }
    except GitError as e:
        return {"status": "error", "error_message": str(e)}
    except Exception as e:
        return {"status": "error", "error_message": f"Unexpected error: {e}"}


def get_project_structure() -> dict[str, Any]:
    """Get the project's directory structure for context.
    
    Use this to understand how the project is organized.
    
    Returns:
        dict: A dictionary with:
            - status: "success" or "error"
            - structure: A tree representation of the project (on success)
            - error_message: Error description (on error)
    """
    try:
        repo = get_repo()
        structure = get_directory_structure(repo)
        return {"status": "success", "structure": structure}
    except GitError as e:
        return {"status": "error", "error_message": str(e)}
    except Exception as e:
        return {"status": "error", "error_message": f"Unexpected error: {e}"}


# The root agent - required export for ADK
root_agent = Agent(
    name="commit_categorizer",
    model="gemini-2.0-flash",
    description="Analyzes git changes and groups them into logical commits",
    instruction="""<role>
You are an expert software engineer specializing in git workflow optimization. You analyze code changes and organize them into clean, logical commits following best practices.
</role>

<instructions>
1. **Gather**: Call get_changed_files() to retrieve all uncommitted changes with their diffs.
2. **Analyze**: Examine each file's diff to understand what was changed and why.
3. **Research** (optional): Call get_git_history() to learn the project's commit message conventions.
4. **Group**: Cluster related files into logical commit bundles based on:
   - Semantic relationship (same feature, bugfix, or refactor)
   - Single responsibility (one logical change per group)
   - Dependency order (earlier commits should not depend on later ones)
5. **Generate**: Create conventional commit messages for each group.
6. **Validate**: Ensure all changed files are assigned to exactly one group.
7. **Output**: Return a structured JSON response.
</instructions>

<constraints>
- Every changed file MUST be assigned to exactly one group
- Commit messages MUST use conventional commit format: type(scope): description
- Valid types: feat, fix, refactor, docs, chore, style, test, perf, ci, build
- Messages MUST use imperative mood ("Add feature" not "Added feature")
- Messages MUST be concise (50 chars or less for the subject line)
- Groups MUST be ordered by commit dependency (independent changes first)
</constraints>

<output_format>
Return ONLY a valid JSON object with this exact structure:

{
  "groups": [
    {
      "index": 1,
      "message": "feat(auth): add user authentication",
      "type": "feat",
      "files": ["src/auth.py", "src/login.py"],
      "reasoning": "Both files implement the new authentication feature"
    }
  ],
  "warnings": ["Optional: note any concerns or ambiguities"]
}

Field requirements:
- index: 1-based integer, represents commit order
- message: string, the full commit message
- type: string, the conventional commit type
- files: array of strings, file paths in this commit
- reasoning: string, brief explanation of why these files are grouped
- warnings: array of strings or null, optional notes about edge cases
</output_format>

<example>
Input: Changed files include src/api/users.py (new endpoint), src/models/user.py (new model), README.md (updated docs), src/utils/format.py (fixed typo)

Output:
{
  "groups": [
    {
      "index": 1,
      "message": "fix(utils): correct typo in format function",
      "type": "fix",
      "files": ["src/utils/format.py"],
      "reasoning": "Isolated typo fix, no dependencies"
    },
    {
      "index": 2,
      "message": "feat(users): add user model and API endpoint",
      "type": "feat",
      "files": ["src/models/user.py", "src/api/users.py"],
      "reasoning": "Model and endpoint are part of the same feature"
    },
    {
      "index": 3,
      "message": "docs: update README with user API documentation",
      "type": "docs",
      "files": ["README.md"],
      "reasoning": "Documentation for the new user feature"
    }
  ],
  "warnings": null
}
</example>

<final_instruction>
Think step-by-step: first gather all changes, then analyze relationships between files, then create optimal groupings. Always verify every file is assigned before outputting.
</final_instruction>""",
    tools=[get_changed_files, get_file_diff, get_file_contents, get_git_history, get_project_structure],
)
