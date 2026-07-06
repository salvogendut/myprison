"""Post model and CRUD on content/posts/*.md with Hugo front matter.

Front matter is written as YAML (--- delimited), which Hugo accepts natively.
Reading supports both YAML (---) and TOML (+++) simple key/value front matter,
so posts created with `hugo new` also work. Unknown keys are preserved.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def slugify(title: str) -> str:
    s = unicodedata.normalize("NFKD", title)
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "post"


def _parse_date(raw: str) -> datetime | None:
    raw = raw.strip().strip("'\"")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    for candidate in (raw, raw.replace(" ", "T", 1)):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _parse_tags(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        return [t.strip().strip("'\"") for t in inner.split(",") if t.strip()]
    return [raw.strip("'\"")] if raw else []


@dataclass
class Post:
    path: Path
    title: str = ""
    date: datetime | None = None
    draft: bool = False
    tags: list[str] = field(default_factory=list)
    extra: dict[str, str] = field(default_factory=dict)  # unknown front matter, raw values
    body: str = ""

    @property
    def date_str(self) -> str:
        if self.date is None:
            return "(no date)"
        return self.date.strftime("%Y-%m-%d %H:%M")

    def sort_key(self):
        d = self.date or datetime.fromtimestamp(0).astimezone()
        if d.tzinfo is None:
            d = d.astimezone()
        return d

    # -- serialization ------------------------------------------------------

    def front_matter(self) -> str:
        lines = ["---"]
        lines.append('title: "%s"' % self.title.replace("\\", "\\\\").replace('"', '\\"'))
        if self.date is not None:
            lines.append("date: %s" % self.date.isoformat(timespec="seconds"))
        lines.append("draft: %s" % ("true" if self.draft else "false"))
        if self.tags:
            lines.append("tags: [%s]" % ", ".join('"%s"' % t for t in self.tags))
        for key, raw in self.extra.items():
            lines.append("%s: %s" % (key, raw))
        lines.append("---")
        return "\n".join(lines)

    def full_text(self) -> str:
        body = self.body
        if body and not body.startswith("\n"):
            body = "\n" + body
        return self.front_matter() + body + ("" if body.endswith("\n") else "\n")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.full_text(), encoding="utf-8")


_KNOWN = {"title", "date", "draft", "tags"}


def parse_post(path: Path) -> Post:
    text = path.read_text(encoding="utf-8", errors="replace")
    post = Post(path=path)
    lines = text.splitlines(keepends=True)
    delim = None
    if lines and lines[0].strip() in ("---", "+++"):
        delim = lines[0].strip()
    if delim is None:
        post.body = text
        post.title = path.stem
        return post

    sep = ":" if delim == "---" else "="
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == delim:
            end = i
            break
    if end is None:
        post.body = text
        post.title = path.stem
        return post

    for line in lines[1:end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or sep not in stripped:
            continue
        key, raw = stripped.split(sep, 1)
        key = key.strip()
        raw = raw.strip()
        lkey = key.lower()
        if lkey == "title":
            post.title = raw.strip("'\"")
        elif lkey == "date":
            post.date = _parse_date(raw)
        elif lkey == "draft":
            post.draft = raw.strip().lower() in ("true", "yes", "1")
        elif lkey == "tags":
            post.tags = _parse_tags(raw)
        elif key not in _KNOWN:
            post.extra[key] = raw
    post.body = "".join(lines[end + 1:])
    if not post.title:
        post.title = path.stem
    return post


def list_posts(posts_dir: Path) -> list[Post]:
    """All posts, newest first (chronological ordering)."""
    posts: list[Post] = []
    if posts_dir.is_dir():
        for p in sorted(posts_dir.rglob("*.md")):
            if p.name.startswith("_"):
                continue
            try:
                posts.append(parse_post(p))
            except OSError:
                continue
    posts.sort(key=lambda p: p.sort_key(), reverse=True)
    return posts


def new_post(posts_dir: Path, title: str) -> Post:
    slug = slugify(title)
    path = posts_dir / ("%s.md" % slug)
    n = 2
    while path.exists():
        path = posts_dir / ("%s-%d.md" % (slug, n))
        n += 1
    post = Post(
        path=path,
        title=title,
        date=datetime.now().astimezone().replace(microsecond=0),
        draft=True,
        body="\n",
    )
    post.save()
    return post


def delete_post(post: Post) -> None:
    post.path.unlink(missing_ok=True)


def rename_post(post: Post, new_slug: str) -> Post:
    new_slug = slugify(new_slug)
    new_path = post.path.with_name("%s.md" % new_slug)
    if new_path != post.path:
        if new_path.exists():
            raise FileExistsError(str(new_path))
        post.path.rename(new_path)
        post.path = new_path
    return post
