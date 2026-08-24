"""Optional Textual user interface for myprison."""

from __future__ import annotations

import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Static, TextArea

from . import deploy, posts
from .assistant import run_ai_assistant
from .config import ToolConfig
from .hugosite import Site


class MyprisonTextualApp(App):
    """A richer terminal UI built with Textual."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #main {
        height: 1fr;
    }

    #sidebar {
        width: 42;
        min-width: 32;
        border: solid $surface;
    }

    #workspace {
        width: 1fr;
        border: solid $surface;
    }

    #post-table {
        height: 1fr;
    }

    #new-title {
        margin: 1 1 0 1;
    }

    #metadata {
        height: 5;
        padding: 0 1;
        border-bottom: solid $surface;
    }

    #editor {
        height: 1fr;
    }

    #actions {
        height: auto;
        padding: 0 1;
    }

    #status {
        height: 1;
        padding: 0 1;
    }

    Button {
        margin: 0 1 0 0;
    }
    """

    BINDINGS = [
        ("ctrl+s", "save_post", "Save"),
        ("ctrl+n", "new_post", "New"),
        ("ctrl+d", "toggle_draft", "Draft"),
        ("ctrl+b", "build_site", "Build"),
        ("ctrl+a", "ai_assistance", "AI"),
        ("f5", "refresh_posts", "Refresh"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, site_dir: Path):
        super().__init__()
        self.site = Site(site_dir)
        self.cfg = ToolConfig(self.site.root)
        self.current_post: posts.Post | None = None
        self._columns_ready = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="sidebar"):
                yield Static("Posts", id="posts-title")
                yield DataTable(id="post-table")
                yield Input(placeholder="New post title", id="new-title")
                with Horizontal(id="sidebar-actions"):
                    yield Button("New", id="new")
                    yield Button("Refresh", id="refresh")
            with Vertical(id="workspace"):
                yield Static("No post selected", id="metadata")
                yield TextArea("", id="editor")
                with Horizontal(id="actions"):
                    yield Button("Save", id="save", variant="primary")
                    yield Button("Draft", id="draft")
                    yield Button("Build", id="build")
                    yield Button("Deploy", id="deploy")
                    yield Button("AI assistance", id="ai")
                yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#post-table", DataTable)
        table.cursor_type = "row"
        editor = self.query_one("#editor", TextArea)
        _set_text(editor, "")
        self.refresh_posts()

    def refresh_posts(self) -> None:
        table = self.query_one("#post-table", DataTable)
        if not self._columns_ready:
            table.add_columns("Date", "State", "Title")
            self._columns_ready = True
        else:
            table.clear()
        for post in posts.list_posts(self.site.posts_dir):
            table.add_row(
                post.date_str,
                "DRAFT" if post.draft else "",
                post.title,
                key=str(post.path),
            )
        if self.current_post is not None and not self.current_post.path.exists():
            self.current_post = None
            self._load_post(None)
        self._status("Loaded posts from %s" % self.site.posts_dir)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        path = Path(str(event.row_key.value))
        if path.is_file():
            self._load_post(posts.parse_post(path))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "new-title":
            self.action_new_post()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "new":
            self.action_new_post()
        elif button_id == "refresh":
            self.refresh_posts()
        elif button_id == "save":
            self.action_save_post()
        elif button_id == "draft":
            self.action_toggle_draft()
        elif button_id == "build":
            self.action_build_site()
        elif button_id == "deploy":
            self.action_deploy_site()
        elif button_id == "ai":
            self.action_ai_assistance()

    def action_refresh_posts(self) -> None:
        self.refresh_posts()

    def action_new_post(self) -> None:
        title_input = self.query_one("#new-title", Input)
        title = title_input.value.strip()
        if not title:
            self._status("Enter a title first.")
            title_input.focus()
            return
        post = posts.new_post(self.site.posts_dir, title)
        title_input.value = ""
        self.refresh_posts()
        self._load_post(post)
        self.query_one("#editor", TextArea).focus()
        self._status("Created draft %s" % post.path.name)

    def action_save_post(self) -> None:
        if self.current_post is None:
            self._status("No post selected.")
            return
        editor = self.query_one("#editor", TextArea)
        self.current_post.body = _get_text(editor)
        self.current_post.save()
        self.current_post = posts.parse_post(self.current_post.path)
        self.refresh_posts()
        self._load_post(self.current_post)
        self._status("Saved %s" % self.current_post.path.name)

    def action_toggle_draft(self) -> None:
        if self.current_post is None:
            self._status("No post selected.")
            return
        self.current_post.draft = not self.current_post.draft
        self.current_post.save()
        self.current_post = posts.parse_post(self.current_post.path)
        self.refresh_posts()
        self._load_post(self.current_post)
        self._status("Draft is now %s" % self.current_post.draft)

    def action_build_site(self) -> None:
        if not self.site.hugo_available():
            self._status("Hugo is not on PATH.")
            return
        self.action_save_post()
        argv = self.site.build_argv(include_drafts=self.cfg.deploy["include_drafts"])
        rc, output = _run(argv, self.site.root)
        self._status("Build exit %d%s" % (rc, _tail_hint(output)))

    def action_deploy_site(self) -> None:
        self.action_save_post()
        try:
            result = _deploy_current_site(self.site, self.cfg)
        except Exception as exc:
            self._status("Deploy failed: %s" % exc)
            return
        self._status(result)

    def action_ai_assistance(self) -> None:
        self.action_save_post()
        with self.suspend():
            run_ai_assistant(self.site, self.cfg)
        self.refresh_posts()

    def _load_post(self, post: posts.Post | None) -> None:
        self.current_post = post
        metadata = self.query_one("#metadata", Static)
        editor = self.query_one("#editor", TextArea)
        if post is None:
            metadata.update("No post selected")
            _set_text(editor, "")
            return
        metadata.update(
            "%s\n%s   %s   %s\n%s"
            % (
                post.title,
                post.date_str,
                "DRAFT" if post.draft else "PUBLISHED",
                post.path.name,
                ", ".join(post.tags) if post.tags else "No tags",
            )
        )
        _set_text(editor, post.body)

    def _status(self, text: str) -> None:
        self.query_one("#status", Static).update(text.replace("\n", " ")[:240])


