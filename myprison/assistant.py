"""Resident AI assistant for myprison."""

from __future__ import annotations

import getpass
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from . import deploy, posts
from .ai_providers import ProviderError, ToolCall, load_provider, provider_names
from .config import ToolConfig
from .hugosite import Site

READ_ONLY_TOOLS = {
    "list_posts", "read_post", "get_site_config", "list_themes", "git_status",
}
DESTRUCTIVE_TOOLS = {"delete_post", "remove_theme", "deploy_site", "publish_post"}


class AssistantError(Exception):
    """Expected user-facing assistant failure."""


def run_ai_assistant(site: Site, cfg: ToolConfig) -> None:
    """Run the terminal prompt loop."""
    settings = cfg.ai
    provider_name = settings.get("provider") or "chatgpt"
    try:
        provider = load_provider(provider_name)
    except ProviderError as exc:
        print("ERROR: %s" % exc)
        print("Available providers: %s" % ", ".join(provider_names()))
        return

    provider_settings = _provider_settings(settings, provider_name)
    key = provider.api_key(provider_settings)
    if not key:
        key = provider.authenticate(provider_settings, cfg)
    if not key:
        print("AI assistance is not configured.")
        return

    model = provider_settings.get("model") or provider.default_model
    print("myprison AI assistance")
    print("Provider: %s" % provider.display_name)
    print("Model: %s" % model)
    print("Type /help for commands, /quit to return to myprison.\n")

    messages: list[dict[str, Any]] = []
    while True:
        try:
            prompt = input("ai> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not prompt:
            continue
        if prompt in ("/q", "/quit", "quit", "exit"):
            return
        if prompt == "/help":
            _print_help(provider_name)
            continue
        if prompt.startswith("/model "):
            model = prompt.split(None, 1)[1].strip()
            provider_settings["model"] = model
            cfg.save()
            print("Model set to %s" % model)
            continue
        if prompt.startswith("/provider "):
            new_name = prompt.split(None, 1)[1].strip()
            old_provider = provider
            old_provider_name = provider_name
            old_provider_settings = provider_settings
            old_key = key
            old_model = model
            try:
                provider = load_provider(new_name)
            except ProviderError as exc:
                print("ERROR: %s" % exc)
                continue
            provider_name = new_name
            settings["provider"] = new_name
            provider_settings = _provider_settings(settings, provider_name)
            model = provider_settings.get("model") or provider.default_model
            key = (
                provider.api_key(provider_settings)
                or provider.authenticate(provider_settings, cfg)
            )
            if not key:
                provider = old_provider
                provider_name = old_provider_name
                provider_settings = old_provider_settings
                key = old_key
                model = old_model
                print("Provider was not changed; authentication was cancelled.")
                continue
            cfg.save()
            print("Provider set to %s" % provider.display_name)
            continue
        if prompt == "/auth":
            new_key = provider.authenticate(provider_settings, cfg, force=True)
            if new_key:
                key = new_key
            continue
        if prompt == "/clear":
            messages = []
            print("Conversation cleared.")
            continue

        messages.append({"role": "user", "content": prompt})
        try:
            reply = provider.run_turn(
                provider_settings,
                key,
                model,
                _instructions(),
                messages,
                _tools(),
                lambda call: _handle_tool_call(site, cfg, call),
            )
        except (AssistantError, ProviderError) as exc:
            print("ERROR: %s" % exc)
            continue
        except KeyboardInterrupt:
            print("\nInterrupted.")
            continue
        if reply:
            messages.append({"role": "assistant", "content": reply})
            print(reply)


def _print_help(provider_name: str) -> None:
    print(
        "Commands:\n"
        "  /help                show this help\n"
        "  /provider NAME       switch AI provider (%s)\n"
        "  /model MODEL         set the provider model for future turns\n"
        "  /auth                enter or replace provider credentials\n"
        "  /clear               clear conversation context\n"
        "  /quit                return to myprison\n\n"
        "Current provider: %s\n\n"
        "Ask for blog actions in plain language, for example:\n"
        "  list my posts\n"
        "  make the latest post a draft\n"
        "  create a post titled \"Hello\" with a short introduction and publish it\n"
        "  write a French post about cold-weather sailing with relevant links and publish it\n"
        "  build and deploy the site\n"
        % (", ".join(provider_names()), provider_name)
    )


def _provider_settings(settings: dict, provider_name: str) -> dict:
    providers = settings.setdefault("providers", {})
    return providers.setdefault(provider_name, {})


def _instructions() -> str:
    return (
        "You are the resident AI assistant inside myprison, a terminal Hugo blog manager. "
        "Use tools to inspect and change the site instead of guessing. "
        "For requests like 'write/create a post ... and publish it', create or update the "
        "post body yourself, use provider web search when available for relevant links, "
        "include any requested translation and Markdown links, call git_status, then call "
        "publish_post for that post. If the site is a git repository, default to committing "
        "and pushing source changes when publishing a newly created or edited post. "
        "Summarize actions briefly. For destructive or publishing actions, explain what you "
        "are about to do before calling the tool; the host application will ask for confirmation. "
        "Do not invent files or deployment results that tools did not report."
    )


def _tools() -> list[dict[str, Any]]:
    obj = "object"
    empty = {
        "type": obj,
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }
    return [
        {
            "name": "list_posts",
            "description": "List Hugo posts, newest first.",
            "parameters": empty,
        },
        {
            "name": "read_post",
            "description": "Read a post by filename slug, title substring, or 'latest'.",
            "parameters": {
                "type": obj,
                "properties": {"post": {"type": "string"}},
                "required": ["post"],
                "additionalProperties": False,
            },
        },
        {
            "name": "create_post",
            "description": "Create a new Hugo post.",
            "parameters": {
                "type": obj,
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "draft": {"type": "boolean"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "body", "draft", "tags"],
                "additionalProperties": False,
            },
        },
        {
            "name": "update_post",
            "description": "Update post metadata and/or replace its Markdown body. Use empty strings/arrays for fields that should not change.",
            "parameters": {
                "type": obj,
                "properties": {
                    "post": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "draft": {"type": "boolean"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "date": {"type": "string"},
                    "slug": {"type": "string"},
                },
                "required": ["post", "title", "body", "draft", "tags", "date", "slug"],
                "additionalProperties": False,
            },
        },
        {
            "name": "delete_post",
            "description": "Delete a post by filename slug, title substring, or 'latest'.",
            "parameters": {
                "type": obj,
                "properties": {"post": {"type": "string"}},
                "required": ["post"],
                "additionalProperties": False,
            },
        },
        {
            "name": "get_site_config",
            "description": "Read key site and deployment configuration.",
            "parameters": empty,
        },
        {
            "name": "set_site_config",
            "description": "Set a top-level Hugo config string value.",
            "parameters": {
                "type": obj,
                "properties": {"key": {"type": "string"}, "value": {"type": "string"}},
                "required": ["key", "value"],
                "additionalProperties": False,
            },
        },
        {
            "name": "list_themes",
            "description": "List installed Hugo themes and the active theme.",
            "parameters": empty,
        },
        {
            "name": "set_theme",
            "description": "Set the active Hugo theme by installed theme name.",
            "parameters": {
                "type": obj,
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
        {
            "name": "install_theme",
            "description": "Install a Hugo theme from a git URL.",
            "parameters": {
                "type": obj,
                "properties": {"url": {"type": "string"}, "set_active": {"type": "boolean"}},
                "required": ["url", "set_active"],
                "additionalProperties": False,
            },
        },
        {
            "name": "remove_theme",
            "description": "Remove an installed Hugo theme.",
            "parameters": {
                "type": obj,
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
        {
            "name": "build_site",
            "description": "Build the Hugo site.",
            "parameters": {
                "type": obj,
                "properties": {"include_drafts": {"type": "boolean"}},
                "required": ["include_drafts"],
                "additionalProperties": False,
            },
        },
        {
            "name": "deploy_site",
            "description": "Deploy the built site using current deployment settings.",
            "parameters": empty,
        },
        {
            "name": "publish_post",
            "description": "Publish a post: mark it non-draft, build the site, optionally commit/push source changes, and deploy using current settings.",
            "parameters": {
                "type": obj,
                "properties": {
                    "post": {"type": "string"},
                    "commit_source": {"type": "boolean"},
                    "push_source": {"type": "boolean"},
                    "commit_message": {"type": "string"},
                },
                "required": ["post", "commit_source", "push_source", "commit_message"],
                "additionalProperties": False,
            },
        },
        {
            "name": "git_status",
            "description": "Read git branch and short status for the current Hugo site, if it is a git repository.",
            "parameters": empty,
        },
    ]


def _handle_tool_call(site: Site, cfg: ToolConfig, call: ToolCall) -> dict:
    if call.name not in READ_ONLY_TOOLS and not _confirm_tool(call.name, call.arguments):
        return {"ok": False, "cancelled": True}
    try:
        return _run_tool(site, cfg, call.name, call.arguments)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _confirm_tool(name: str, args: dict) -> bool:
    label = "destructive" if name in DESTRUCTIVE_TOOLS else "mutating"
    print("\nAI requested %s action: %s" % (label, name))
    print(json.dumps(args, indent=2, ensure_ascii=False))
    answer = input("Allow this action? [y/N] ").strip().lower()
    return answer == "y"


def _run_tool(site: Site, cfg: ToolConfig, name: str, args: dict) -> dict:
    if name == "list_posts":
        return {"ok": True, "posts": [_post_summary(p, site) for p in posts.list_posts(site.posts_dir)]}
    if name == "read_post":
        post = _find_post(site, args["post"])
        return {"ok": True, "post": _post_detail(post, site)}
    if name == "create_post":
        post = posts.new_post(site.posts_dir, args["title"])
        post.body = args.get("body") or "\n"
        post.draft = bool(args.get("draft"))
        post.tags = [str(t) for t in args.get("tags") or []]
        post.save()
        return {"ok": True, "post": _post_summary(post, site)}
    if name == "update_post":
        post = _find_post(site, args["post"])
        if args.get("title"):
            post.title = args["title"]
        if args.get("body"):
            post.body = args["body"]
        if isinstance(args.get("draft"), bool):
            post.draft = args["draft"]
        if args.get("tags"):
            post.tags = [str(t) for t in args["tags"]]
        if args.get("date"):
            post.date = datetime.fromisoformat(args["date"])
        post.save()
        if args.get("slug"):
            post = posts.rename_post(post, args["slug"])
        return {"ok": True, "post": _post_summary(post, site)}
    if name == "delete_post":
        post = _find_post(site, args["post"])
        summary = _post_summary(post, site)
        posts.delete_post(post)
        return {"ok": True, "deleted": summary}
    if name == "get_site_config":
        return {
            "ok": True,
            "hugo": {
                key: site.get_config_value(key)
                for key in ("baseURL", "title", "languageCode", "locale", "theme")
            },
            "deploy": _safe_deploy_config(cfg.deploy),
        }
    if name == "set_site_config":
        site.set_config_value(args["key"], args["value"])
        return {"ok": True, "key": args["key"], "value": args["value"]}
    if name == "list_themes":
        return {
            "ok": True,
            "active": site.get_config_value("theme") or "",
            "themes": site.list_themes(),
        }
    if name == "set_theme":
        if args["name"] not in site.list_themes():
            raise AssistantError("theme is not installed: %s" % args["name"])
        site.set_config_value("theme", args["name"])
        return {"ok": True, "active": args["name"]}
    if name == "install_theme":
        argv, theme_name = site.install_theme_argv(args["url"])
        site.themes_dir.mkdir(parents=True, exist_ok=True)
        rc, out = _run_subprocess(argv, site.root, timeout=300)
        if rc != 0:
            return {"ok": False, "exit_code": rc, "output": out[-4000:]}
        if args.get("set_active"):
            site.set_config_value("theme", theme_name)
        return {"ok": True, "theme": theme_name, "output": out[-4000:]}
    if name == "remove_theme":
        site.remove_theme(args["name"])
        return {"ok": True, "removed": args["name"]}
    if name == "build_site":
        include_drafts = bool(args.get("include_drafts"))
        if not site.hugo_available():
            raise AssistantError("hugo is not on PATH")
        rc, out = _run_subprocess(site.build_argv(include_drafts), site.root, timeout=300)
        return {"ok": rc == 0, "exit_code": rc, "output": out[-6000:]}
    if name == "deploy_site":
        return _deploy_site(site, cfg)
    if name == "publish_post":
        return _publish_post(site, cfg, args)
    if name == "git_status":
        return _git_status(site)
    return {"ok": False, "error": "unknown tool: %s" % name}


def _find_post(site: Site, query: str) -> posts.Post:
    all_posts = posts.list_posts(site.posts_dir)
    if not all_posts:
        raise AssistantError("no posts found")
    q = query.strip().lower()
    if q == "latest":
        return all_posts[0]
    matches = [
        p for p in all_posts
        if q == p.path.stem.lower() or q in p.path.stem.lower() or q in p.title.lower()
    ]
    if not matches:
        raise AssistantError("no post matches '%s'" % query)
    if len(matches) > 1:
        names = ", ".join("%s (%s)" % (p.title, p.path.name) for p in matches[:6])
        raise AssistantError("ambiguous post '%s': %s" % (query, names))
    return matches[0]


def _post_summary(post: posts.Post, site: Site) -> dict:
    return {
        "title": post.title,
        "file": str(post.path.relative_to(site.root)),
        "date": post.date.isoformat(timespec="seconds") if post.date else "",
        "draft": post.draft,
        "tags": list(post.tags),
    }


def _post_detail(post: posts.Post, site: Site) -> dict:
    data = _post_summary(post, site)
    data["body"] = post.body
    data["front_matter_extra"] = dict(post.extra)
    return data


def _safe_deploy_config(deploy_cfg: dict) -> dict:
    safe = dict(deploy_cfg)
    if safe.get("ftp_password"):
        safe["ftp_password"] = "(set)"
    return safe


def _run_subprocess(argv: list[str], cwd: Path, timeout: int = 120) -> tuple[int, str]:
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _deploy_site(site: Site, cfg: ToolConfig) -> dict:
    d = cfg.deploy
    if d.get("build_first", True):
        if not site.hugo_available():
            raise AssistantError("hugo is not on PATH")
        rc, out = _run_subprocess(site.build_argv(bool(d.get("include_drafts"))), site.root, 300)
        if rc != 0:
            return {"ok": False, "stage": "build", "exit_code": rc, "output": out[-6000:]}
    pub = site.public_dir
    if not pub.is_dir() or not any(pub.iterdir()):
        raise AssistantError("public/ is empty")
    method = d.get("method")
    if method == "github":
        info = deploy.github_pages_publish(d, pub)
        return {"ok": True, "method": "github", "pushed": info}
    if method == "rsync":
        if not d.get("host"):
            raise AssistantError("rsync host is not configured")
        rc, out = _run_subprocess(deploy.rsync_argv(d, pub), site.root, 300)
        return {"ok": rc == 0, "method": "rsync", "exit_code": rc, "output": out[-6000:]}
    if method in ("ftp", "ftps"):
        password = d.get("ftp_password") or getpass.getpass("FTP password: ")
        n = deploy.ftp_upload(d, pub, password)
        return {"ok": True, "method": method, "uploaded_files": n}
    raise AssistantError("unknown deployment method: %s" % method)


def _publish_post(site: Site, cfg: ToolConfig, args: dict) -> dict:
    post = _find_post(site, args["post"])
    post.draft = False
    post.save()
    result = {
        "ok": True,
        "post": _post_summary(post, site),
        "source_commit": None,
        "source_push": None,
        "deploy": None,
    }
    if args.get("commit_source"):
        result["source_commit"] = _commit_source_changes(
            site,
            args.get("commit_message") or "Publish %s" % post.title,
        )
        if not result["source_commit"].get("ok"):
            result["ok"] = False
            return result
        if args.get("push_source"):
            rc, out = _run_subprocess(["git", "push"], site.root, timeout=300)
            result["source_push"] = {
                "ok": rc == 0,
                "exit_code": rc,
                "output": out[-4000:],
            }
            if rc != 0:
                result["ok"] = False
                return result
    result["deploy"] = _deploy_site(site, cfg)
    if not result["deploy"].get("ok"):
        result["ok"] = False
    return result


def _git_status(site: Site) -> dict:
    if not (site.root / ".git").exists():
        return {"ok": False, "error": "site is not a git repository"}
    branch_rc, branch = _run_subprocess(
        ["git", "branch", "--show-current"], site.root, timeout=30
    )
    status_rc, status = _run_subprocess(
        ["git", "status", "--short", "--branch"], site.root, timeout=30
    )
    return {
        "ok": branch_rc == 0 and status_rc == 0,
        "branch": branch.strip(),
        "status": status,
    }


def _commit_source_changes(site: Site, message: str) -> dict:
    if not (site.root / ".git").exists():
        return {"ok": False, "error": "site is not a git repository"}
    paths = [
        "archetypes", "content", "layouts", "static", "themes",
        "hugo.toml", "config.toml", ".github", ".gitignore", "README.md",
    ]
    existing = [path for path in paths if (site.root / path).exists()]
    if not existing:
        return {"ok": False, "error": "no source paths found to stage"}
    rc, out = _run_subprocess(["git", "add", *existing], site.root, timeout=120)
    if rc != 0:
        return {"ok": False, "stage": "add", "exit_code": rc, "output": out[-4000:]}
    rc, out = _run_subprocess(["git", "diff", "--cached", "--quiet"], site.root, timeout=30)
    if rc == 0:
        return {"ok": True, "changed": False, "message": "no source changes to commit"}
    rc, out = _run_subprocess(["git", "commit", "-m", message], site.root, timeout=120)
    return {
        "ok": rc == 0,
        "changed": True,
        "exit_code": rc,
        "output": out[-4000:],
    }
