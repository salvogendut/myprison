"""Hugo site handling: detection, scaffolding, config read/write, themes, build."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

CONFIG_NAMES = ("hugo.toml", "config.toml")

ARCHETYPE_DEFAULT = """---
title: "{{ replace .File.ContentBaseName \"-\" \" \" | title }}"
date: {{ .Date }}
draft: true
---
"""

# Based on the official Hugo "Host on GitHub Pages" starter workflow.
GITHUB_WORKFLOW = """\
name: Deploy Hugo site to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

defaults:
  run:
    shell: bash

jobs:
  build:
    runs-on: ubuntu-latest
    env:
      HUGO_VERSION: 0.162.1
    steps:
      - name: Install Hugo CLI
        run: |
          wget -O ${{ runner.temp }}/hugo.deb \\
            https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-amd64.deb
          sudo dpkg -i ${{ runner.temp }}/hugo.deb
      - name: Checkout
        uses: actions/checkout@v4
        with:
          submodules: recursive
      - name: Setup Pages
        id: pages
        uses: actions/configure-pages@v5
      - name: Build with Hugo
        run: hugo --minify --baseURL "${{ steps.pages.outputs.base_url }}/"
      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: ./public

  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
"""


def _toml_quote(value: str) -> str:
    if "'" not in value:
        return "'%s'" % value
    return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')


class Site:
    """A Hugo site rooted at *root*."""

    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()

    # -- detection / scaffolding -------------------------------------------

    @property
    def config_path(self) -> Path | None:
        for name in CONFIG_NAMES:
            p = self.root / name
            if p.is_file():
                return p
        return None

    def exists(self) -> bool:
        return self.config_path is not None

    def create(self, title: str, base_url: str) -> None:
        """Scaffold a minimal Hugo-compatible site tree."""
        self.root.mkdir(parents=True, exist_ok=True)
        for sub in ("content/posts", "static", "themes", "layouts", "archetypes"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        cfg = self.root / "hugo.toml"
        if not cfg.exists():
            cfg.write_text(
                "baseURL = %s\n"
                "languageCode = 'en-us'\n"
                "title = %s\n" % (_toml_quote(base_url), _toml_quote(title)),
                encoding="utf-8",
            )
        arch = self.root / "archetypes" / "default.md"
        if not arch.exists():
            arch.write_text(ARCHETYPE_DEFAULT, encoding="utf-8")

    # -- paths ---------------------------------------------------------------

    @property
    def posts_dir(self) -> Path:
        return self.root / "content" / "posts"

    @property
    def public_dir(self) -> Path:
        return self.root / "public"

    @property
    def themes_dir(self) -> Path:
        return self.root / "themes"

    # -- config values (top-level TOML string keys) ---------------------------

    def get_config_value(self, key: str) -> str | None:
        path = self.config_path
        if path is None:
            return None
        rx = re.compile(r"^\s*%s\s*=\s*(.+?)\s*$" % re.escape(key))
        for line in path.read_text(encoding="utf-8").splitlines():
            m = rx.match(line)
            if m:
                raw = m.group(1)
                if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
                    return raw[1:-1]
                return raw
        return None

    def set_config_value(self, key: str, value: str) -> None:
        path = self.config_path
        if path is None:
            raise FileNotFoundError("no hugo.toml/config.toml in %s" % self.root)
        rx = re.compile(r"^\s*%s\s*=" % re.escape(key))
        lines = path.read_text(encoding="utf-8").splitlines()
        new_line = "%s = %s" % (key, _toml_quote(value))
        for i, line in enumerate(lines):
            if rx.match(line):
                lines[i] = new_line
                break
        else:
            # insert before the first table header, or append
            for i, line in enumerate(lines):
                if line.lstrip().startswith("["):
                    lines.insert(i, new_line)
                    break
            else:
                lines.append(new_line)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # -- themes ----------------------------------------------------------------

    def list_themes(self) -> list[str]:
        if not self.themes_dir.is_dir():
            return []
        return sorted(p.name for p in self.themes_dir.iterdir() if p.is_dir())

    def theme_name_from_url(self, url: str) -> str:
        name = url.rstrip("/").rsplit("/", 1)[-1]
        if name.endswith(".git"):
            name = name[:-4]
        return name

    def install_theme_argv(self, url: str) -> tuple[list[str], str]:
        """Return (git argv, theme name) to clone *url* into themes/."""
        name = self.theme_name_from_url(url)
        dest = self.themes_dir / name
        return (["git", "clone", "--depth", "1", url, str(dest)], name)

    def remove_theme(self, name: str) -> None:
        dest = self.themes_dir / name
        if dest.is_dir():
            shutil.rmtree(dest)

    # -- GitHub Pages CI -----------------------------------------------------------

    def write_github_workflow(self) -> Path:
        """Write the Hugo GitHub Pages Actions workflow; returns its path."""
        path = self.root / ".github" / "workflows" / "hugo.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(GITHUB_WORKFLOW, encoding="utf-8")
        return path

    def vendored_theme_gits(self) -> list[str]:
        """Themes that carry their own .git (invisible to a plain git push)."""
        return [
            name for name in self.list_themes()
            if (self.themes_dir / name / ".git").exists()
        ]

    # -- build -------------------------------------------------------------------

    def hugo_available(self) -> bool:
        return shutil.which("hugo") is not None

    def build_argv(self, include_drafts: bool = False) -> list[str]:
        argv = ["hugo", "--source", str(self.root)]
        if include_drafts:
            argv.append("--buildDrafts")
        return argv

    def serve_argv(self) -> list[str]:
        return ["hugo", "server", "--source", str(self.root), "--buildDrafts"]

    def run(self, argv: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(argv, cwd=str(self.root))
