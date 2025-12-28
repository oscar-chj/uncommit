"""Git operations layer for uncommit."""

from __future__ import annotations

import os
from pathlib import Path

from git import Repo
from git.exc import InvalidGitRepositoryError, GitCommandError

from uncommit.models import FileChange, CommitInfo


class GitError(Exception):
    """Custom exception for git operation errors."""
    pass


def get_repo(path: str | Path = ".") -> Repo:
    """Get the git repository at the given path.
    
    Args:
        path: Path to the repository root. Defaults to current directory.
    
    Returns:
        The git Repo object.
    
    Raises:
        GitError: If the path is not a valid git repository.
    """
    try:
        return Repo(path, search_parent_directories=True)
    except InvalidGitRepositoryError:
        raise GitError(f"Not a git repository: {path}")


def get_repo_root(repo: Repo) -> Path:
    """Get the root directory of the repository.
    
    Args:
        repo: The git Repo object.
    
    Returns:
        Path to the repository root.
    """
    return Path(repo.working_dir)


def get_uncommitted_files(repo: Repo) -> list[FileChange]:
    """Get list of all uncommitted file changes (staged + unstaged + untracked).
    
    Args:
        repo: The git Repo object.
    
    Returns:
        List of FileChange objects representing all uncommitted changes.
    """
    changes: list[FileChange] = []
    
    # Check if repo has any commits
    has_commits = False
    try:
        repo.head.commit
        has_commits = True
    except ValueError:
        # Fresh repo with no commits
        pass
    
    if has_commits:
        # Get staged changes (in index, not yet committed)
        try:
            staged_diffs = repo.index.diff(repo.head.commit)
            for diff in staged_diffs:
                status = _get_diff_status(diff)
                path = diff.b_path or diff.a_path
                changes.append(FileChange(path=path, status=status))
        except Exception:
            pass
        
        # Get unstaged changes (modified but not staged)
        try:
            unstaged_diffs = repo.index.diff(None)
            for diff in unstaged_diffs:
                status = _get_diff_status(diff)
                path = diff.b_path or diff.a_path
                # Avoid duplicates if file is both staged and has more unstaged changes
                if not any(c.path == path for c in changes):
                    changes.append(FileChange(path=path, status=status))
        except Exception:
            pass
    
    # Get untracked files (new files not yet added) - works even in fresh repos
    for untracked in repo.untracked_files:
        if not any(c.path == untracked for c in changes):
            changes.append(FileChange(path=untracked, status="added"))
    
    return changes


def _get_diff_status(diff) -> str:
    """Convert a git diff type to a human-readable status string."""
    if diff.new_file:
        return "added"
    elif diff.deleted_file:
        return "deleted"
    elif diff.renamed:
        return "renamed"
    else:
        return "modified"


def get_diff(repo: Repo, file_path: str | None = None) -> str:
    """Get the diff for a specific file or all uncommitted changes.
    
    Args:
        repo: The git Repo object.
        file_path: Optional path to a specific file. If None, returns diff for all files.
    
    Returns:
        The diff content as a string.
    
    Raises:
        GitError: If there's an error getting the diff.
    """
    try:
        if file_path:
            # Get diff for specific file (both staged and unstaged)
            diff = repo.git.diff("HEAD", "--", file_path)
            if not diff:
                # Try getting diff for untracked file
                diff = repo.git.diff("--no-index", "/dev/null", file_path, with_exceptions=False)
            return diff
        else:
            # Get diff for all changes
            return repo.git.diff("HEAD")
    except GitCommandError as e:
        raise GitError(f"Failed to get diff: {e}")


def get_file_content(repo: Repo, file_path: str) -> str:
    """Read the current content of a file.
    
    Args:
        repo: The git Repo object.
        file_path: Path to the file relative to repo root.
    
    Returns:
        The file content as a string.
    
    Raises:
        GitError: If the file cannot be read.
    """
    repo_root = get_repo_root(repo)
    full_path = repo_root / file_path
    
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        raise GitError(f"File not found: {file_path}")
    except UnicodeDecodeError:
        raise GitError(f"Cannot read binary file: {file_path}")
    except Exception as e:
        raise GitError(f"Failed to read file {file_path}: {e}")


