"""Reusable curses widgets: menus, list views, dialogs, input fields, forms."""

from __future__ import annotations

import curses

KEY_ESC = 27


def safe_addstr(win, y: int, x: int, s: str, attr: int = 0) -> None:
    """addstr that clips to the window and never raises."""
    maxy, maxx = win.getmaxyx()
    if y < 0 or y >= maxy or x >= maxx:
        return
    if x < 0:
        s = s[-x:]
        x = 0
    space = maxx - x
    if space <= 0:
        return
    try:
        win.addstr(y, x, s[:space], attr)
    except curses.error:
        pass  # writing to the bottom-right cell raises; output is still drawn


def hline(win, y: int, attr: int = 0) -> None:
    _, maxx = win.getmaxyx()
    safe_addstr(win, y, 0, "─" * maxx, attr)


def draw_titlebar(stdscr, title: str) -> None:
    _, maxx = stdscr.getmaxyx()
    safe_addstr(stdscr, 0, 0, " " * maxx, curses.A_REVERSE)
    safe_addstr(stdscr, 0, 1, title, curses.A_REVERSE | curses.A_BOLD)


def draw_statusbar(stdscr, text: str) -> None:
    maxy, maxx = stdscr.getmaxyx()
    safe_addstr(stdscr, maxy - 1, 0, " " * maxx, curses.A_REVERSE)
    safe_addstr(stdscr, maxy - 1, 1, text, curses.A_REVERSE)


