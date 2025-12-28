"""Area-based context system for smart commit grouping.

This module maintains lightweight documentation about different areas of the codebase,
updated incrementally to provide context for commit suggestions.

Designed to be convertible to ADK tools in the future.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from uncommit.git_ops import get_repo, get_repo_root


# Directory names to skip when analyzing
SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    ".tox", ".pytest_cache", ".mypy_cache", "dist", "build",
    ".uncommit", ".egg-info"
}

# File extensions to analyze
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".kt", ".scala", ".sh", ".bash", ".zsh", ".yaml", ".yml",
    ".json", ".toml", ".md", ".rst", ".txt"
}


def get_uncommit_dir() -> Path:
    """Get the .uncommit directory in the repo root, creating if needed."""
    repo = get_repo()
    uncommit_dir = get_repo_root(repo) / ".uncommit"
    uncommit_dir.mkdir(exist_ok=True)
    return uncommit_dir


def get_areas_dir() -> Path:
    """Get the .uncommit/areas directory, creating if needed."""
    areas_dir = get_uncommit_dir() / "areas"
    areas_dir.mkdir(exist_ok=True)
    return areas_dir


def get_area_for_file(file_path: str) -> str:
    """Determine which area a file belongs to.
    
    Areas are based on top-level directories. Files in root are in "root" area.
    
    Args:
        file_path: Relative path to the file from repo root.
    
    Returns:
        Area name (e.g., "src_uncommit", "tests", "root")
    """
    path = Path(file_path)
    parts = path.parts
    
    if len(parts) == 1:
        # Root-level file
        return "root"
    
    # Use first 1-2 levels for area name
    if len(parts) >= 2 and parts[0] == "src":
        # src/package/ -> src_package
        return f"{parts[0]}_{parts[1]}"
    
    # Otherwise just use first directory
    return parts[0].replace("-", "_").replace(".", "_")


def get_area_files(area: str) -> list[Path]:
    """Get all code files in an area.
    
    Args:
        area: Area name.
    
    Returns:
        List of file paths relative to repo root.
    """
    repo = get_repo()
    repo_root = get_repo_root(repo)
    
    # Convert area name back to path
    if area == "root":
        search_dir = repo_root
        max_depth = 1  # Only root-level files
    elif "_" in area:
        # src_uncommit -> src/uncommit
        parts = area.split("_", 1)
        search_dir = repo_root / parts[0] / parts[1]
        max_depth = 10
    else:
        search_dir = repo_root / area
        max_depth = 10
    
    if not search_dir.exists():
        return []
    
    files: list[Path] = []
    
    def walk(path: Path, depth: int):
        if depth > max_depth:
            return
        
        try:
            for entry in path.iterdir():
                if entry.name in SKIP_DIRS or entry.name.startswith("."):
                    continue
                
                if entry.is_file():
                    if area == "root" and depth > 0:
                        continue  # For root, only include direct children
                    if entry.suffix in CODE_EXTENSIONS or entry.name in {"Makefile", "Dockerfile"}:
                        files.append(entry.relative_to(repo_root))
                elif entry.is_dir() and area != "root":
                    walk(entry, depth + 1)
        except PermissionError:
            pass
    
    walk(search_dir, 0)
    return sorted(files)


def get_area_hash(area: str) -> str:
    """Get a hash of the area's structure for staleness detection.
    
    Args:
        area: Area name.
    
    Returns:
        MD5 hash of file list.
    """
    files = get_area_files(area)
    file_list = "\n".join(str(f) for f in files)
    return hashlib.md5(file_list.encode()).hexdigest()[:12]


def load_area_doc(area: str) -> str | None:
    """Load cached area documentation from disk.
    
    Args:
        area: Area name.
    
    Returns:
        Area doc content, or None if not cached.
    """
    doc_path = get_areas_dir() / f"{area}.md"
    if not doc_path.exists():
        return None
    
    try:
        return doc_path.read_text(encoding="utf-8")
    except Exception:
        return None


def save_area_doc(area: str, content: str, structure_hash: str) -> None:
    """Save area documentation to disk.
    
    Args:
        area: Area name.
        content: Documentation content.
        structure_hash: Hash of current structure for staleness check.
    """
    doc_path = get_areas_dir() / f"{area}.md"
    
    # Prepend hash as first line for staleness detection
    full_content = f"<!-- hash:{structure_hash} -->\n{content}"
    
    try:
        doc_path.write_text(full_content, encoding="utf-8")
    except Exception:
        pass


def is_area_stale(area: str) -> bool:
    """Check if an area's documentation is stale.
    
    Args:
        area: Area name.
    
    Returns:
        True if stale/missing, False if fresh.
    """
    doc = load_area_doc(area)
    if doc is None:
        return True
    
    # Extract stored hash from first line
    first_line = doc.split("\n")[0]
    if not first_line.startswith("<!-- hash:"):
        return True
    
    stored_hash = first_line[10:22]  # Extract hash from <!-- hash:XXXX -->
    current_hash = get_area_hash(area)
    
    return stored_hash != current_hash


async def generate_area_doc(area: str, api_key: str, model: str = "gemini-2.0-flash") -> str:
    """Generate documentation for an area using Gemini.
    
    Args:
        area: Area name.
        api_key: Google API key.
        model: Model to use.
    
    Returns:
        Generated documentation.
    """
    import google.genai as genai
    
    files = get_area_files(area)
    if not files:
        return f"# Area: {area}\n\nEmpty or non-existent area."
    
    # Build file list with first few lines of each file
    file_info: list[str] = []
    repo = get_repo()
    repo_root = get_repo_root(repo)
    
    for f in files[:20]:  # Limit to 20 files
        full_path = repo_root / f
        try:
            content = full_path.read_text(encoding="utf-8")
            # Get first 10 lines or docstring
            lines = content.split("\n")[:10]
            preview = "\n".join(lines)
            if len(preview) > 500:
                preview = preview[:500] + "..."
            file_info.append(f"### {f}\n```\n{preview}\n```")
        except Exception:
            file_info.append(f"### {f}\n[unreadable]")
    
    file_context = "\n\n".join(file_info)
    
    prompt = f"""Analyze this codebase area and create concise documentation.

