"""Optional Textual user interface for myprison."""

from __future__ import annotations

import subprocess
from pathlib import Path

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, DataTable, Footer, Header, Input, RichLog, Static, TextArea

from . import deploy, posts
from .assistant import run_ai_assistant
from .config import ToolConfig
from .hugosite import Site


class ResizeHandle(Widget):
    """Draggable divider between the posts sidebar and editor workspace."""

    can_focus = False

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self.capture_mouse()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if self.app.mouse_captured is self:
            self.app.adjust_sidebar_width(event.delta_x)
            event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self.app.mouse_captured is self:
            self.release_mouse()
            event.stop()


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
        width: 76;
        min-width: 42;
        border: solid $surface;
    }

    #splitter {
        width: 1;
        min-width: 1;
        background: $primary-background;
    }

    #splitter:hover {
        background: $accent;
    }

    #workspace {
        width: 1fr;
        border: solid $surface;
    }

    #post-table {
        height: 1fr;
    }

    #console-title {
        height: 1;
        padding: 0 1;
    }

    #console {
        height: 1fr;
        min-height: 6;
        border: solid $surface;
    }

    #new-title {
        margin: 1 1 0 1;
    }

    #format-title {
        height: 1;
        padding: 0 1;
    }

    #format-actions {
        height: auto;
        padding: 0 1;
    }

    #format-actions Button {
        min-width: 7;
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
        ("ctrl+p", "preview_site", "Preview"),
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
        self.edit_style = "current"
        self.vi_insert = True
        self._vi_pending = ""
        self._vi_command = ""

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
                yield Static("Console", id="console-title")
                yield RichLog(id="console", wrap=True, highlight=False, markup=False)
            yield ResizeHandle(id="splitter")
            with Vertical(id="workspace"):
                yield Static("No post selected", id="metadata")
                yield Static("Editor tools", id="format-title")
                with Horizontal(id="format-actions"):
                    yield Button("B", id="fmt-bold")
                    yield Button("I", id="fmt-italic")
                    yield Button("Link", id="fmt-link")
                    yield Button("Image", id="fmt-image")
                yield TextArea("", id="editor")
                with Horizontal(id="actions"):
                    yield Button("Save", id="save", variant="primary")
                    yield Button("Draft", id="draft")
                    yield Button("Build", id="build")
                    yield Button("Preview", id="preview")
                    yield Button("Deploy", id="deploy")
                    yield Button("AI assistance", id="ai")
                    yield Button("Editor: Default", id="edit-style")
                    yield Button("Quit", id="quit", variant="error")
                yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#post-table", DataTable)
        table.cursor_type = "row"
        editor = self.query_one("#editor", TextArea)
        _set_text(editor, "")
        self._log("Console ready.")
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
        elif button_id == "preview":
            self.action_preview_site()
        elif button_id == "deploy":
            self.action_deploy_site()
        elif button_id == "ai":
            self.action_ai_assistance()
        elif button_id == "edit-style":
            self.action_toggle_edit_style()
        elif button_id == "quit":
            self.exit()
        elif button_id == "fmt-bold":
            self._format_selection("**", "**", "bold text")
        elif button_id == "fmt-italic":
            self._format_selection("*", "*", "italic text")
        elif button_id == "fmt-link":
            self._format_selection("[", "](https://example.org/)", "link text")
        elif button_id == "fmt-image":
            self._format_selection("![", "](https://example.org/image.jpg)", "alt text")

    def action_refresh_posts(self) -> None:
        self.refresh_posts()

    def action_toggle_edit_style(self) -> None:
        button = self.query_one("#edit-style", Button)
        if self.edit_style == "current":
            self.edit_style = "vi"
            self.vi_insert = False
            self._vi_pending = ""
            self._vi_command = ""
            button.label = "Editor: Vi"
            self._status("Vi style: normal mode. Use i/a/o to insert, :w to save, :q to quit.")
            self.query_one("#editor", TextArea).focus()
        else:
            self.edit_style = "current"
            self.vi_insert = True
            self._vi_pending = ""
            self._vi_command = ""
            button.label = "Editor: Default"
            self._status("Default editor style.")

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
            self._log("Build skipped: hugo is not on PATH.")
            return
        self.action_save_post()
        argv = self.site.build_argv(include_drafts=self.cfg.deploy["include_drafts"])
        self._log("$ %s" % " ".join(argv))
        rc, output = _run(argv, self.site.root)
        self._log(output or "(no output)")
        self._status("Build exit %d%s" % (rc, _tail_hint(output)))

    def action_preview_site(self) -> None:
        if not self.site.hugo_available():
            self._status("Hugo is not on PATH.")
            self._log("Preview skipped: hugo is not on PATH.")
            return
        self.action_save_post()
        argv = self.site.serve_argv()
        self._log("$ %s" % " ".join(argv))
        self._status("Starting preview server; Ctrl-C returns to myprison.")
        with self.suspend():
            print("$ %s" % " ".join(argv))
            print("(Ctrl-C stops the preview server)\n")
            try:
                subprocess.call(argv, cwd=str(self.site.root))
            except KeyboardInterrupt:
                pass
            try:
                input("\n[ press Enter to return to myprison ]")
            except (EOFError, KeyboardInterrupt):
                pass
        self.refresh_posts()

    def action_deploy_site(self) -> None:
        self.action_save_post()
        try:
            result = _deploy_current_site(self.site, self.cfg, self._log)
        except Exception as exc:
            self._status("Deploy failed: %s" % exc)
            self._log("Deploy failed: %s" % exc)
            return
        self._status(result)
        self._log(result)

    def action_ai_assistance(self) -> None:
        self.action_save_post()
        with self.suspend():
            run_ai_assistant(self.site, self.cfg)
        self.refresh_posts()

    def on_key(self, event: events.Key) -> None:
        if self.edit_style != "vi":
            return
        if not self.query_one("#editor", TextArea).has_focus:
            return
        if self.vi_insert:
            if event.key == "escape":
                self.vi_insert = False
                self._status("Vi normal mode")
                event.stop()
            return
        event.stop()
        self._handle_vi_normal_key(event.key, event.character or "")

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

    def _log(self, text: str) -> None:
        log = self.query_one("#console", RichLog)
        for line in str(text).splitlines() or [""]:
            log.write(line)

    def adjust_sidebar_width(self, delta: int) -> None:
        sidebar = self.query_one("#sidebar", Vertical)
        current = sidebar.outer_size.width
        max_width = max(56, self.size.width - 60)
        new_width = max(42, min(max_width, current + int(delta)))
        sidebar.styles.width = new_width
        self._status("Sidebar width: %d" % new_width)

    def _format_selection(self, prefix: str, suffix: str, placeholder: str) -> None:
        editor = self.query_one("#editor", TextArea)
        selected = getattr(editor, "selected_text", "") or ""
        if selected:
            selection = editor.selection
            editor.replace("%s%s%s" % (prefix, selected, suffix), selection.start, selection.end)
        else:
            editor.insert("%s%s%s" % (prefix, placeholder, suffix))
        editor.focus()

    def _handle_vi_normal_key(self, key: str, char: str) -> None:
        editor = self.query_one("#editor", TextArea)
        if self._vi_command:
            self._handle_vi_command_key(key, char)
            return
        if char == ":":
            self._vi_command = ":"
            self._status(":")
            return
        if char in ("h", "j", "k", "l"):
            self._vi_move(editor, char)
            return
        if char == "i":
            self.vi_insert = True
            self._status("Vi insert mode")
            return
        if char == "a":
            self._vi_move(editor, "l")
            self.vi_insert = True
            self._status("Vi insert mode")
            return
        if char == "o":
            row, col = editor.cursor_location
            line_len = len(_text_lines(editor)[row]) if _text_lines(editor) else 0
            editor.insert("\n", (row, line_len))
            self.vi_insert = True
            self._status("Vi insert mode")
            return
        if char == "x":
            row, col = editor.cursor_location
            lines = _text_lines(editor)
            if row < len(lines):
                end_col = min(col + 1, len(lines[row]))
                if end_col > col:
                    editor.delete((row, col), (row, end_col))
            return
        if char == "d" and self._vi_pending == "d":
            self._delete_current_line(editor)
            self._vi_pending = ""
            return
        self._vi_pending = char if char == "d" else ""

    def _handle_vi_command_key(self, key: str, char: str) -> None:
        if key == "escape":
            self._vi_command = ""
            self._status("Vi normal mode")
            return
        if key == "backspace":
            self._vi_command = self._vi_command[:-1] or ":"
            self._status(self._vi_command)
            return
        if key == "enter":
            command = self._vi_command[1:].strip()
            self._vi_command = ""
            if command == "w":
                self.action_save_post()
            elif command == "q":
                self.exit()
            elif command == "wq":
                self.action_save_post()
                self.exit()
            else:
                self._status("Unknown Vi command: %s" % command)
            return
        if char and char.isprintable():
            self._vi_command += char
            self._status(self._vi_command)

    def _vi_move(self, editor: TextArea, key: str) -> None:
        lines = _text_lines(editor)
        if not lines:
            return
        row, col = editor.cursor_location
        if key == "h":
            col = max(0, col - 1)
        elif key == "l":
            col = min(len(lines[row]), col + 1)
        elif key == "j":
            row = min(len(lines) - 1, row + 1)
            col = min(col, len(lines[row]))
        elif key == "k":
            row = max(0, row - 1)
            col = min(col, len(lines[row]))
        editor.move_cursor((row, col))

    def _delete_current_line(self, editor: TextArea) -> None:
        lines = _text_lines(editor)
        if not lines:
            return
        row, _ = editor.cursor_location
        if len(lines) == 1:
            editor.replace("", (0, 0), (0, len(lines[0])))
            editor.move_cursor((0, 0))
            return
        if row + 1 < len(lines):
            editor.delete((row, 0), (row + 1, 0))
            editor.move_cursor((min(row, len(lines) - 2), 0))
        else:
            editor.delete((row - 1, len(lines[row - 1])), (row, len(lines[row])))
            editor.move_cursor((row - 1, len(lines[row - 1])))


