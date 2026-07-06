# myprison

**Write your blog in the terminal. Publish it anywhere.**

`myprison` is a static-files blogging platform for the Linux/Unix shell. It
gives you a friendly curses (text-mode) interface — menus, forms, and a
built-in text editor — on top of a completely standard
[Hugo](https://gohugo.io/) site. You write posts in the terminal; Hugo turns
them into a fast static website; `myprison` uploads the result to your web
server over SSH or FTP. No database, no web admin panel, no JavaScript
toolchain — just Markdown files you own, managed from a keyboard.

```
┌──────────────────────────────────────────────────────────┐
│ myprison 0.1.0 — /home/you/blog                          │
│                                                          │
│  ❯ Posts — list / edit / delete                          │
│    New post                                              │
│    Build site (hugo)                                     │
│    Preview site (hugo server)                            │
│    Deploy to web server                                  │
│    Deployment settings (SSH/FTP)                         │
│    Site settings (title, URL)                            │
│    Themes                                                │
│    Edit Hugo config file                                 │
│    Quit                                                  │
│                                                          │
│ ↑/↓ move   Enter select   q/Esc back                     │
└──────────────────────────────────────────────────────────┘
```

## Why myprison?

- **Terminal-native.** Everything happens in one curses UI: create, edit,
  and delete posts, manage themes, configure deployment, publish. Works over
  SSH, in a tmux pane, on a Raspberry Pi.
- **It's just Hugo.** The site tree, config, and post files are plain Hugo.
  Any theme from [themes.gohugo.io](https://themes.gohugo.io/) works. Stop
  using `myprison` tomorrow and your site still builds with the `hugo` CLI.
- **Zero dependencies.** Pure Python 3 standard library. No pip packages,
  no node_modules.
- **Built-in editor.** A small nano-style editor for writing posts, with
  Hugo front matter handled for you. Posts are listed chronologically,
  newest first.
- **Publish from the same menu.** Sync the built site to your server with
  rsync over SSH (incremental, recommended) or FTP/FTPS — credentials and
  options configured in-app.

## Quick start

```bash
git clone https://github.com/salvogendut/myprison.git
cd myprison
python3 -m myprison ~/blog     # offers to scaffold a new Hugo site there
```

Then, from the menus: install a theme (paste any git URL from
themes.gohugo.io), write your first post, build, and deploy.

## Documentation

| Document | Contents |
|----------|----------|
| [INSTALL.md](INSTALL.md) | Requirements, installation methods, installing Hugo |
| [USAGE.md](USAGE.md) | Full guide: menus, the editor, posts, themes, deployment |

## License

MIT
