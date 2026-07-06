"""Main curses application: screens and actions."""

from __future__ import annotations

import curses
import subprocess
from datetime import datetime
from pathlib import Path

from . import __version__, deploy, posts, ui
from .config import ToolConfig
from .editor import Editor
from .hugosite import Site


def run_external(stdscr, func) -> None:
    """Suspend curses, run func() on the normal terminal, wait for Enter."""
    curses.def_prog_mode()
    curses.endwin()
    try:
        func()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as exc:  # surface errors instead of crashing the UI
        print("\nERROR: %s" % exc)
    try:
        input("\n[ press Enter to return to myprison ]")
    except (EOFError, KeyboardInterrupt):
        pass
    curses.reset_prog_mode()
    stdscr.touchwin()
    stdscr.refresh()


class App:
    def __init__(self, stdscr, site: Site):
        self.stdscr = stdscr
        self.site = site
        self.cfg = ToolConfig(site.root)

    # -- posts -----------------------------------------------------------------

    def posts_screen(self) -> None:
        sel = 0
        while True:
            all_posts = posts.list_posts(self.site.posts_dir)
            stdscr = self.stdscr
            stdscr.erase()
            ui.draw_titlebar(
                stdscr, "Posts — %d, newest first" % len(all_posts)
            )
            ui.draw_statusbar(
                stdscr,
                "Enter edit   n new   m metadata   d delete   q back",
            )
            maxy, maxx = stdscr.getmaxyx()
            visible = maxy - 3
            if not all_posts:
                ui.safe_addstr(stdscr, 2, 2, "No posts yet. Press n to write the first one.")
                stdscr.refresh()
            else:
                sel = max(0, min(sel, len(all_posts) - 1))
                first = max(0, min(sel - visible + 1, len(all_posts) - visible))
                first = max(0, first)
                for row, i in enumerate(range(first, min(len(all_posts), first + visible))):
                    p = all_posts[i]
                    attr = curses.A_REVERSE | curses.A_BOLD if i == sel else 0
                    flag = "DRAFT" if p.draft else "     "
                    line = " %s  %s  %s" % (p.date_str, flag, p.title)
                    ui.safe_addstr(stdscr, 2 + row, 1, line.ljust(maxx - 2), attr)
                stdscr.refresh()
            ch = stdscr.getch()
            if ch in (ui.KEY_ESC, ord("q")):
                return
            if ch == ord("n"):
                self.new_post()
                sel = 0
                continue
            if not all_posts:
                continue
            if ch in (curses.KEY_UP, ord("k")):
                sel = (sel - 1) % len(all_posts)
            elif ch in (curses.KEY_DOWN, ord("j")):
                sel = (sel + 1) % len(all_posts)
            elif ch == curses.KEY_HOME:
                sel = 0
            elif ch == curses.KEY_END:
                sel = len(all_posts) - 1
            elif ch in (10, 13, curses.KEY_ENTER):
                self.edit_post(all_posts[sel])
            elif ch == ord("m"):
                self.metadata_screen(all_posts[sel])
            elif ch == ord("d"):
                p = all_posts[sel]
                if ui.confirm(self.stdscr, "Delete '%s'?" % p.title, "Delete post"):
                    posts.delete_post(p)

    def new_post(self) -> None:
        title = ui.input_dialog(self.stdscr, "New post", "Title:")
        if not title or not title.strip():
            return
        post = posts.new_post(self.site.posts_dir, title.strip())
        self.edit_post(post)

    def edit_post(self, post: posts.Post) -> None:
        Editor(self.stdscr, post.path, display_name=post.title).run()

    def metadata_screen(self, post: posts.Post) -> None:
        post = posts.parse_post(post.path)  # fresh read
        fields = [
            {"key": "title", "label": "Title", "type": "str", "value": post.title},
            {"key": "date", "label": "Date (ISO 8601)", "type": "str",
             "value": post.date.isoformat(timespec="seconds") if post.date else ""},
            {"key": "draft", "label": "Draft", "type": "bool", "value": post.draft},
            {"key": "tags", "label": "Tags (comma-sep)", "type": "str",
             "value": ", ".join(post.tags)},
            {"key": "slug", "label": "Filename slug", "type": "str",
             "value": post.path.stem},
        ]
        res = ui.Form(self.stdscr, "Post metadata — %s" % post.path.name, fields).run()
        if res is None:
            return
        post.title = res["title"].strip() or post.title
        if res["date"].strip():
            try:
                post.date = datetime.fromisoformat(res["date"].strip())
            except ValueError:
                ui.message(self.stdscr, "Error",
                           "Invalid date '%s' — keeping the old one." % res["date"])
        post.draft = res["draft"]
        post.tags = [t.strip() for t in res["tags"].split(",") if t.strip()]
        post.save()
        if res["slug"].strip() and res["slug"].strip() != post.path.stem:
            try:
                posts.rename_post(post, res["slug"].strip())
            except FileExistsError:
                ui.message(self.stdscr, "Error", "A post with that filename already exists.")

    # -- site settings -----------------------------------------------------------

    def site_settings(self) -> None:
        fields = [
            {"key": "title", "label": "Site title", "type": "str",
             "value": self.site.get_config_value("title") or ""},
            {"key": "baseURL", "label": "Base URL", "type": "str",
             "value": self.site.get_config_value("baseURL") or ""},
            {"key": "languageCode", "label": "Language code", "type": "str",
             "value": self.site.get_config_value("languageCode") or "en-us"},
        ]
        res = ui.Form(self.stdscr, "Site settings — %s" % self.site.config_path.name,
                      fields).run()
        if res is None:
            return
        for key, value in res.items():
            self.site.set_config_value(key, value)
        ui.message(self.stdscr, "Saved", "Site settings written to %s"
                   % self.site.config_path.name)

    def edit_site_config(self) -> None:
        Editor(self.stdscr, self.site.config_path).run()

    # -- themes ---------------------------------------------------------------------

    def themes_screen(self) -> None:
        while True:
            themes = self.site.list_themes()
            active = self.site.get_config_value("theme") or "(none)"
            items = ["Install theme from git URL…"]
            items += ["Use theme: %s%s" % (t, "   ← active" if t == active else "")
                      for t in themes]
            items += ["Remove a theme…"] if themes else []
            menu = ui.Menu(self.stdscr, "Themes — active: %s" % active, items)
            choice = menu.run()
            if choice < 0:
                return
            if choice == 0:
                self.install_theme()
            elif choice <= len(themes):
                name = themes[choice - 1]
                self.site.set_config_value("theme", name)
                ui.message(self.stdscr, "Theme set",
                           "theme = '%s' written to %s" % (name, self.site.config_path.name))
            else:
                idx = ui.Menu(self.stdscr, "Remove which theme?", themes).run()
                if idx >= 0 and ui.confirm(
                    self.stdscr, "Delete themes/%s from disk?" % themes[idx], "Remove theme"
                ):
                    self.site.remove_theme(themes[idx])

    def install_theme(self) -> None:
        url = ui.input_dialog(
            self.stdscr, "Install theme",
            "Git URL (from themes.gohugo.io):",
        )
        if not url or not url.strip():
            return
        argv, name = self.site.install_theme_argv(url.strip())
        self.site.themes_dir.mkdir(parents=True, exist_ok=True)

        def clone():
            print("$ %s" % " ".join(argv))
            rc = subprocess.call(argv)
            if rc != 0:
                print("git clone failed (exit %d)" % rc)

        run_external(self.stdscr, clone)
        if (self.site.themes_dir / name).is_dir():
            if ui.confirm(self.stdscr, "Set '%s' as the active theme?" % name, "Theme"):
                self.site.set_config_value("theme", name)

    # -- build / deploy ----------------------------------------------------------------

    def build(self) -> None:
        if not self.site.hugo_available():
            ui.message(
                self.stdscr, "Hugo not found",
                "The 'hugo' binary is not on PATH.\n"
                "Install it (e.g. 'sudo dnf install hugo') to build the site.\n"
                "Your content is still fully Hugo-compatible.",
            )
            return
        argv = self.site.build_argv(include_drafts=self.cfg.deploy["include_drafts"])

        def do_build():
            print("$ %s" % " ".join(argv))
            subprocess.call(argv)

        run_external(self.stdscr, do_build)

    def preview(self) -> None:
        if not self.site.hugo_available():
            ui.message(self.stdscr, "Hugo not found",
                       "The 'hugo' binary is not on PATH — cannot start the preview server.")
            return
        argv = self.site.serve_argv()

        def serve():
            print("$ %s" % " ".join(argv))
            print("(Ctrl-C stops the preview server)\n")
            subprocess.call(argv)

        run_external(self.stdscr, serve)

    def deploy_settings(self) -> None:
        d = self.cfg.deploy
        fields = [
            {"key": "method", "label": "Method", "type": "choice",
             "value": d["method"], "choices": ["rsync", "ftp", "ftps", "github"]},
            {"key": "host", "label": "Host (rsync/ftp)", "type": "str", "value": d["host"]},
            {"key": "port", "label": "Port (0 = default)", "type": "int", "value": d["port"]},
            {"key": "user", "label": "User (rsync/ftp)", "type": "str", "value": d["user"]},
            {"key": "remote_path", "label": "Remote path", "type": "str",
             "value": d["remote_path"]},
            {"key": "ssh_key", "label": "SSH key file (rsync)", "type": "str",
             "value": d["ssh_key"]},
            {"key": "ftp_password", "label": "FTP password (stored!)", "type": "password",
             "value": d["ftp_password"]},
            {"key": "gh_repo", "label": "GH Pages repo (path/URL)", "type": "str",
             "value": d["gh_repo"]},
            {"key": "gh_branch", "label": "GH branch (URL mode)", "type": "str",
             "value": d["gh_branch"]},
            {"key": "gh_cname", "label": "GH custom domain", "type": "str",
             "value": d["gh_cname"]},
            {"key": "delete_remote", "label": "rsync --delete", "type": "bool",
             "value": d["delete_remote"]},
            {"key": "build_first", "label": "Build before deploy", "type": "bool",
             "value": d["build_first"]},
            {"key": "include_drafts", "label": "Include drafts", "type": "bool",
             "value": d["include_drafts"]},
        ]
        res = ui.Form(self.stdscr, "Deployment settings (.myprison.json)", fields).run()
        if res is None:
            return
        d.update(res)
        self.cfg.save()
        if d["ftp_password"]:
            ui.message(
                self.stdscr, "Saved",
                "Settings saved to .myprison.json (mode 600).\n"
                "Note: the FTP password is stored in plain text —\n"
                "keep that file out of version control.",
            )
        else:
            ui.message(self.stdscr, "Saved", "Settings saved to .myprison.json")

    def do_deploy(self) -> None:
        d = self.cfg.deploy
        if d["method"] == "github":
            if not d["gh_repo"]:
                ui.message(self.stdscr, "Not configured",
                           "Set the GitHub Pages repo (path or URL)\n"
                           "in 'Deployment settings' first.")
                return
        elif not d["host"]:
            ui.message(self.stdscr, "Not configured",
                       "Set the host in 'Deployment settings' first.")
            return
        if d["build_first"]:
            if self.site.hugo_available():
                self.build()
            else:
                if not ui.confirm(
                    self.stdscr,
                    "Hugo is not installed; deploy existing public/ anyway?",
                    "Deploy",
                ):
                    return
        pub = self.site.public_dir
        if not pub.is_dir() or not any(pub.iterdir()):
            ui.message(self.stdscr, "Nothing to deploy",
                       "public/ is empty. Build the site first (needs hugo).")
            return

        if d["method"] == "github":

            def gh_publish():
                deploy.github_pages_publish(d, pub)

            run_external(self.stdscr, gh_publish)
        elif d["method"] == "rsync":
            argv = deploy.rsync_argv(d, pub)

            def sync():
                print("$ %s" % " ".join(argv))
                rc = subprocess.call(argv)
                print("\nrsync finished with exit code %d" % rc)

            run_external(self.stdscr, sync)
        else:
            password = d["ftp_password"]
            if not password:
                password = ui.input_dialog(
                    self.stdscr, "Deploy", "FTP password for %s@%s:"
                    % (d["user"], d["host"]), password=True,
                )
                if password is None:
                    return

            def ftp_sync():
                n = deploy.ftp_upload(d, pub, password)
                print("\nUploaded %d files." % n)

            run_external(self.stdscr, ftp_sync)

    def github_actions_setup(self) -> None:
        if not ui.confirm(
            self.stdscr,
            "Write .github/workflows/hugo.yml into the site?",
            "GitHub Pages (Actions)",
        ):
            return
        path = self.site.write_github_workflow()
        lines = [
            "Wrote %s" % path.relative_to(self.site.root),
            "",
            "GitHub now builds the site itself on every push:",
            "1. Make the site a git repo and push it to GitHub.",
            "2. Repo Settings -> Pages -> Source: 'GitHub Actions'.",
            "3. Push to main; the site appears at your Pages URL.",
        ]
        nested = self.site.vendored_theme_gits()
        if nested:
            lines += [
                "",
                "Note: these themes contain their own .git and would NOT",
                "be pushed with the site: %s." % ", ".join(nested),
                "Either add them as git submodules, or delete the .git",
                "directory inside the theme to commit it as plain files.",
            ]
        ui.message(self.stdscr, "GitHub Actions workflow created", "\n".join(lines))

    # -- main menu -------------------------------------------------------------------------

    def run(self) -> None:
        entries = [
            ("Posts — list / edit / delete", self.posts_screen),
            ("New post", self.new_post),
            ("Build site (hugo)", self.build),
            ("Preview site (hugo server)", self.preview),
            ("Deploy (rsync / FTP / GitHub Pages)", self.do_deploy),
            ("Deployment settings", self.deploy_settings),
            ("GitHub Pages via Actions (CI setup)", self.github_actions_setup),
            ("Site settings (title, URL)", self.site_settings),
            ("Themes", self.themes_screen),
            ("Edit Hugo config file", self.edit_site_config),
            ("Quit", None),
        ]
        menu = ui.Menu(
            self.stdscr,
            "myprison %s — %s" % (__version__, self.site.root),
            [label for label, _ in entries],
        )
        while True:
            choice = menu.run()
            if choice < 0 or entries[choice][1] is None:
                return
            entries[choice][1]()


