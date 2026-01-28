#!/usr/bin/env python3
"""
Export a .drawio file to SVGs (one per tab, named after tab titles).
Incremental by default: only exports tabs whose content changed.
Automatically pulls, commits, and pushes changes.

Usage:
    python export-drawio-svg.py <path-to-drawio-file>
"""
from __future__ import annotations

import os
import re
import sys
import json
import hashlib
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Tuple, Dict

# =============================================================================
# Configuration
# =============================================================================
SCRIPT_DIR = Path(__file__).parent.absolute()
MANIFEST_DIR = SCRIPT_DIR  # Manifest lives in this directory
DEFAULT_OUTPUT_DIR = SCRIPT_DIR.parent.parent / "figures"  # ../../figures
GIT_REMOTE = "origin"
GIT_COMMIT_MESSAGE = "Update diagrams"

# =============================================================================
# Helper Functions
# =============================================================================
def sanitize(name: str) -> str:
    """Sanitize filename by removing invalid characters."""
    name = re.sub(r'[\\/:"*?<>|]+', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name or "Untitled"


def get_page_elements(path: str) -> List[ET.Element]:
    """Extract diagram pages from .drawio file."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        return list(root.findall(".//diagram"))
    except ET.ParseError:
        return []


def page_hash(element: ET.Element) -> str:
    """Compute hash of page content to detect changes."""
    h = hashlib.sha1()

    def walk(node: ET.Element):
        h.update((node.tag or "").encode("utf-8", errors="ignore"))
        for k in sorted(node.attrib):
            h.update(k.encode("utf-8", errors="ignore"))
            h.update(str(node.attrib[k]).encode("utf-8", errors="ignore"))
        if node.text:
            h.update(node.text.encode("utf-8", errors="ignore"))
        for child in list(node):
            walk(child)
        if node.tail:
            h.update(node.tail.encode("utf-8", errors="ignore"))

    walk(element)
    return h.hexdigest()


def run_cmd(cmd: List[str], cwd: Optional[str] = None, capture: bool = False) -> subprocess.CompletedProcess:
    """Run shell command."""
    return subprocess.run(
        cmd,
        check=True,
        capture_output=capture,
        text=True,
        cwd=cwd
    )


def find_git_root(start_dir: str) -> Optional[str]:
    """Find git repository root."""
    try:
        result = run_cmd(["git", "rev-parse", "--show-toplevel"], cwd=start_dir, capture=True)
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def current_branch(repo_root: str) -> Optional[str]:
    """Get current git branch name."""
    try:
        result = run_cmd(["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"], capture=True)
        branch = result.stdout.strip()
        return branch if branch and branch != "HEAD" else None
    except subprocess.CalledProcessError:
        return None


# =============================================================================
# Manifest Management
# =============================================================================
def manifest_path(input_file: Path) -> Path:
    """Get path to manifest file for given .drawio file."""
    base = input_file.stem
    return MANIFEST_DIR / f".drawio-export.{base}.json"


def load_manifest(path: Path) -> Dict:
    """Load manifest from disk."""
    if not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_manifest(path: Path, data: Dict) -> None:
    """Save manifest to disk atomically."""
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    tmp.replace(path)


# =============================================================================
# Export Planning
# =============================================================================
def plan_pages(input_file: Path) -> Tuple[List[Tuple[int, str]], Dict[int, str]]:
    """
    Determine filenames for each page and compute content hashes.
    Returns:
        - file_specs: list of (page_index, filename)
        - page_hashes: dict of page_index -> content_hash
    """
    diagrams = get_page_elements(str(input_file))
    titles = [(d.attrib.get("name") or f"Page {i+1}") for i, d in enumerate(diagrams)] or ["Page 1"]

    # Deduplicate filenames
    seen: Dict[str, int] = {}
    file_specs: List[Tuple[int, str]] = []

    for idx, title in enumerate(titles):
        base = sanitize(title)
        name = base
        count = seen.get(base, 0)

        while name in seen:
            count += 1
            name = f"{base} ({count})"

        seen[base] = count
        seen[name] = 0
        file_specs.append((idx, name + ".svg"))

    # Compute content hashes
    hashes: Dict[int, str] = {}
    if diagrams:
        for i, element in enumerate(diagrams):
            hashes[i] = page_hash(element)
    else:
        # Fallback for single-page documents
        hashes[0] = hashlib.sha1(b"single-page-fallback").hexdigest()

    return file_specs, hashes


def determine_exports(input_file: Path, output_dir: Path) -> Tuple[List[Tuple[int, str]], Dict]:
    """
    Determine which pages need to be exported based on manifest.
    Returns:
        - to_export: list of (page_index, filename) that need export
        - new_manifest: updated manifest data
    """
    file_specs, hashes = plan_pages(input_file)
    mf_path = manifest_path(input_file)
    prev_manifest = load_manifest(mf_path)
    prev_pages: Dict[str, Dict] = prev_manifest.get("pages", {})

    to_export: List[Tuple[int, str]] = []

    for idx, filename in file_specs:
        current_hash = hashes[idx]
        prev_entry = prev_pages.get(str(idx))
        out_path = output_dir / filename

        # Export if: new page, content changed, file missing, or filename changed
        if not prev_entry:
            to_export.append((idx, filename))
        else:
            prev_hash = prev_entry.get("hash")
            prev_filename = prev_entry.get("filename")

            if (current_hash != prev_hash or
                filename != prev_filename or
                not out_path.is_file()):
                to_export.append((idx, filename))

    # Build new manifest
    new_pages = {
        str(idx): {"filename": fname, "hash": hashes[idx]}
        for idx, fname in file_specs
    }
    new_manifest = {
        "input": str(input_file.absolute()),
        "outdir": str(output_dir.absolute()),
        "pages": new_pages,
        "version": 1
    }

    return to_export, new_manifest


# =============================================================================
# Export Execution
# =============================================================================
def export_svg(input_file: Path, page_index: int, output_file: Path) -> None:
    """Export a single page from .drawio file to SVG."""
    # draw.io uses 1-based page indexing
    cmd = ["drawio", "-x", "-f", "svg", "-p", str(page_index + 1), "-o", str(output_file), str(input_file)]
    run_cmd(cmd)


def do_export(input_file: Path, output_dir: Path) -> List[Path]:
    """
    Main export function. Returns list of exported file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    to_export, new_manifest = determine_exports(input_file, output_dir)

    if not to_export:
        print("✓ No changes detected; nothing to export.")
        return []

    exported: List[Path] = []
    print(f"Exporting {len(to_export)} page(s) to {output_dir}")

    for page_idx, filename in to_export:
        output_file = output_dir / filename
        try:
            export_svg(input_file, page_idx, output_file)
            print(f"  ✓ Page {page_idx + 1}: {filename}")
            exported.append(output_file)
        except FileNotFoundError:
            print("Error: 'drawio' CLI not found in PATH.")
            print("Install from: https://github.com/jgraph/drawio-desktop/releases")
            sys.exit(2)
        except subprocess.CalledProcessError as e:
            print(f"Error exporting page {page_idx + 1}: {e}")
            sys.exit(3)

    # Save updated manifest
    save_manifest(manifest_path(input_file), new_manifest)

    return exported


# =============================================================================
# Git Operations
# =============================================================================
def git_pull(repo_root: str) -> None:
    """Pull latest changes from remote."""
    branch = current_branch(repo_root)
    if not branch:
        print("Warning: Could not determine branch; skipping pull.")
        return

    try:
        print(f"Pulling latest changes from {GIT_REMOTE}/{branch}...")
        run_cmd(["git", "-C", repo_root, "pull", GIT_REMOTE, branch])
        print("✓ Pull completed.")
    except subprocess.CalledProcessError as e:
        print(f"Error: Pull failed: {e}")
        sys.exit(4)


def git_commit_and_push(files: List[Path], input_file: Path, repo_root: str) -> None:
    """Commit and push changes."""
    if not files:
        return

    # Convert to relative paths from repo root
    rel_paths = [str(Path(f).relative_to(repo_root)) for f in files]
    rel_paths.append(str(input_file.relative_to(repo_root)))

    # Also commit manifest
    mf = manifest_path(input_file)
    if mf.is_file():
        rel_paths.append(str(mf.relative_to(repo_root)))

    # Stage and commit
    try:
        run_cmd(["git", "-C", repo_root, "add", "--"] + rel_paths)
        result = subprocess.run(
            ["git", "-C", repo_root, "commit", "-m", GIT_COMMIT_MESSAGE],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print("✓ No changes to commit.")
            return

        print(f"✓ Committed: {GIT_COMMIT_MESSAGE}")

        # Push
        branch = current_branch(repo_root)
        if not branch:
            print("Warning: Could not determine branch; skipping push.")
            return

        print(f"Pushing to {GIT_REMOTE}/{branch}...")
        run_cmd(["git", "-C", repo_root, "push", GIT_REMOTE, branch])
        print("✓ Push completed.")

    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")
        sys.exit(5)


# =============================================================================
# Main
# =============================================================================
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Standard export workflow
    input_file = Path(sys.argv[1]).absolute()
    if not input_file.is_file():
        print(f"Error: File not found: {input_file}")
        sys.exit(1)

    output_dir = DEFAULT_OUTPUT_DIR

    # Find git repo
    repo_root = find_git_root(str(output_dir))
    if not repo_root:
        print("Warning: Not a git repository; skipping git operations.")
        exported = do_export(input_file, output_dir)
        return

    # Pull, export, commit, push
    git_pull(repo_root)
    exported = do_export(input_file, output_dir)

    if exported:
        git_commit_and_push(exported, input_file, repo_root)


if __name__ == "__main__":
    main()
