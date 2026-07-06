# myprison

A static-files blogging platform for the Linux/Unix shell. `myprison` is a
curses (text-mode) front end that manages a standard [Hugo](https://gohugo.io/)
site tree: it creates and edits posts with a built-in text editor, keeps them
ordered chronologically, installs themes from
[themes.gohugo.io](https://themes.gohugo.io/), builds the site with `hugo`,
and syncs the result to your web server over SSH (rsync) or FTP/FTPS.

Everything it produces is plain Hugo — you can stop using `myprison` at any
time and keep working on the same site with the `hugo` CLI.

## Requirements

- Python 3.9+ (standard library only — no pip dependencies)
- [`hugo`](https://gohugo.io/installation/) on PATH, to build/preview the site
  (content management works without it)
- `rsync` + `ssh` for rsync deployment, `git` for theme installation

## Run

```bash
python3 -m myprison [SITE_DIR]      # default: current directory
```

or install it:

```bash
pip install .
myprison ~/blog
```

If the directory does not contain a Hugo site yet, `myprison` offers to
scaffold one (`hugo.toml`, `content/posts/`, `themes/`, `static/`, …).

## Main menu

| Entry | What it does |
|-------|--------------|
| **Posts** | Chronological list (newest first). `Enter` edit, `n` new, `m` metadata (title/date/draft/tags/slug), `d` delete. |
| **New post** | Asks for a title, creates `content/posts/<slug>.md` with YAML front matter (`title`, `date`, `draft: true`), opens the editor. |
| **Build site** | Runs `hugo` (optionally with `--buildDrafts`). |
| **Preview site** | Runs `hugo server --buildDrafts`; Ctrl-C returns to the menu. |
| **Deploy to web server** | Optionally builds, then syncs `public/` with rsync-over-SSH or uploads it via FTP/FTPS. |
| **Deployment settings** | Method (rsync/ftp/ftps), host, port, user, remote path, SSH key, FTP password, `--delete`, build-before-deploy. Stored in `.myprison.json` (mode 600, gitignored). |
| **Site settings** | Edits `title`, `baseURL`, `languageCode` in `hugo.toml`. |
| **Themes** | Clone any Hugo theme by its git URL into `themes/`, activate it (`theme = '…'`), or remove it. |
| **Edit Hugo config file** | Opens `hugo.toml` in the built-in editor for anything the forms don't cover. |

## Built-in editor

A small nano-style editor used for posts and the config file:

- Arrows / Home / End / PgUp / PgDn to move, type to insert (UTF-8 aware)
- `Ctrl-S` save, `Ctrl-X` exit (asks to save if modified), `Ctrl-K` delete line
- Tab inserts 4 spaces

## Deployment notes

- **rsync (recommended)**: uses your SSH agent/keys; equivalent to
  `rsync -avz --delete -e "ssh -p PORT -i KEY" public/ user@host:remote_path`.
- **FTP/FTPS**: pure-Python (`ftplib`) recursive upload; remote directories are
  created as needed. The password can be stored in `.myprison.json` or left
  empty to be prompted at deploy time. FTPS (explicit TLS) is preferred over
  plain FTP.

## Post format

Posts are Markdown files with YAML front matter, exactly as Hugo expects:

```markdown
---
title: "Hello world"
date: 2026-07-06T18:30:00+02:00
draft: true
tags: ["meta"]
---

First post!
```

Posts created with `hugo new` (TOML `+++` front matter) are read fine too;
unknown front-matter keys are preserved when editing metadata.