def _set_text(editor: TextArea, text: str) -> None:
    if hasattr(editor, "load_text"):
        editor.load_text(text)
    else:
        editor.text = text


def _get_text(editor: TextArea) -> str:
    return getattr(editor, "text", "")


def _text_lines(editor: TextArea) -> list[str]:
    return _get_text(editor).splitlines() or [""]


def _run(argv: list[str], cwd: Path) -> tuple[int, str]:
    proc = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _tail_hint(output: str) -> str:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return ": %s" % lines[-1] if lines else ""


def _deploy_current_site(site: Site, cfg: ToolConfig, log=print) -> str:
    d = cfg.deploy
    if d.get("build_first", True):
        if not site.hugo_available():
            raise RuntimeError("hugo is not on PATH")
        argv = site.build_argv(bool(d.get("include_drafts")))
        log("$ %s" % " ".join(argv))
        rc, output = _run(argv, site.root)
        log(output or "(no output)")
        if rc != 0:
            return "Build failed before deploy%s" % _tail_hint(output)
    pub = site.public_dir
    if not pub.is_dir() or not any(pub.iterdir()):
        return "Nothing to deploy: public/ is empty."
    method = d.get("method")
    if method == "github":
        info = deploy.github_pages_publish(d, pub, log=log)
        return "GitHub deploy complete%s" % (
            " (%s)" % info.get("sha", "")[:12] if info else ""
        )
    if method == "rsync":
        if not d.get("host"):
            return "Deploy host is not configured."
        argv = deploy.rsync_argv(d, pub)
        log("$ %s" % " ".join(argv))
        rc, output = _run(argv, site.root)
        log(output or "(no output)")
        return "rsync exit %d%s" % (rc, _tail_hint(output))
    if method in ("ftp", "ftps"):
        if not d.get("ftp_password"):
            return "FTP password is not configured; use the curses deploy flow."
        n = deploy.ftp_upload(d, pub, d["ftp_password"], log=log)
        return "Uploaded %d files over %s." % (n, method)
    return "Unknown deployment method: %s" % method
