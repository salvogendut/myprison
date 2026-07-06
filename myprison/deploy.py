"""Deployment of the built site (public/) to a remote web server.

Three transports:
  - rsync over SSH (recommended): incremental, optional --delete
  - FTP / FTPS via ftplib: full upload walk, remote dirs created as needed
  - GitHub Pages: force-push public/ to a branch (default gh-pages)
"""

from __future__ import annotations

import ftplib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def rsync_argv(deploy: dict, local_dir: Path) -> list[str]:
    """Build the rsync command line for the given deploy config."""
    ssh_parts = ["ssh"]
    port = int(deploy.get("port") or 0)
    if port:
        ssh_parts += ["-p", str(port)]
    key = deploy.get("ssh_key", "").strip()
    if key:
        ssh_parts += ["-i", os.path.expanduser(key)]
    argv = ["rsync", "-avz", "-e", " ".join(ssh_parts)]
    if deploy.get("delete_remote", True):
        argv.append("--delete")
    remote = "%s@%s:%s" % (deploy["user"], deploy["host"], deploy["remote_path"])
    if not deploy.get("user"):
        remote = "%s:%s" % (deploy["host"], deploy["remote_path"])
    argv += [str(local_dir) + "/", remote]
    return argv


# -- GitHub Pages ------------------------------------------------------------

# kept when cleaning a local Pages repo: repo housekeeping, not site output
_PAGES_KEEP = {".git", ".github", ".gitignore", "README.md", "LICENSE"}


def _write_pages_extras(dest: Path, deploy: dict) -> None:
    (dest / ".nojekyll").touch()
    cname = deploy.get("gh_cname", "").strip()
    if cname:
        (dest / "CNAME").write_text(cname + "\n", encoding="utf-8")


def _git(repo: Path, *args: str, log=print) -> subprocess.CompletedProcess:
    argv = ["git", "-C", str(repo), *args]
    log("$ %s" % " ".join(argv))
    return subprocess.run(argv, check=True)


def github_pages_publish(deploy: dict, local_dir: Path, log=print) -> None:
    """Publish local_dir (the built site) to GitHub Pages.

    deploy['gh_repo'] may be:
      - a local git repository path (e.g. ~/Dev/chimeric): the built site is
        copied in, committed on the current branch, and pushed to origin;
      - a remote URL: the site is force-pushed to branch deploy['gh_branch']
        (default gh-pages) from a temporary repository.
    """
    target = deploy.get("gh_repo", "").strip()
    if not target:
        raise ValueError("GitHub Pages repository is not set (deployment settings)")
    local_candidate = Path(target).expanduser()
    if (local_candidate / ".git").exists():
        _publish_to_local_repo(deploy, Path(local_dir), local_candidate, log)
    else:
        _publish_to_remote(deploy, Path(local_dir), target, log)


def _publish_to_local_repo(deploy: dict, site_dir: Path, repo: Path, log=print) -> None:
    repo = repo.resolve()
    log("Publishing into local repository %s" % repo)
    kept = []
    for entry in repo.iterdir():
        if entry.name in _PAGES_KEEP:
            kept.append(entry.name)
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    if kept:
        log("(kept: %s)" % ", ".join(sorted(kept)))
    shutil.copytree(site_dir, repo, dirs_exist_ok=True)
    _write_pages_extras(repo, deploy)
    _git(repo, "add", "-A", log=log)
    staged = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--quiet"]
    )
    if staged.returncode == 0:
        log("No changes since the last publish — nothing to push.")
        return
    _git(repo, "commit", "-m", "Publish site (myprison)", log=log)
    _git(repo, "push", "origin", "HEAD", log=log)
    log("\nPublished: pushed current branch of %s to origin." % repo.name)


def _publish_to_remote(deploy: dict, site_dir: Path, url: str, log=print) -> None:
    branch = (deploy.get("gh_branch") or "gh-pages").strip()
    tmp = Path(tempfile.mkdtemp(prefix="myprison-pages-"))
    try:
        shutil.copytree(site_dir, tmp, dirs_exist_ok=True)
        _write_pages_extras(tmp, deploy)
        _git(tmp, "init", "-q", "-b", branch, log=log)
        _git(tmp, "add", "-A", log=log)
        _git(tmp, "-c", "user.name=myprison", "-c", "user.email=myprison@localhost",
             "commit", "-q", "-m", "Publish site (myprison)", log=log)
        _git(tmp, "push", "--force", url, "HEAD:refs/heads/%s" % branch, log=log)
        log("\nPublished: force-pushed to %s branch %s." % (url, branch))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# -- FTP ---------------------------------------------------------------------


def _ftp_mkdirs(ftp: ftplib.FTP, remote_dir: str) -> None:
    """Create remote_dir (absolute or relative) piece by piece, ignoring existing."""
    parts = [p for p in remote_dir.split("/") if p]
    prefix = "/" if remote_dir.startswith("/") else ""
    for part in parts:
        prefix = prefix + part
        try:
            ftp.mkd(prefix)
        except ftplib.error_perm:
            pass  # already exists (or no permission; cwd below will fail loudly)
        prefix += "/"


def ftp_upload(deploy: dict, local_dir: Path, password: str, log=print) -> int:
    """Upload local_dir tree to deploy['remote_path'] over FTP/FTPS.

    Returns the number of files uploaded. Raises ftplib errors / OSError on failure.
    """
    use_tls = deploy.get("method") == "ftps"
    ftp: ftplib.FTP = ftplib.FTP_TLS() if use_tls else ftplib.FTP()
    host = deploy["host"]
    port = int(deploy.get("port") or 21)
    log("Connecting to %s:%d (%s)..." % (host, port, "FTPS" if use_tls else "FTP"))
    ftp.connect(host, port, timeout=30)
    ftp.login(deploy.get("user") or "anonymous", password)
    if use_tls:
        assert isinstance(ftp, ftplib.FTP_TLS)
        ftp.prot_p()

    remote_root = deploy.get("remote_path", "").rstrip("/") or "."
    if remote_root != ".":
        _ftp_mkdirs(ftp, remote_root)
        ftp.cwd(remote_root)

    count = 0
    local_dir = Path(local_dir)
    for root, dirs, files in os.walk(local_dir):
        dirs.sort()
        rel = os.path.relpath(root, local_dir)
        if rel != ".":
            _ftp_mkdirs(ftp, rel)
        for name in sorted(files):
            local_file = Path(root) / name
            remote_file = name if rel == "." else "%s/%s" % (rel, name)
            log("  put %s" % remote_file)
            with open(local_file, "rb") as fh:
                ftp.storbinary("STOR %s" % remote_file, fh)
            count += 1
    ftp.quit()
    return count