## Area: {area}

## Files in this area:
{file_context}

## Task
Write a brief documentation file (50-100 lines max) covering:
1. **Purpose**: What this area does (1-2 sentences)
2. **Key Files**: Brief description of each file's role
3. **Patterns**: Common patterns or conventions used
4. **Dependencies**: What this area depends on or provides

Format as clean markdown. Be concise. Focus on information useful for understanding commit context."""

    client = genai.Client(api_key=api_key)
    response = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
    )
    
    doc_content = response.text
    
    # Cache it
    structure_hash = get_area_hash(area)
    save_area_doc(area, doc_content, structure_hash)
    
    return doc_content


async def get_context_for_changes(
    changed_files: list[str],
    api_key: str,
    model: str = "gemini-2.0-flash"
) -> str:
    """Get context documentation for a set of changed files.
    
    Args:
        changed_files: List of changed file paths.
        api_key: Google API key.
        model: Model to use.
    
    Returns:
        Combined context from all affected areas.
    """
    # Determine affected areas
    areas: set[str] = set()
    for f in changed_files:
        areas.add(get_area_for_file(f))
    
    # Load or generate docs for each area
    context_parts: list[str] = []
    
    for area in sorted(areas):
        if is_area_stale(area):
            # Generate fresh doc
            doc = await generate_area_doc(area, api_key, model)
        else:
            # Load cached doc
            doc = load_area_doc(area)
            # Remove hash line
            if doc and doc.startswith("<!-- hash:"):
                doc = "\n".join(doc.split("\n")[1:])
        
        if doc:
            context_parts.append(doc)
    
    return "\n\n---\n\n".join(context_parts)


def get_all_areas() -> list[str]:
    """Get list of all areas in the repository.
    
    Returns:
        List of area names.
    """
    repo = get_repo()
    repo_root = get_repo_root(repo)
    
    areas: set[str] = {"root"}
    
    for entry in repo_root.iterdir():
        if entry.is_dir() and entry.name not in SKIP_DIRS and not entry.name.startswith("."):
            if entry.name == "src":
                # Check for packages inside src
                for subentry in entry.iterdir():
                    if subentry.is_dir() and not subentry.name.startswith("."):
                        areas.add(f"src_{subentry.name}")
            else:
                areas.add(entry.name)
    
    return sorted(areas)
