# Using myprison

Start it with the site directory as argument (defaults to the current
directory):

```bash
myprison ~/blog            # or: python3 -m myprison ~/blog
```

General keys, everywhere: **↑/↓** (or `j`/`k`) move, **Enter** selects,
**q** or **Esc** goes back, digits **1–9** jump to a menu entry.

## 1. Creating a site

If the directory has no Hugo site, a bootstrap menu offers to create one.
You are asked for a **site title** and a **base URL** (the public address of
your blog, e.g. `https://blog.example.org/`). That scaffolds:

```
blog/
├── hugo.toml            site configuration
├── archetypes/default.md
├── content/posts/       your posts live here
├── layouts/
├── static/              images, files copied verbatim
└── themes/              installed themes
```

You can change the title/URL later under **Site settings**, or edit
`hugo.toml` directly via **Edit Hugo config file**.

## 2. Installing a theme

A fresh Hugo site renders nothing without a theme.

1. Browse [themes.gohugo.io](https://themes.gohugo.io/) and pick one.
2. On the theme's page, find its git repository URL
   (e.g. `https://github.com/theNewDynamic/gohugo-theme-ananke.git`).
3. In `myprison`: **Themes → Install theme from git URL…**, paste the URL.
4. Confirm setting it as the active theme (writes `theme = '…'` to
   `hugo.toml`).

The Themes menu also switches between installed themes and removes them.
Some themes need extra configuration — use **Edit Hugo config file** and
follow the theme's README.

## 3. Writing posts

**New post** asks for a title and creates
`content/posts/<slug>.md` — e.g. *"Hello, World!"* becomes
`hello-world.md` — with standard Hugo front matter:

```markdown
---
title: "Hello, World!"
date: 2026-07-06T18:30:00+02:00
draft: true
---
```

The built-in editor then opens with the cursor below the front matter.
Write Markdown; Hugo renders it.

### The editor

| Key | Action |
|-----|--------|
| arrows, Home, End, PgUp, PgDn | move around |
| any printable key | insert text (UTF-8 aware) |
| Enter / Backspace / Delete | edit |
| Tab | insert 4 spaces |
| **Ctrl-S** | save |
| **Ctrl-K** | delete current line |
| **Ctrl-X** | exit (asks to save if modified) |

### The posts list

**Posts** shows every post, **newest first**, with date and a `DRAFT` flag.

| Key | Action |
|-----|--------|
| Enter | edit the post in the editor |
| `n` | new post |
| `m` | edit metadata: title, date, draft flag, tags, filename slug |
| `d` | delete (asks for confirmation) |
| `q` / Esc | back to the main menu |

Notes:

- New posts start as **drafts** (`draft: true`). Hugo skips drafts in normal
  builds — flip the flag in the metadata form (`m`) when ready to publish,
  or enable *Include drafts* in the deployment settings for preview builds.
- Posts created with `hugo new` (TOML `+++` front matter) are read fine, and
  front-matter keys `myprison` doesn't know about are preserved.
- Changing the **date** in the metadata form changes the post's position in
  the chronological list and on the site.

## 4. Building and previewing

- **Build site** runs `hugo`, writing the finished website to `public/`.
- **Preview site** runs `hugo server --buildDrafts` — open the printed URL
  (usually `http://localhost:1313/`) in a browser; **Ctrl-C** returns to the
  menu.

Both require the `hugo` binary ([INSTALL.md](INSTALL.md#installing-hugo)).

## 5. Deploying to your web server

### Configure once: Deployment settings

| Field | Meaning |
|-------|---------|
| Method | `rsync` (over SSH, recommended), `ftp`, or `ftps` (FTP with TLS) |
| Host | server hostname or IP |
| Port | `0` = default (SSH 22 / FTP 21) |
| User | remote username |
| Remote path | directory served by your web server, e.g. `/var/www/blog` |
| SSH key file | optional identity file for rsync (else your ssh-agent/default keys) |
| FTP password | optional; leave empty to be prompted at each deploy |
| rsync --delete | remove remote files that no longer exist locally |
| Build before deploy | run `hugo` automatically first |
| Include drafts | pass `--buildDrafts` to that build |

Settings are stored in `.myprison.json` in the site root, created with mode
600 and covered by the repository's `.gitignore`. If you store the FTP
password, remember it is in plain text — prefer rsync/SSH with keys, or
leave the password empty and type it when deploying.

### Deploy

**Deploy to web server** builds (if configured), then syncs `public/`:

- **rsync**: equivalent to
  `rsync -avz --delete -e "ssh -p PORT -i KEY" public/ user@host:/remote/path`.
  Incremental — only changed files are transferred. Authentication is your
  normal SSH setup (keys/agent); set up key-based login with
  `ssh-copy-id user@host` first.
- **FTP/FTPS**: recursive upload of `public/` via Python's `ftplib`,
  creating remote directories as needed. Choose `ftps` (explicit TLS)
  whenever the server supports it; plain `ftp` sends credentials
  unencrypted. FTP deploys never delete remote files.

The sync runs outside the curses UI so you see the full rsync/FTP output,
then returns to the menu on Enter.

## 6. Interoperating with plain Hugo

The site is a normal Hugo site at all times. You can freely mix tools:

```bash
cd ~/blog
hugo new posts/from-the-cli.md    # appears in myprison's post list
hugo server -D                    # preview outside myprison
git init && git add . && git commit -m "my blog"   # version it
```

`myprison` only manages `content/posts/*.md`, top-level values in
`hugo.toml`, `themes/`, and its own `.myprison.json`. Everything else —
pages outside `posts/`, custom layouts, shortcodes, `static/` assets — you
manage as with any Hugo site.
