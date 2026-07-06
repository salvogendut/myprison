"""Built-in full-screen curses text editor (nano-style) for writing posts.

Keys:
  arrows / Home / End / PgUp / PgDn   move
  Enter / Backspace / Delete          edit
  ^S save    ^X exit (asks if modified)    ^K delete current line
Tabs are inserted as 4 spaces.
"""

from __future__ import annotations

import curses
from pathlib import Path

from .ui import KEY_ESC, safe_addstr

CTRL_S = 0x13
CTRL_X = 0x18
CTRL_K = 0x0B
TAB_SPACES = "    "


class Editor:
    def __init__(self, stdscr, path: Path, display_name: str | None = None):
        self.stdscr = stdscr
        self.path = Path(path)
        self.display_name = display_name or self.path.name
        if self.path.is_file():
            text = self.path.read_text(encoding="utf-8", errors="replace")
        else:
            text = ""
        self.lines: list[str] = text.split("\n") or [""]
        self.cy = 0
        self.cx = 0
        # start below the front matter block, if any, so typing lands in the body
        if self.lines and self.lines[0].strip() in ("---", "+++"):
            delim = self.lines[0].strip()
            for i in range(1, len(self.lines)):
                if self.lines[i].strip() == delim:
                    self.cy = min(i + 1, len(self.lines) - 1)
                    break
        self.top = 0
        self.left = 0
        self.modified = False
        self.saved_once = False
        self.status_msg = ""

    # -- persistence ----------------------------------------------------------

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(self.lines), encoding="utf-8")
        self.modified = False
        self.saved_once = True
        self.status_msg = "Saved %s" % self.path.name

    # -- drawing ----------------------------------------------------------------

    def _view_size(self):
        maxy, maxx = self.stdscr.getmaxyx()
        return maxy - 2, maxx  # minus title bar and status bar

    def _scroll_into_view(self) -> None:
        h, w = self._view_size()
        if h < 1 or w < 1:
            return
        if self.cy < self.top:
            self.top = self.cy
        if self.cy >= self.top + h:
            self.top = self.cy - h + 1
        if self.cx < self.left:
            self.left = self.cx
        if self.cx >= self.left + w - 1:
            self.left = self.cx - w + 2

    def draw(self) -> None:
        stdscr = self.stdscr
        maxy, maxx = stdscr.getmaxyx()
        h, w = self._view_size()
        stdscr.erase()
        mark = "*" if self.modified else " "
        safe_addstr(stdscr, 0, 0, " " * maxx, curses.A_REVERSE)
        safe_addstr(
            stdscr, 0, 1,
            "myprison editor %s %s" % (mark, self.display_name),
            curses.A_REVERSE | curses.A_BOLD,
        )
        for row in range(h):
            i = self.top + row
            if i >= len(self.lines):
                break
            safe_addstr(stdscr, 1 + row, 0, self.lines[i][self.left:self.left + w])
        pos = "Ln %d/%d  Col %d" % (self.cy + 1, len(self.lines), self.cx + 1)
        hints = "^S save   ^X exit   ^K del line"
        bar = (" %s   %s" % (hints, self.status_msg)).ljust(max(0, maxx - len(pos) - 2))
        safe_addstr(stdscr, maxy - 1, 0, " " * maxx, curses.A_REVERSE)
        safe_addstr(stdscr, maxy - 1, 0, bar[:maxx - len(pos) - 2], curses.A_REVERSE)
        safe_addstr(stdscr, maxy - 1, maxx - len(pos) - 1, pos, curses.A_REVERSE | curses.A_BOLD)
        try:
            stdscr.move(1 + self.cy - self.top, min(self.cx - self.left, maxx - 1))
        except curses.error:
            pass
        stdscr.refresh()

    # -- editing primitives -------------------------------------------------------

    def _clamp_cx(self) -> None:
        self.cx = min(self.cx, len(self.lines[self.cy]))

    def insert_text(self, s: str) -> None:
        line = self.lines[self.cy]
        self.lines[self.cy] = line[:self.cx] + s + line[self.cx:]
        self.cx += len(s)
        self.modified = True

    def newline(self) -> None:
        line = self.lines[self.cy]
        self.lines[self.cy] = line[:self.cx]
        self.lines.insert(self.cy + 1, line[self.cx:])
        self.cy += 1
        self.cx = 0
        self.modified = True

    def backspace(self) -> None:
        if self.cx > 0:
            line = self.lines[self.cy]
            self.lines[self.cy] = line[:self.cx - 1] + line[self.cx:]
            self.cx -= 1
            self.modified = True
        elif self.cy > 0:
            prev = self.lines[self.cy - 1]
            self.cx = len(prev)
            self.lines[self.cy - 1] = prev + self.lines[self.cy]
            del self.lines[self.cy]
            self.cy -= 1
            self.modified = True

    def delete_char(self) -> None:
        line = self.lines[self.cy]
        if self.cx < len(line):
            self.lines[self.cy] = line[:self.cx] + line[self.cx + 1:]
            self.modified = True
        elif self.cy + 1 < len(self.lines):
            self.lines[self.cy] = line + self.lines[self.cy + 1]
            del self.lines[self.cy + 1]
            self.modified = True

    def delete_line(self) -> None:
        if len(self.lines) == 1:
            if self.lines[0]:
                self.lines[0] = ""
                self.modified = True
        else:
            del self.lines[self.cy]
            self.cy = min(self.cy, len(self.lines) - 1)
            self.modified = True
        self.cx = 0

    # -- prompts ----------------------------------------------------------------------

    def _ask_exit(self) -> bool:
        """Returns True if the editor should close."""
        maxy, maxx = self.stdscr.getmaxyx()
        safe_addstr(self.stdscr, maxy - 1, 0, " " * maxx, curses.A_REVERSE)
        safe_addstr(
            self.stdscr, maxy - 1, 1,
            "Save modified buffer?  y = save & exit   n = discard   Esc = keep editing",
            curses.A_REVERSE | curses.A_BOLD,
        )
        self.stdscr.refresh()
        while True:
            ch = self.stdscr.getch()
            if ch in (ord("y"), ord("Y")):
                self.save()
                return True
            if ch in (ord("n"), ord("N")):
                return True
            if ch == KEY_ESC:
                return False

    # -- main loop ---------------------------------------------------------------------

    def run(self) -> bool:
        """Run the editor. Returns True if the file was saved at least once."""
        stdscr = self.stdscr
        stdscr.keypad(True)
        curses.curs_set(1)
        try:
            while True:
                self._scroll_into_view()
                self.draw()
                try:
                    wch = stdscr.get_wch()
                except curses.error:
                    continue
                self.status_msg = ""
                if isinstance(wch, str):
                    code = ord(wch) if len(wch) == 1 else -1
                    if code == CTRL_S:
                        self.save()
                    elif code == CTRL_X:
                        if not self.modified or self._ask_exit():
                            return self.saved_once
                    elif code == CTRL_K:
                        self.delete_line()
                    elif code in (10, 13):
                        self.newline()
                    elif code == 9:
                        self.insert_text(TAB_SPACES)
                    elif code in (8, 127):
                        self.backspace()
                    elif code == KEY_ESC:
                        pass  # ignore bare Esc; use ^X to exit
                    elif wch.isprintable():
                        self.insert_text(wch)
                else:
                    if wch == curses.KEY_UP and self.cy > 0:
                        self.cy -= 1
                        self._clamp_cx()
                    elif wch == curses.KEY_DOWN and self.cy + 1 < len(self.lines):
                        self.cy += 1
                        self._clamp_cx()
                    elif wch == curses.KEY_LEFT:
                        if self.cx > 0:
                            self.cx -= 1
                        elif self.cy > 0:
                            self.cy -= 1
                            self.cx = len(self.lines[self.cy])
                    elif wch == curses.KEY_RIGHT:
                        if self.cx < len(self.lines[self.cy]):
                            self.cx += 1
                        elif self.cy + 1 < len(self.lines):
                            self.cy += 1
                            self.cx = 0
                    elif wch == curses.KEY_HOME:
                        self.cx = 0
                    elif wch == curses.KEY_END:
                        self.cx = len(self.lines[self.cy])
                    elif wch == curses.KEY_PPAGE:
                        h, _ = self._view_size()
                        self.cy = max(0, self.cy - h)
                        self.top = max(0, self.top - h)
                        self._clamp_cx()
                    elif wch == curses.KEY_NPAGE:
                        h, _ = self._view_size()
                        self.cy = min(len(self.lines) - 1, self.cy + h)
                        self._clamp_cx()
                    elif wch == curses.KEY_BACKSPACE:
                        self.backspace()
                    elif wch == curses.KEY_DC:
                        self.delete_char()
                    elif wch == curses.KEY_RESIZE:
                        self.top = max(0, min(self.top, len(self.lines) - 1))
        finally:
            curses.curs_set(0)