def _center_win(stdscr, h: int, w: int):
    maxy, maxx = stdscr.getmaxyx()
    h = min(h, maxy)
    w = min(w, maxx)
    y = max(0, (maxy - h) // 2)
    x = max(0, (maxx - w) // 2)
    win = curses.newwin(h, w, y, x)
    win.keypad(True)
    return win


def message(stdscr, title: str, text: str) -> None:
    """Modal message box; any key dismisses."""
    lines = []
    for para in str(text).splitlines() or [""]:
        lines.append(para)
    maxy, maxx = stdscr.getmaxyx()
    w = min(maxx - 2, max(len(title) + 6, max((len(l) for l in lines), default=0) + 4, 30))
    h = min(maxy - 2, len(lines) + 4)
    win = _center_win(stdscr, h, w)
    win.erase()
    win.box()
    safe_addstr(win, 0, 2, " %s " % title, curses.A_BOLD)
    for i, line in enumerate(lines[: h - 4]):
        safe_addstr(win, 1 + i, 2, line)
    safe_addstr(win, h - 2, 2, "[ press any key ]", curses.A_DIM)
    win.refresh()
    win.getch()
    del win
    stdscr.touchwin()
    stdscr.refresh()


def confirm(stdscr, question: str, title: str = "Confirm") -> bool:
    maxy, maxx = stdscr.getmaxyx()
    w = min(maxx - 2, max(len(question) + 4, len(title) + 6, 34))
    win = _center_win(stdscr, 5, w)
    win.erase()
    win.box()
    safe_addstr(win, 0, 2, " %s " % title, curses.A_BOLD)
    safe_addstr(win, 1, 2, question)
    safe_addstr(win, 3, 2, "y = yes    n / Esc = no", curses.A_DIM)
    win.refresh()
    while True:
        ch = win.getch()
        if ch in (ord("y"), ord("Y")):
            result = True
            break
        if ch in (ord("n"), ord("N"), KEY_ESC, ord("q")):
            result = False
            break
    del win
    stdscr.touchwin()
    stdscr.refresh()
    return result


def input_dialog(
    stdscr,
    title: str,
    label: str,
    initial: str = "",
    password: bool = False,
) -> str | None:
    """Single-line text input. Returns the string, or None if cancelled (Esc)."""
    maxy, maxx = stdscr.getmaxyx()
    w = min(maxx - 2, max(60, len(label) + 4))
    win = _center_win(stdscr, 6, w)
    curses.curs_set(1)
    buf = list(initial)
    pos = len(buf)
    left = 0
    field_w = w - 4
    try:
        while True:
            win.erase()
            win.box()
            safe_addstr(win, 0, 2, " %s " % title, curses.A_BOLD)
            safe_addstr(win, 1, 2, label)
            if pos < left:
                left = pos
            if pos - left >= field_w:
                left = pos - field_w + 1
            shown = "".join(buf)
            if password:
                shown = "*" * len(shown)
            shown = shown[left:left + field_w]
            safe_addstr(win, 2, 2, " " * field_w, curses.A_UNDERLINE)
            safe_addstr(win, 2, 2, shown, curses.A_UNDERLINE)
            safe_addstr(win, 4, 2, "Enter = OK    Esc = cancel", curses.A_DIM)
            win.move(2, 2 + pos - left)
            win.refresh()
            try:
                wch = win.get_wch()
            except curses.error:
                continue
            if isinstance(wch, str):
                code = ord(wch) if len(wch) == 1 else -1
                if code in (10, 13):
                    return "".join(buf)
                if code == KEY_ESC:
                    return None
                if code in (8, 127):  # backspace
                    if pos > 0:
                        del buf[pos - 1]
                        pos -= 1
                elif code == 21:  # ^U clear
                    buf = []
                    pos = 0
                elif wch.isprintable():
                    buf.insert(pos, wch)
                    pos += 1
            else:
                if wch in (curses.KEY_ENTER,):
                    return "".join(buf)
                if wch == curses.KEY_BACKSPACE and pos > 0:
                    del buf[pos - 1]
                    pos -= 1
                elif wch == curses.KEY_DC and pos < len(buf):
                    del buf[pos]
                elif wch == curses.KEY_LEFT and pos > 0:
                    pos -= 1
                elif wch == curses.KEY_RIGHT and pos < len(buf):
                    pos += 1
                elif wch == curses.KEY_HOME:
                    pos = 0
                elif wch == curses.KEY_END:
                    pos = len(buf)
                elif wch == curses.KEY_RESIZE:
                    pass
    finally:
        curses.curs_set(0)
        del win
        stdscr.touchwin()
        stdscr.refresh()


class Menu:
    """Vertical selection menu rendered over the whole screen."""

    def __init__(self, stdscr, title: str, items: list[str], footer: str = ""):
        self.stdscr = stdscr
        self.title = title
        self.items = items
        self.footer = footer or "↑/↓ move   Enter select   q/Esc back"
        self.sel = 0

    def run(self) -> int:
        """Returns selected index, or -1 on cancel."""
        stdscr = self.stdscr
        while True:
            stdscr.erase()
            draw_titlebar(stdscr, self.title)
            draw_statusbar(stdscr, self.footer)
            maxy, _ = stdscr.getmaxyx()
            top = 2
            visible = maxy - 3
            first = max(0, min(self.sel - visible + 1, len(self.items) - visible))
            first = max(0, first)
            for row, i in enumerate(range(first, min(len(self.items), first + visible))):
                attr = curses.A_REVERSE | curses.A_BOLD if i == self.sel else 0
                prefix = " ❯ " if i == self.sel else "   "
                safe_addstr(stdscr, top + row, 1, prefix + self.items[i] + " ", attr)
            stdscr.refresh()
            ch = stdscr.getch()
            if ch in (curses.KEY_UP, ord("k")):
                self.sel = (self.sel - 1) % len(self.items)
            elif ch in (curses.KEY_DOWN, ord("j")):
                self.sel = (self.sel + 1) % len(self.items)
            elif ch in (curses.KEY_HOME,):
                self.sel = 0
            elif ch in (curses.KEY_END,):
                self.sel = len(self.items) - 1
            elif ch in (10, 13, curses.KEY_ENTER):
                return self.sel
            elif ch in (KEY_ESC, ord("q")):
                return -1
            elif ord("1") <= ch <= ord("9") and ch - ord("1") < len(self.items):
                return ch - ord("1")
            elif ch == curses.KEY_RESIZE:
                continue


class Form:
    """A vertical form of editable fields plus Save/Cancel buttons.

    fields: list of dicts with keys:
      key, label, type ('str'|'int'|'bool'|'password'|'choice'), value,
      choices (for 'choice')
    Returns dict of key -> value on save, or None on cancel.
    """

    def __init__(self, stdscr, title: str, fields: list[dict]):
        self.stdscr = stdscr
        self.title = title
        self.fields = [dict(f) for f in fields]

    def _display_value(self, f: dict) -> str:
        if f["type"] == "bool":
            return "[x] yes" if f["value"] else "[ ] no"
        if f["type"] == "password":
            return "*" * len(str(f["value"])) if f["value"] else "(not set)"
        v = str(f["value"])
        return v if v else "(empty)"

    def run(self) -> dict | None:
        stdscr = self.stdscr
        sel = 0
        n = len(self.fields)
        total = n + 2  # + Save + Cancel
        label_w = max(len(f["label"]) for f in self.fields) + 2
        while True:
            stdscr.erase()
            draw_titlebar(stdscr, self.title)
            draw_statusbar(
                stdscr,
                "↑/↓ move   Enter edit/toggle   ←/→ cycle   q/Esc cancel",
            )
            for i, f in enumerate(self.fields):
                attr = curses.A_REVERSE if i == sel else 0
                safe_addstr(stdscr, 2 + i, 2, f["label"].ljust(label_w), attr | curses.A_BOLD)
                safe_addstr(stdscr, 2 + i, 2 + label_w + 1, self._display_value(f), attr)
            save_attr = curses.A_REVERSE | curses.A_BOLD if sel == n else curses.A_BOLD
            cancel_attr = curses.A_REVERSE | curses.A_BOLD if sel == n + 1 else curses.A_BOLD
            safe_addstr(stdscr, 3 + n, 2, "[ Save ]", save_attr)
            safe_addstr(stdscr, 3 + n, 12, "[ Cancel ]", cancel_attr)
            stdscr.refresh()
            ch = stdscr.getch()
            if ch in (curses.KEY_UP, ord("k")):
                sel = (sel - 1) % total
            elif ch in (curses.KEY_DOWN, ord("j"), 9):
                sel = (sel + 1) % total
            elif ch in (KEY_ESC, ord("q")):
                return None
            elif ch in (10, 13, curses.KEY_ENTER, curses.KEY_LEFT, curses.KEY_RIGHT, ord(" ")):
                if sel == n and ch in (10, 13, curses.KEY_ENTER):
                    return {f["key"]: f["value"] for f in self.fields}
                if sel == n + 1 and ch in (10, 13, curses.KEY_ENTER):
                    return None
                if sel >= n:
                    continue
                f = self.fields[sel]
                if f["type"] == "bool":
                    f["value"] = not f["value"]
                elif f["type"] == "choice":
                    choices = f["choices"]
                    idx = choices.index(f["value"]) if f["value"] in choices else 0
                    step = -1 if ch == curses.KEY_LEFT else 1
                    f["value"] = choices[(idx + step) % len(choices)]
                elif ch in (10, 13, curses.KEY_ENTER):
                    initial = "" if f["type"] == "password" else str(f["value"])
                    res = input_dialog(
                        stdscr, self.title, f["label"] + ":", initial,
                        password=(f["type"] == "password"),
                    )
                    if res is not None:
                        if f["type"] == "int":
                            try:
                                f["value"] = int(res) if res.strip() else 0
                            except ValueError:
                                message(stdscr, "Error", "Not a number: %s" % res)
                        else:
                            f["value"] = res
            elif ch == curses.KEY_RESIZE:
                continue
