# Installing myprison

## Requirements

| What | Needed for | Notes |
|------|------------|-------|
| Python **3.9+** | everything | standard library only — no pip dependencies |
| a terminal with curses | everything | any normal Linux/Unix terminal (UTF-8 recommended) |
| [`hugo`](https://gohugo.io/installation/) | building / previewing the site | content management works without it |
| `git` | installing themes | themes are cloned from their git URLs |
| `rsync` + `ssh` | rsync deployment | recommended deployment method |
| — | FTP/FTPS deployment | pure Python (`ftplib`), nothing extra needed |
| `git` | GitHub Pages deployment | publishing pushes the built site with git |
| [`gh`](https://cli.github.com/) or a `GITHUB_TOKEN` | GitHub Pages extras | optional: lets myprison configure the repo's Pages source and watch private-repo Actions runs; public-repo status checks work without it |

## Option 1 — run from the repository (no installation)

```bash
git clone https://github.com/salvogendut/myprison.git
cd myprison
python3 -m myprison ~/blog
```

## Option 2 — install with pip

```bash
git clone https://github.com/salvogendut/myprison.git
cd myprison
pip install .          # or: pip install --user .
```

This installs a `myprison` command:

```bash
myprison ~/blog
```

For an isolated install, use [pipx](https://pipx.pypa.io/):

```bash
pipx install git+https://github.com/salvogendut/myprison.git
```

## Installing Hugo

`myprison` produces a standard Hugo site; the `hugo` binary does the actual
HTML generation. Install it from your distribution:

```bash
# Fedora
sudo dnf install hugo

# Debian / Ubuntu
sudo apt install hugo

# Arch
sudo pacman -S hugo

# macOS
brew install hugo
```

or download a release binary from
[github.com/gohugoio/hugo/releases](https://github.com/gohugoio/hugo/releases)
and put it on your `PATH`. Any reasonably recent Hugo works; the *extended*
edition is required by some themes (it is the default download).

Without Hugo installed you can still create and edit posts, manage themes,
and configure deployment — only **Build site** and **Preview site** need the
binary.

## Upgrading

For a local directory install, pip always rebuilds and reinstalls, so
upgrading is just:

```bash
cd myprison && git pull
pip install --user .        # same flavor you installed with
```

Or install **editable** once and never reinstall again — the installed
command then always runs the code currently in the repo:

```bash
pip install --user -e .
```

With pipx: `pipx reinstall myprison` (or `pipx install --force git+...`).

## First run

```bash
myprison ~/blog        # or: python3 -m myprison ~/blog
```

If `~/blog` does not contain a Hugo site yet, `myprison` offers to scaffold
one: `hugo.toml`, `content/posts/`, `themes/`, `static/`, `layouts/`, and
`archetypes/default.md`. Existing Hugo sites (with `hugo.toml` or
`config.toml`) are opened as-is.

See [USAGE.md](USAGE.md) for what to do next.