def bootstrap(stdscr, start_dir: Path) -> Site | None:
    """Return an existing or freshly created Site, or None to quit."""
    site = Site(start_dir)
    if site.exists():
        return site
    while True:
        choice = ui.Menu(
            stdscr,
            "myprison — no Hugo site found in %s" % site.root,
            [
                "Create a new site here (%s)" % site.root,
                "Open a site at another path…",
                "Quit",
            ],
        ).run()
        if choice in (-1, 2):
            return None
        if choice == 0:
            title = ui.input_dialog(stdscr, "New site", "Site title:", "My Blog")
            if title is None:
                continue
            base = ui.input_dialog(stdscr, "New site", "Base URL:", "https://example.org/")
            if base is None:
                continue
            site.create(title.strip() or "My Blog", base.strip() or "https://example.org/")
            ui.message(stdscr, "Site created",
                       "Scaffolded a Hugo site in %s\n"
                       "Next: install a theme from themes.gohugo.io\n"
                       "via the Themes menu." % site.root)
            return site
        if choice == 1:
            path = ui.input_dialog(stdscr, "Open site", "Path:", str(site.root))
            if path is None:
                continue
            candidate = Site(Path(path))
            if candidate.exists():
                return candidate
            site = candidate  # offer creation at the new path


def curses_main(stdscr, start_dir: Path) -> None:
    curses.raw()  # receive ^S / ^X etc. directly
    curses.curs_set(0)
    if hasattr(curses, "set_escdelay"):
        curses.set_escdelay(25)
    stdscr.keypad(True)
    site = bootstrap(stdscr, start_dir)
    if site is None:
        return
    App(stdscr, site).run()
