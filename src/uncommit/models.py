"""Data models for uncommit."""

from pydantic import BaseModel, Field


class FileChange(BaseModel):
    """Represents a single file change in the working directory."""

    path: str = Field(description="Path to the file relative to repo root")
    status: str = Field(description="Change status: added, modified, deleted, renamed")
    diff: str | None = Field(default=None, description="The diff content for this file")


class CommitInfo(BaseModel):
    """Represents a commit from git history."""

    hash: str = Field(description="Short commit hash")
    message: str = Field(description="Commit message")
    author: str = Field(description="Author name")
    date: str = Field(description="Commit date as ISO string")


class CommitGroup(BaseModel):
    """A proposed group of files to commit together."""

    index: int = Field(description="1-based index for user reference")
    message: str = Field(description="Suggested commit message")
    type: str = Field(description="Conventional commit type: feat, fix, refactor, docs, chore, style, test")
    files: list[str] = Field(description="List of file paths in this group")
    reasoning: str = Field(description="Explanation of why these files are grouped together")


class SuggestionResult(BaseModel):
    """Result from the AI agent's analysis."""

    groups: list[CommitGroup] = Field(description="Proposed commit groups")
    warnings: list[str] | None = Field(default=None, description="Optional warnings about potential issues")
