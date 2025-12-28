"""Unit tests for git_ops module."""

import os
import tempfile
from pathlib import Path

import pytest
from git import Repo

from uncommit.git_ops import (
    get_repo,
    get_repo_root,
    get_uncommitted_files,
    get_diff,
    get_file_content,
    get_recent_commits,
    get_directory_structure,
    stage_files,
    create_commit,
    unstage_all,
    get_last_commit,
    undo_last_commit,
    GitError,
)


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary git repository for testing."""
    repo = Repo.init(tmp_path)
    
    # Configure git user for commits
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()
    
    return repo


@pytest.fixture
def repo_with_commit(temp_repo, tmp_path):
    """Create a repo with an initial commit."""
    # Create a file and commit it
    test_file = tmp_path / "initial.txt"
    test_file.write_text("initial content")
    temp_repo.index.add(["initial.txt"])
    temp_repo.index.commit("Initial commit")
    
    return temp_repo


class TestGetRepo:
    """Tests for get_repo function."""
    
    def test_valid_repo(self, temp_repo, tmp_path):
        """Should return repo for valid git directory."""
        os.chdir(tmp_path)
        repo = get_repo()
        assert repo is not None
        assert Path(repo.working_dir) == tmp_path
    
    def test_invalid_repo(self, tmp_path):
        """Should raise GitError for non-git directory."""
        non_git_dir = tmp_path / "not_a_repo"
        non_git_dir.mkdir()
        
        with pytest.raises(GitError, match="Not a git repository"):
            get_repo(non_git_dir)


class TestGetRepoRoot:
    """Tests for get_repo_root function."""
    
    def test_returns_root_path(self, temp_repo, tmp_path):
        """Should return the repository root path."""
        root = get_repo_root(temp_repo)
        assert root == tmp_path


class TestGetUncommittedFiles:
    """Tests for get_uncommitted_files function."""
    
    def test_no_changes(self, repo_with_commit):
        """Should return empty list when no uncommitted changes."""
        changes = get_uncommitted_files(repo_with_commit)
        assert changes == []
    
    def test_untracked_file(self, repo_with_commit, tmp_path):
        """Should detect untracked files."""
        new_file = tmp_path / "new.txt"
        new_file.write_text("new content")
        
        changes = get_uncommitted_files(repo_with_commit)
        assert len(changes) == 1
        assert changes[0].path == "new.txt"
        assert changes[0].status == "added"
    
    def test_modified_file(self, repo_with_commit, tmp_path):
        """Should detect modified files."""
        existing = tmp_path / "initial.txt"
        existing.write_text("modified content")
        
        changes = get_uncommitted_files(repo_with_commit)
        assert len(changes) == 1
        assert changes[0].path == "initial.txt"
        assert changes[0].status == "modified"
    
    def test_fresh_repo_with_untracked(self, temp_repo, tmp_path):
        """Should work with fresh repo (no commits) and untracked files."""
        new_file = tmp_path / "first.txt"
        new_file.write_text("first file")
        
        changes = get_uncommitted_files(temp_repo)
        assert len(changes) == 1
        assert changes[0].status == "added"


class TestGetDiff:
    """Tests for get_diff function."""
    
    def test_diff_modified_file(self, repo_with_commit, tmp_path):
        """Should return diff for modified file."""
        existing = tmp_path / "initial.txt"
        existing.write_text("modified content")
        
        diff = get_diff(repo_with_commit, "initial.txt")
        assert "initial content" in diff or "modified content" in diff


class TestGetFileContent:
    """Tests for get_file_content function."""
    
    def test_read_existing_file(self, repo_with_commit, tmp_path):
        """Should read file content."""
        content = get_file_content(repo_with_commit, "initial.txt")
        assert content == "initial content"
    
    def test_missing_file(self, repo_with_commit):
        """Should raise GitError for missing file."""
        with pytest.raises(GitError, match="File not found"):
            get_file_content(repo_with_commit, "nonexistent.txt")


class TestGetRecentCommits:
    """Tests for get_recent_commits function."""
    
    def test_returns_commits(self, repo_with_commit):
        """Should return list of commits."""
        commits = get_recent_commits(repo_with_commit)
        assert len(commits) == 1
        assert commits[0].message == "Initial commit"
    
    def test_fresh_repo(self, temp_repo):
        """Should return empty list for fresh repo."""
        commits = get_recent_commits(temp_repo)
        assert commits == []


class TestGetDirectoryStructure:
    """Tests for get_directory_structure function."""
    
    def test_returns_tree(self, repo_with_commit, tmp_path):
        """Should return directory tree."""
        structure = get_directory_structure(repo_with_commit)
        assert "initial.txt" in structure


class TestStageFiles:
    """Tests for stage_files function."""
    
    def test_stage_untracked(self, repo_with_commit, tmp_path):
        """Should stage untracked files."""
        new_file = tmp_path / "staged.txt"
        new_file.write_text("staged content")
        
        stage_files(repo_with_commit, ["staged.txt"])
        
        # Check file is staged
        staged = [item.a_path for item in repo_with_commit.index.diff("HEAD")]
        assert "staged.txt" in staged or len(repo_with_commit.index.diff("HEAD")) > 0


class TestCreateCommit:
    """Tests for create_commit function."""
    
    def test_create_commit(self, repo_with_commit, tmp_path):
        """Should create a commit."""
        new_file = tmp_path / "to_commit.txt"
        new_file.write_text("commit me")
        
        stage_files(repo_with_commit, ["to_commit.txt"])
        commit_hash = create_commit(repo_with_commit, "Test commit")
        
        assert len(commit_hash) == 7
        assert repo_with_commit.head.commit.message.strip() == "Test commit"


class TestUnstageAll:
    """Tests for unstage_all function."""
    
    def test_unstage(self, repo_with_commit, tmp_path):
        """Should unstage all staged files."""
        new_file = tmp_path / "staged.txt"
        new_file.write_text("content")
        stage_files(repo_with_commit, ["staged.txt"])
        
        unstage_all(repo_with_commit)
        # After unstage, file should be untracked again
        assert "staged.txt" in repo_with_commit.untracked_files


class TestGetLastCommit:
    """Tests for get_last_commit function."""
    
    def test_returns_commit_info(self, repo_with_commit):
        """Should return info about last commit."""
        last = get_last_commit(repo_with_commit)
        assert last is not None
        assert last.message == "Initial commit"
        assert len(last.hash) == 7
    
    def test_fresh_repo(self, temp_repo):
        """Should return None for fresh repo."""
        last = get_last_commit(temp_repo)
        assert last is None


class TestUndoLastCommit:
    """Tests for undo_last_commit function."""
    
    def test_undo_mixed(self, repo_with_commit, tmp_path):
        """Should undo commit with mixed mode (unstaged)."""
        # Create a second commit
        new_file = tmp_path / "second.txt"
        new_file.write_text("second")
        stage_files(repo_with_commit, ["second.txt"])
        create_commit(repo_with_commit, "Second commit")
        
        undone = undo_last_commit(repo_with_commit, mode="mixed")
        
        assert undone.message == "Second commit"
        assert get_last_commit(repo_with_commit).message == "Initial commit"
    
    def test_undo_soft(self, repo_with_commit, tmp_path):
        """Should undo commit with soft mode (staged)."""
        new_file = tmp_path / "third.txt"
        new_file.write_text("third")
        stage_files(repo_with_commit, ["third.txt"])
        create_commit(repo_with_commit, "Third commit")
        
        undone = undo_last_commit(repo_with_commit, mode="soft")
        
        assert undone.message == "Third commit"
    
    def test_undo_no_commits(self, temp_repo):
        """Should raise GitError when no commits to undo."""
        with pytest.raises(GitError, match="No commits to undo"):
            undo_last_commit(temp_repo)