def get_recent_commits(repo: Repo, n: int = 10) -> list[CommitInfo]:
    """Get recent commit history for style matching.
    
    Args:
        repo: The git Repo object.
        n: Number of recent commits to retrieve.
    
    Returns:
        List of CommitInfo objects.
    """
    commits: list[CommitInfo] = []
    
    try:
        for commit in repo.iter_commits(max_count=n):
            commits.append(CommitInfo(
                hash=commit.hexsha[:7],
                message=commit.message.strip().split("\n")[0],  # First line only
                author=commit.author.name,
                date=commit.committed_datetime.isoformat(),
            ))
    except Exception:
        # Repository might be empty or have no commits
        pass
    
    return commits


def get_directory_structure(repo: Repo, max_depth: int = 3) -> str:
    """Get a tree representation of the project structure.
    
    Args:
        repo: The git Repo object.
        max_depth: Maximum depth to traverse.
    
    Returns:
        A string representation of the directory tree.
    """
    repo_root = get_repo_root(repo)
    lines: list[str] = []
    
    def _walk(path: Path, prefix: str, depth: int):
        if depth > max_depth:
            return
        
        # Skip hidden directories and common non-essential directories
        skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox", ".pytest_cache"}
        
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return
        
        # Filter entries
        entries = [e for e in entries if e.name not in skip_dirs and not e.name.startswith(".")]
        
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}")
            
            if entry.is_dir():
                extension = "    " if is_last else "│   "
                _walk(entry, prefix + extension, depth + 1)
    
    lines.append(repo_root.name + "/")
    _walk(repo_root, "", 1)
    
    return "\n".join(lines)


def stage_files(repo: Repo, file_paths: list[str]) -> None:
    """Stage specific files for commit.
    
    Args:
        repo: The git Repo object.
        file_paths: List of file paths to stage.
    
    Raises:
        GitError: If staging fails.
    """
    try:
        # Use git add command directly (handles empty files better than index.add)
        repo.git.add(file_paths)
    except Exception as e:
        raise GitError(f"Failed to stage files: {e}")


def create_commit(repo: Repo, message: str) -> str:
    """Create a commit with the staged changes.
    
    Args:
        repo: The git Repo object.
        message: The commit message.
    
    Returns:
        The short hash of the new commit.
    
    Raises:
        GitError: If the commit fails.
    """
    try:
        # Use git commit command directly (handles initial commits better)
        repo.git.commit("-m", message)
        # Get the hash of the commit we just made
        commit_hash = repo.git.rev_parse("HEAD", short=7)
        return commit_hash
    except Exception as e:
        raise GitError(f"Failed to create commit: {e}")


def unstage_all(repo: Repo) -> None:
    """Unstage all staged files (reset index to HEAD).
    
    Args:
        repo: The git Repo object.
    """
    try:
        repo.index.reset()
    except Exception:
        # Ignore errors, repo might be in an unusual state
        pass


def get_last_commit(repo: Repo) -> CommitInfo | None:
    """Get info about the most recent commit.
    
    Args:
        repo: The git Repo object.
    
    Returns:
        CommitInfo for the last commit, or None if no commits exist.
    """
    try:
        commit = repo.head.commit
        return CommitInfo(
            hash=commit.hexsha[:7],
            message=commit.message.strip().split("\n")[0],
            author=commit.author.name,
            date=commit.committed_datetime.isoformat(),
        )
    except (ValueError, TypeError):
        return None


def undo_last_commit(repo: Repo, keep_changes: bool = True) -> CommitInfo:
    """Undo the last commit.
    
    Args:
        repo: The git Repo object.
        keep_changes: If True, keep the changes in working directory (soft reset).
                     If False, discard changes completely (hard reset).
    
    Returns:
        CommitInfo of the undone commit.
    
    Raises:
        GitError: If there's no commit to undo or the operation fails.
    """
    last_commit = get_last_commit(repo)
    if last_commit is None:
        raise GitError("No commits to undo")
    
    try:
        if keep_changes:
            # Soft reset: undo commit but keep changes staged
            repo.git.reset("--soft", "HEAD~1")
        else:
            # Hard reset: undo commit and discard all changes
            repo.git.reset("--hard", "HEAD~1")
        return last_commit
    except Exception as e:
        raise GitError(f"Failed to undo commit: {e}")
