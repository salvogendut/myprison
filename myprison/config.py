"""Per-site tool configuration stored in .myprison.json at the site root.

Holds deployment settings. The file may contain an FTP password, so it is
written with mode 0600 and should be kept out of version control.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_FILENAME = ".myprison.json"

DEFAULT_DEPLOY = {
    "method": "rsync",        # rsync | ftp | ftps | github
    "host": "",
    "port": 0,                 # 0 = default for the method (22 / 21)
    "user": "",
    "remote_path": "",
    "ssh_key": "",            # optional identity file for rsync/ssh
    "ftp_password": "",       # optional; prompted at deploy time if empty
    "gh_repo": "",            # GitHub Pages: local repo path or remote git URL
    "gh_branch": "gh-pages",  # branch for remote-URL publishing
    "gh_cname": "",           # custom domain -> CNAME file
    "delete_remote": True,     # rsync --delete (rsync only)
    "build_first": True,       # run `hugo` before syncing
    "include_drafts": False,   # pass --buildDrafts to hugo
}


class ToolConfig:
    def __init__(self, site_root: Path):
        self.path = Path(site_root) / CONFIG_FILENAME
        self.data: dict = {"deploy": dict(DEFAULT_DEPLOY)}
        self.load()

    def load(self) -> None:
        if self.path.is_file():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return
            deploy = dict(DEFAULT_DEPLOY)
            deploy.update(loaded.get("deploy", {}))
            self.data = {"deploy": deploy}

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self.data, indent=2) + "\n", encoding="utf-8"
        )
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @property
    def deploy(self) -> dict:
        return self.data["deploy"]
