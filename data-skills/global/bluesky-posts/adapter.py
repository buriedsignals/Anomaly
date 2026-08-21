"""Adapter for global/bluesky/posts — Bluesky public AppView (EXPERIMENTAL).

Two ops over https://public.api.bsky.app/xrpc (no key):
  search  → app.bsky.feed.searchPosts   (full-text post search)
  profile → app.bsky.actor.getProfile   (account lookup by handle or DID)

The search lexicon explicitly allows service providers to require
authentication. As of 2026-08-12, Bluesky's public AppView returns a CDN-level
403 to this unauthenticated egress for searchPosts, while getProfile stays open.
When search is blocked we raise a clear error instead of a retry storm.

Rate limit: ~3000 req/5min per IP. Single attempt per call, no retries.
"""

from __future__ import annotations

from typing import Any

import httpx

API_URL = "https://public.api.bsky.app/xrpc"
SOURCE_ID = "global/bluesky/posts"
USER_AGENT = "BuriedSignals-Navigator/1.0"

def _search_blocked_msg(code: int) -> str:
    return (
        f"Bluesky public AppView refused unauthenticated post search (HTTP {code}). "
        "This EXPERIMENTAL endpoint has no stability commitment and has flipped "
        "between open and auth-required before — this egress is currently "
        "denied (observed 2026-08-12). Profile lookup still works: "
        'try {"actor": "<handle>"}. Do not retry search in a loop.'
    )


def _post_web_url(uri: str | None, author: dict[str, Any]) -> str | None:
    """at://<did>/app.bsky.feed.post/<rkey> → https://bsky.app/profile/<handle>/post/<rkey>."""
    if not uri or "/app.bsky.feed.post/" not in uri:
        return None
    rkey = uri.rsplit("/", 1)[-1]
    who = author.get("handle") or author.get("did")
    if not who or not rkey:
        return None
    return f"https://bsky.app/profile/{who}/post/{rkey}"


def _normalize_post(p: dict[str, Any]) -> dict[str, Any]:
    author = p.get("author") or {}
    record = p.get("record") or {}
    return {
        "entity": "Post",
        "text": record.get("text"),
        "handle": author.get("handle"),
        "display_name": author.get("displayName"),
        "did": author.get("did"),
        "created_at": record.get("createdAt"),
        "indexed_at": p.get("indexedAt"),
        "likes": p.get("likeCount"),
        "reposts": p.get("repostCount"),
        "replies": p.get("replyCount"),
        "uri": p.get("uri"),
        "source_url": _post_web_url(p.get("uri"), author),
    }


def _normalize_profile(d: dict[str, Any]) -> dict[str, Any]:
    who = d.get("handle") or d.get("did")
    return {
        "entity": "Profile",
        "text": d.get("description"),
        "handle": d.get("handle"),
        "display_name": d.get("displayName"),
        "did": d.get("did"),
        "created_at": d.get("createdAt"),
        "indexed_at": d.get("indexedAt"),
        "followers": d.get("followersCount"),
        "follows": d.get("followsCount"),
        "posts": d.get("postsCount"),
        "source_url": f"https://bsky.app/profile/{who}" if who else None,
    }


def _mode(input: dict) -> str:
    """Explicit `mode`, else inferred from which inputs are present."""
    mode = input.get("mode")
    if mode:
        if mode not in ("search", "profile"):
            raise ValueError(f"Unknown mode `{mode}` — use search or profile.")
        return mode
    if input.get("actor"):
        return "profile"
    if input.get("q"):
        return "search"
    raise ValueError("Provide `q` (post search) or `actor` (profile lookup).")


def _search(input: dict, client: httpx.Client) -> dict:
    q = input.get("q")
    if not isinstance(q, str) or not q.strip():
        raise ValueError("q is required for post search.")
    q = q.strip()
    params: dict[str, Any] = {
        "q": q,
        "limit": max(1, min(int(input.get("limit", 10)), 100)),
    }
    if input.get("sort"):
        if input["sort"] not in ("top", "latest"):
            raise ValueError("sort must be `top` or `latest`.")
        params["sort"] = input["sort"]
    if input.get("cursor"):
        params["cursor"] = input["cursor"]
    for field in ("since", "until", "mentions", "author", "lang", "domain", "url"):
        value = input.get(field)
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a non-empty string.")
            params[field] = value.strip()
    tags = input.get("tag")
    if tags is not None:
        if isinstance(tags, str):
            tags = [tags]
        if not isinstance(tags, list) or not tags:
            raise ValueError("tag must be a non-empty string or list of strings.")
        cleaned_tags = []
        for tag in tags:
            if not isinstance(tag, str) or not tag.strip():
                raise ValueError("tag values must be non-empty strings.")
            cleaned = tag.strip()
            if cleaned.startswith("#"):
                raise ValueError("tag values must not include the # prefix.")
            cleaned_tags.append(cleaned)
        params["tag"] = cleaned_tags
    resp = client.get(f"{API_URL}/app.bsky.feed.searchPosts", params=params)
    if resp.status_code in (401, 403):
        raise RuntimeError(_search_blocked_msg(resp.status_code))
    resp.raise_for_status()
    data = resp.json()
    posts = data.get("posts") or []
    return {
        "source_id": SOURCE_ID,
        "mode": "search",
        "records": [_normalize_post(p) for p in posts],
        "page": {
            "limit": params["limit"],
            "returned": len(posts),
            "hits_total": data.get("hitsTotal"),
            "cursor": data.get("cursor"),
        },
    }


def _profile(input: dict, client: httpx.Client) -> dict:
    actor = input.get("actor")
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("actor is required for profile lookup.")
    resp = client.get(
        f"{API_URL}/app.bsky.actor.getProfile", params={"actor": actor.strip()}
    )
    resp.raise_for_status()
    return {
        "source_id": SOURCE_ID,
        "mode": "profile",
        "records": [_normalize_profile(resp.json())],
        "page": {},
    }


def run(input: dict, ctx) -> dict:
    mode = _mode(input)
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30) as client:
        return _search(input, client) if mode == "search" else _profile(input, client)
