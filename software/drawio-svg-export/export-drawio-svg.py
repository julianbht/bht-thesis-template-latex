#!/usr/bin/env python3
from __future__ import annotations

import os, re, sys, json, hashlib, subprocess, xml.etree.ElementTree as ET
from typing import List, Optional, Tuple, Dict
import typer

app = typer.Typer(add_completion=False, help="""
Export a .drawio file to SVGs (one per tab, named after tab titles),
then optionally git add/commit the SVGs + the .drawio file, and git push.

Now incremental by default: only export tabs whose content (or filename) changed.
""")

# ---------------- helpers ----------------
def sanitize(name: str) -> str:
    name = re.sub(r'[\\/:"*?<>|]+', '_', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name or "Untitled"

def get_page_elements(path: str) -> List[ET.Element]:
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        return list(root.findall(".//diagram"))
    except ET.ParseError:
        return []

def get_page_titles(path: str) -> List[str]:
    ds = get_page_elements(path)
    if not ds:
        return ["Page 1"]
    titles = []
    for i, d in enumerate(ds):
        titles.append(d.attrib.get("name") or f"Page {i+1}")
    return titles

def page_hash(e: ET.Element) -> str:
    # Hash the serialized element text + attributes (stable enough for changes)
    h = hashlib.sha1()
    # include attributes deterministically
    attrs = "|".join(f"{k}={e.attrib.get(k,'')}" for k in sorted(e.attrib))
    h.update(attrs.encode("utf-8", errors="ignore"))
    # include tag text and tail plus children serialized
    def walk(node: ET.Element):
        h.update((node.tag or "").encode("utf-8", errors="ignore"))
        for k in sorted(node.attrib):
            h.update(k.encode("utf-8", errors="ignore"))
            h.update(str(node.attrib[k]).encode("utf-8", errors="ignore"))
        if node.text:
            h.update(node.text.encode("utf-8", errors="ignore"))
        for c in list(node):
            walk(c)
        if node.tail:
            h.update(node.tail.encode("utf-8", errors="ignore"))
    walk(e)
    return h.hexdigest()

def git_pull(repo_root: str, remote: str, branch: Optional[str]) -> None:
    if not branch:
        branch = current_branch(repo_root)
    if not branch:
        typer.secho("Could not determine branch; skipping pull.", fg=typer.colors.YELLOW)
        return
    try:
        typer.echo(f"Pulling latest changes from {remote}/{branch} ...")
        run(["git", "-C", repo_root, "pull", remote, branch], check=True)
        typer.secho("Pull completed.", fg=typer.colors.GREEN)
    except subprocess.CalledProcessError as e:
        typer.secho(f"Pull failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=4)


def run(cmd: list[str], check=True, capture_output=False, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=capture_output, text=True, cwd=cwd)

def find_git_root(start_dir: str) -> Optional[str]:
    try:
        res = run(["git", "rev-parse", "--show-toplevel"], capture_output=True, cwd=start_dir)
        return res.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def current_branch(repo_root: str) -> Optional[str]:
    try:
        res = run(["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True)
        b = res.stdout.strip()
        return b if b and b != "HEAD" else None
    except subprocess.CalledProcessError:
        return None

def git_add_and_commit(paths: List[str], repo_root: str, message: str, drawio_file: Optional[str] = None) -> bool:
    # stage only the exported files (+ optional .drawio)
    if not paths and not drawio_file:
        return False
    rel: List[str] = [os.path.relpath(p, repo_root) for p in paths]
    if drawio_file:
        rel.append(os.path.relpath(drawio_file, repo_root))
    try:
        run(["git", "-C", repo_root, "add", "--"] + rel)
        cp = subprocess.run(["git", "-C", repo_root, "commit", "-m", message])
        if cp.returncode != 0:
            typer.secho("Nothing to commit (no changes).", fg=typer.colors.YELLOW)
            return False
        typer.secho(f"Committed: {message}", fg=typer.colors.GREEN)
        return True
    except FileNotFoundError:
        typer.secho("Git not found; skipping commit.", fg=typer.colors.YELLOW)
        return False
    except subprocess.CalledProcessError as e:
        typer.secho(f"Git error; skipping commit: {e}", fg=typer.colors.YELLOW)
        return False

def git_push(repo_root: str, remote: str, branch: Optional[str]) -> None:
    if not branch:
        branch = current_branch(repo_root)
    if not branch:
        typer.secho("Could not determine branch; skipping push.", fg=typer.colors.YELLOW)
        return
    has_upstream = True
    try:
        run(["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], capture_output=True)
    except subprocess.CalledProcessError:
        has_upstream = False
    try:
        if has_upstream:
            typer.echo(f"Pushing to {remote} {branch} ...")
            run(["git", "-C", repo_root, "push", remote, branch], check=True)
        else:
            typer.echo(f"No upstream set. Pushing with upstream: {remote} {branch} ...")
            run(["git", "-C", repo_root, "push", "-u", remote, branch], check=True)
        typer.secho("Push completed.", fg=typer.colors.GREEN)
    except subprocess.CalledProcessError as e:
        typer.secho(f"Push failed: {e}", fg=typer.colors.RED)

# ---------- incremental export support ----------
def manifest_path(outdir: str, input_path: str) -> str:
    base = os.path.splitext(os.path.basename(input_path))[0]
    return os.path.join(outdir, f".drawio-export.{base}.json")

def load_manifest(path: str) -> Dict:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_manifest(path: str, data: Dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, path)

def plan_pages(input_path: str, outdir: str) -> Tuple[List[Tuple[int, str]], Dict[int, str]]:
    """
    Returns:
      - file_specs: list of (page_index, filename) after de-dup
      - page_hashes: dict page_index -> sha1
    """
    diagrams = get_page_elements(input_path)
    titles = [ (d.attrib.get("name") or f"Page {i+1}") for i, d in enumerate(diagrams) ] or ["Page 1"]
    os.makedirs(outdir, exist_ok=True)

    # disambiguate duplicates
    seen: dict[str, int] = {}
    file_specs: List[Tuple[int, str]] = []
    for idx, t in enumerate(titles):
        base = sanitize(t)
        n = base
        count = seen.get(base, 0)
        while n in seen:
            count += 1
            n = f"{base} ({count})"
        seen[base] = count
        seen[n] = 0
        file_specs.append((idx, n + ".svg"))

    # compute hashes
    hashes: Dict[int, str] = {}
    if diagrams:
        for i, e in enumerate(diagrams):
            hashes[i] = page_hash(e)
    else:
        # fallback single page (unknown content)
        hashes[0] = hashlib.sha1(b"single-page-fallback").hexdigest()

    return file_specs, hashes

def incremental_selection(input_path: str, outdir: str, full: bool, clean: bool) -> Tuple[List[Tuple[int, str]], List[str], Dict]:
    """
    Decide which pages to export and which stale files to remove.
    Returns:
      - to_export: list of (page_index, filename)
      - stale_files: list of paths to delete (if clean=True)
      - new_manifest: dict for saving
    """
    file_specs, hashes = plan_pages(input_path, outdir)
    mf_path = manifest_path(outdir, input_path)
    prev = load_manifest(mf_path)
    prev_pages: Dict[str, Dict] = prev.get("pages", {})  # key: str(page_index) from last run

    to_export: List[Tuple[int, str]] = []
    # build reverse map of previous filenames to index to detect renames
    prev_by_index = {int(k): v for k, v in prev_pages.items()} if prev_pages else {}

    for idx, fname in file_specs:
        h = hashes[idx]
        prev_entry = prev_by_index.get(idx)
        if full or not prev_entry:
            to_export.append((idx, fname))
        else:
            prev_hash = prev_entry.get("hash")
            prev_fname = prev_entry.get("filename")
            # export if content changed, file missing, or target filename changed
            out_path = os.path.join(outdir, fname)
            if (h != prev_hash) or (fname != prev_fname) or (not os.path.isfile(out_path)):
                to_export.append((idx, fname))

    # stale files: any previous filename whose index no longer exists OR whose filename changed
    stale_files: List[str] = []
    if clean and prev_pages:
        current_indices = set(i for i, _ in file_specs)
        current_filenames = set(os.path.join(outdir, f) for _, f in file_specs)
        for k, v in prev_by_index.items():
            old_path = os.path.join(outdir, v.get("filename", ""))
            if (k not in current_indices) or (old_path not in current_filenames):
                if os.path.isfile(old_path):
                    stale_files.append(old_path)

    # new manifest content
    new_pages = { str(idx): {"filename": fname, "hash": hashes[idx]} for idx, fname in file_specs }
    new_manifest = {
        "input": os.path.abspath(input_path),
        "outdir": os.path.abspath(outdir),
        "pages": new_pages,
        "version": 1
    }
    return to_export, stale_files, new_manifest

def export_pages(input_path: str, outdir: str, dry_run: bool, full: bool, clean: bool) -> List[str]:
    os.makedirs(outdir, exist_ok=True)
    typer.echo(f"Export directory: {outdir}")

    to_export, stale, new_manifest = incremental_selection(input_path, outdir, full=full, clean=clean)

    if stale:
        for p in stale:
            if dry_run:
                typer.echo(f"DRY-RUN: rm {p}")
            else:
                try:
                    os.remove(p)
                    typer.secho(f"🗑  Removed stale: {os.path.basename(p)}", fg=typer.colors.YELLOW)
                except OSError as e:
                    typer.secho(f"Could not remove {p}: {e}", fg=typer.colors.RED)

    exported: List[str] = []
    if not to_export:
        typer.secho("No changes detected; nothing to export.", fg=typer.colors.CYAN)
    for page_idx, filename in to_export:
        out_path = os.path.join(outdir, filename)
        # draw.io page index is 1-based
        cmd = ["drawio", "-x", "-f", "svg", "-p", str(page_idx + 1), "-o", out_path, input_path]
        if dry_run:
            typer.echo("DRY-RUN: " + " ".join(cmd))
            exported.append(out_path)  # pretend for git staging preview
        else:
            try:
                run(cmd)
                typer.secho(f"✓ Page {page_idx + 1}: {filename}", fg=typer.colors.GREEN)
                exported.append(out_path)
            except FileNotFoundError:
                typer.secho("Error: 'drawio' CLI not found in PATH.", fg=typer.colors.RED)
                raise typer.Exit(code=2)
            except subprocess.CalledProcessError as e:
                typer.secho(f"Error exporting page {page_idx + 1}: {e}", fg=typer.colors.RED)
                raise typer.Exit(code=3)

    # save manifest (even if nothing exported—keeps filename renames consistent)
    mf_path = manifest_path(outdir, input_path)
    if dry_run:
        typer.echo(f"DRY-RUN: write {mf_path}")
    else:
        save_manifest(mf_path, new_manifest)

    return exported

# ---------------- CLI ----------------
@app.command()
def cli_export(
    input: str = typer.Argument(..., help="Path to .drawio file"),
    outdir: Optional[str] = typer.Option(
        None, "--outdir", "-o",
        help="Output directory (default: '../figures' next to current working directory)"
    ),
    git_message: str = typer.Option("Updated SVGs", "--git-message", "-m", help="Commit message"),
    push: bool = typer.Option(False, "--push", help="After commit, also push"),
    remote: str = typer.Option("origin", "--remote", help="Remote to push to"),
    branch: Optional[str] = typer.Option(None, "--branch", help="Branch to push (default: current)"),
    no_git: bool = typer.Option(False, "--no-git", help="Do not run git add/commit"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Only print actions without executing"),
    full: bool = typer.Option(False, "--full", help="Force full export of all pages (ignore manifest)"),
    clean: bool = typer.Option(True, "--clean/--no-clean", help="Delete stale/renamed SVGs based on manifest"),
):
    """
    Export SVGs (named by tab title) from a .drawio file.
    Incremental by default: exports only pages whose content or filename changed
    since the last run (tracked via a manifest). Also commits the exported SVGs AND
    the .drawio file itself, then optionally pushes.
    """
    cwd = os.getcwd()
    default_outdir = os.path.abspath(os.path.join(cwd, "..", "figures"))

    input_path = os.path.abspath(input)
    if not os.path.isfile(input_path):
        typer.secho(f"Error: input file not found: {input_path}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    outdir = os.path.abspath(outdir or default_outdir)
    exported = export_pages(input_path, outdir, dry_run=dry_run, full=full, clean=clean)

    if dry_run or no_git:
        raise typer.Exit()

    repo_root = find_git_root(outdir) or find_git_root(os.path.dirname(input_path))
    if not repo_root:
        typer.secho("Not a git repository; skipping commit/push.", fg=typer.colors.YELLOW)
        raise typer.Exit()

    # Pull latest changes first to avoid push conflicts
    git_pull(repo_root, remote, branch)

    did_commit = git_add_and_commit(exported, repo_root, git_message, drawio_file=input_path)
    if did_commit and push:
        git_push(repo_root, remote, branch)

if __name__ == "__main__":
    app()
