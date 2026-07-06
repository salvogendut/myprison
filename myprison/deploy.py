"""Deployment of the built site (public/) to a remote web server.

Two transports:
  - rsync over SSH (recommended): incremental, optional --delete
  - FTP / FTPS via ftplib: full upload walk, remote dirs created as needed
"""

from __future__ import annotations

import ftplib
import os
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