def _set_text(editor: TextArea, text: str) -> None:
    if hasattr(editor, "load_text"):
        editor.load_text(text)
    else:
        editor.text = text


def _get_text(editor: TextArea) -> str:
    return getattr(editor, "text", "")


def _run(argv: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _tail_hint(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return ": %s" % lines[-1] if lines else ""


def _deploy_current_site(site: Site, cfg: ToolConfig) -> str:
    d = cfg.deploy
    if d.get("build_first", True):
        if not site.hugo_available():
            raise RuntimeError("hugo is not on PATH")
        rc, output = _run(site.build_argv(bool(d.get("include_drafts"))), site.root)
        if rc != 0:
            return "Build failed before deploy%s" % _tail_hint(output)
    pub = site.public_dir
    if not pub.is_dir() or not any(pub.iterdir()):
        return "Nothing to deploy: public/ is empty."
    method = d.get("method")
    if method == "github":
        info = deploy.github_pages_publish(d, pub, log=lambda _msg: None)
        return "GitHub deploy complete%s" % (
            " (%s)" % info.get("sha", "")[:12] if info else ""
        )
    if method == "rsync":
        if not d.get("host"):
            return "Deploy host is not configured."
        rc, output = _run(deploy.rsync_argv(d, pub), site.root)
        return "rsync exit %d%s" % (rc, _tail_hint(output))
    if method in ("ftp", "ftps"):
        if not d.get("ftp_password"):
            return "FTP password is not configured; use the curses deploy flow."
        n = deploy.ftp_upload(d, pub, d["ftp_password"], log=lambda _msg: None)
        return "Uploaded %d files over %s." % (n, method)
    return "Unknown deployment method: %s" % method
