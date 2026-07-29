"""Per-site tool configuration stored in .myprison.json at the site root.

Holds deployment and AI settings. The file may contain secrets, so it is
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
    "gh_watch_actions": True,  # after publishing, wait for the Actions run
    "delete_remote": True,     # rsync --delete (rsync only)
    "build_first": True,       # run `hugo` before syncing
    "include_drafts": False,   # pass --buildDrafts to hugo
}

DEFAULT_AI = {
    "provider": "chatgpt",
    "providers": {
        "chatgpt": {
            "model": "gpt-5.6-terra",
            "api_key": "",
            "web_search": True,
        },
    },
}


class ToolConfig:
    def __init__(self, site_root: Path):
        self.path = Path(site_root) / CONFIG_FILENAME
        self.data: dict = {
            "deploy": dict(DEFAULT_DEPLOY),
            "ai": dict(DEFAULT_AI),
        }
        self.load()

    def load(self) -> None:
        if self.path.is_file():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return
            deploy = dict(DEFAULT_DEPLOY)
            deploy.update(loaded.get("deploy", {}))
            ai = dict(DEFAULT_AI)
            ai.update(loaded.get("ai", {}))
            # Backward compatibility for early AI config drafts that stored
            # model/api_key directly under "ai".
            providers = dict(DEFAULT_AI["providers"])
            providers.update(ai.get("providers", {}))
            if ai.get("model") or ai.get("api_key"):
                chatgpt = dict(providers.get("chatgpt", {}))
                if ai.get("model"):
                    chatgpt["model"] = ai["model"]
                if ai.get("api_key"):
                    chatgpt["api_key"] = ai["api_key"]
                providers["chatgpt"] = chatgpt
                ai.pop("model", None)
                ai.pop("api_key", None)
            ai["providers"] = providers
            self.data = {"deploy": deploy, "ai": ai}

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

    @property
    def ai(self) -> dict:
        return self.data["ai"]
