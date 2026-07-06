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
| Method | `rsync` (over SSH, recommended), `ftp`, `ftps` (FTP with TLS), or `github` (GitHub Pages) |
| Host | server hostname or IP (rsync/ftp) |
| Port | `0` = default (SSH 22 / FTP 21) |
| User | remote username (rsync/ftp) |
| Remote path | directory served by your web server, e.g. `/var/www/blog` |
| SSH key file | optional identity file for rsync (else your ssh-agent/default keys) |
| FTP password | optional; leave empty to be prompted at each deploy |
| GH Pages repo | `github` method: local repo path (e.g. `~/Dev/mypages`) or remote git URL |
| GH branch | `github` method with a remote URL: branch to force-push (default `gh-pages`) |
| GH custom domain | optional; written as a `CNAME` file into the published site |
| GH watch Actions run | after publishing, poll GitHub Actions and report whether the Pages deployment succeeded |
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

## 6. Publishing on GitHub Pages

There are two independent routes; pick one.

### Route A — push the built site with git (method `github`)

`myprison` builds locally and publishes `public/` to a GitHub repository
that serves GitHub Pages. Set **Method** to `github` in the deployment
settings and fill **GH Pages repo** with either:

- **a local clone** (e.g. `~/Dev/mypages`): the built site replaces the
  repo's contents (housekeeping files like `README.md`, `LICENSE`,
  `.gitignore`, `.github/` are kept), is committed on the current branch,
  and pushed to `origin` with your normal git credentials. If nothing
  changed since the last publish, nothing is pushed.
- **a remote URL** (e.g. `git@github.com:you/blog-pages.git`): the built
  site is force-pushed to the **GH branch** (default `gh-pages`) from a
  throwaway repository.

A `.nojekyll` file is always included (so Hugo output isn't mangled by
Jekyll), plus a `CNAME` file if you set a custom domain.

Then, once, the repo's Pages source must be set to **“Deploy from a
branch”** pointing at the branch you publish to. `myprison` can do this for
you: **GitHub Pages: deploy from a branch (setup)** enables Pages on the
repo and points it at the right branch through the GitHub API, then offers
to set your site's `baseURL` to the resulting Pages URL. It authenticates
with `GITHUB_TOKEN`/`GH_TOKEN` or, if neither is set, your `gh` CLI login
(`gh auth login`); with no credentials it prints the manual steps
(**repo Settings → Pages → Source: “Deploy from a branch”**, branch,
`/ (root)`).

Mind the `baseURL` in your site settings — for a project repository it is
`https://<user>.github.io/<repo>/`; for a `<user>.github.io` repository it
is `https://<user>.github.io/`.

After the push, if **GH watch Actions run** is enabled (default), `myprison`
polls the GitHub API for the workflow run triggered by that exact commit —
the automatic *“pages build and deployment”* run for branch-source Pages,
or your `hugo.yml` run for Actions-source — and reports its conclusion, so
you know the site is actually live before leaving the deploy screen.
`Ctrl-C` stops watching (the deployment on GitHub continues regardless).
Public repositories need no authentication; for private ones (or to avoid
API rate limits) export `GITHUB_TOKEN` (or `GH_TOKEN`) before starting
`myprison`.

### Route B — let GitHub build it (Actions workflow)

**GitHub Pages via Actions (CI setup)** writes
`.github/workflows/hugo.yml` (the official Hugo starter workflow) into the
*site source* directory. Version the site with git, push it to GitHub, and
set **repo Settings → Pages → Source: “GitHub Actions”**. From then on
every push to `main` builds and deploys the site on GitHub's runners — you
don't need Hugo installed at all, and `baseURL` is set automatically by the
workflow.

Caveat: themes installed by `myprison` are git clones and contain their own
`.git`, so a plain `git push` of the site would *not* include them. Either
register the theme as a proper submodule
(`git submodule add <theme-url> themes/<name>` — the workflow checks out
submodules), or delete `themes/<name>/.git` to commit the theme as plain
files. `myprison` warns about affected themes when it writes the workflow.

## 7. Interoperating with plain Hugo

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
