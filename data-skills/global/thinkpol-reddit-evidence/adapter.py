"""Hosted adapter for ThinkPol's documented Reddit evidence API."""

from __future__ import annotations

import csv
import io
from typing import Any
from urllib.parse import quote

import httpx

API_ROOT = "https://api.think-pol.com"
SEARCH_URL = f"{API_ROOT}/v2/search"
SOURCE_ID = "global/thinkpol/reddit-evidence"
PROFILE_MODELS = {
    "x-ai/grok-4.3",
    "google/gemini-2.5-flash",
    "deepseek/deepseek-v4-pro",
    "google/gemini-3.1-flash-lite",
    "openai/gpt-5.4-nano",
}


def _operation(input: dict[str, Any]) -> str:
    operation = input.get("operation") or "search"
    allowed = {
        "analyze_profile",
        "quota",
        "search",
        "subreddit_users",
        "user_history",
    }
    if operation not in allowed:
        raise ValueError(f"operation must be one of: {', '.join(sorted(allowed))}.")
    return operation


def _required_string(input: dict[str, Any], field: str) -> str:
    value = input.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required.")
    return value.strip()


def _terms(input: dict[str, Any]) -> list[str]:
    supplied = input.get("terms")
    if supplied is None:
        supplied = [input.get("q")]
    elif isinstance(supplied, str):
        supplied = [supplied]
    elif not isinstance(supplied, list):
        raise ValueError("terms must be a string or list of strings.")

    terms = [term.strip() for term in supplied if isinstance(term, str) and term.strip()]
    if not terms:
        raise ValueError("Provide q or one or more terms.")
    return terms


def _boolean_param(input: dict[str, Any], field: str) -> bool | None:
    value = input.get(field)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean.")
    return value


def _normalize_submission(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity": "RedditSubmission",
        "id": record.get("id"),
        "title": record.get("title"),
        "text": record.get("text"),
        "author": record.get("author"),
        "subreddit": record.get("subreddit"),
        "created_at": record.get("created_utc"),
        "score": record.get("score"),
        "num_comments": record.get("num_comments"),
        "content_type": "submission",
        "source_url": record.get("submission_url") or record.get("url"),
    }


def _normalize_comment(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity": "RedditComment",
        "id": record.get("id"),
        "text": record.get("text"),
        "author": record.get("author"),
        "subreddit": record.get("subreddit"),
        "created_at": record.get("created_utc"),
        "score": record.get("score"),
        "submission_id": record.get("submission_id"),
        "parent_id": record.get("parent_id"),
        "content_type": "comment",
        "source_url": record.get("comment_url"),
    }


def _search(input: dict[str, Any], client: httpx.Client) -> dict[str, Any]:
    content_type = input.get("content_type")
    if content_type and content_type not in {"comment", "submission"}:
        raise ValueError("content_type must be `comment` or `submission`.")

    params: list[tuple[str, str | int]] = [("terms", term) for term in _terms(input)]
    bounds: dict[str, int] = {}
    for key in ("from", "to"):
        if input.get(key) is not None:
            value = int(input[key])
            if value < 0:
                raise ValueError(f"{key} must be a non-negative Unix timestamp.")
            bounds[key] = value
            params.append((key, value))
    if bounds.get("from") is not None and bounds.get("to") is not None:
        if bounds["from"] > bounds["to"]:
            raise ValueError("from must not be later than to.")
    if content_type:
        params.append(("type", content_type))

    response = client.get(SEARCH_URL, params=params)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("ThinkPol search response must be a JSON object.")
    submissions = data.get("submissions") or []
    comments = data.get("comments") or []
    if not isinstance(submissions, list) or not isinstance(comments, list):
        raise ValueError("ThinkPol search response collections must be arrays.")
    records = [_normalize_submission(record) for record in submissions]
    records.extend(_normalize_comment(record) for record in comments)
    return {
        "source_id": SOURCE_ID,
        "operation": "search",
        "records": records,
        "page": {"returned": len(records)},
    }


def _user_history(input: dict[str, Any], client: httpx.Client) -> dict[str, Any]:
    username = _required_string(input, "username")
    latest = _boolean_param(input, "latest")
    params = {"latest": latest} if latest is not None else None
    response = client.get(
        f"{API_ROOT}/user/{quote(username, safe='')}",
        params=params,
    )
    response.raise_for_status()
    rows = csv.reader(io.StringIO(response.text), delimiter=";")
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) != 4:
            raise ValueError(
                f"ThinkPol user-history CSV row {index} has {len(row)} columns; expected 4."
            )
        text, raw_id, created_at, subreddit = (cell.strip() for cell in row)
        if index == 1 and raw_id.lower() in {"comment id", "comment_id", "id"}:
            continue
        content_id = raw_id.removeprefix("[").removesuffix("]")
        content_type = "submission" if text.startswith("[") else "comment"
        records.append(
            {
                "entity": "RedditSubmission" if content_type == "submission" else "RedditComment",
                "id": content_id,
                "text": text,
                "author": username,
                "subreddit": subreddit,
                "created_at": created_at,
                "content_type": content_type,
                "source_url": f"{API_ROOT}/user/{quote(username, safe='')}",
            }
        )
    return {
        "source_id": SOURCE_ID,
        "operation": "user_history",
        "records": records,
        "page": {"returned": len(records)},
    }


def _subreddit_users(input: dict[str, Any], client: httpx.Client) -> dict[str, Any]:
    subreddit = _required_string(input, "subreddit_name")
    response = client.get(f"{API_ROOT}/subreddit/{quote(subreddit, safe='')}")
    response.raise_for_status()
    usernames = response.json()
    # The live API returns JSON null, rather than an empty array, when no
    # subreddit association is found. Normalize that observed no-result shape.
    if usernames is None:
        usernames = []
    if not isinstance(usernames, list) or not all(isinstance(item, str) for item in usernames):
        raise ValueError("ThinkPol subreddit response must be an array of usernames.")
    records = [
        {
            "entity": "RedditAuthor",
            "username": username,
            "subreddit": subreddit,
            "source_url": f"https://www.reddit.com/user/{quote(username, safe='')}/",
        }
        for username in usernames
    ]
    return {
        "source_id": SOURCE_ID,
        "operation": "subreddit_users",
        "records": records,
        "page": {"returned": len(records)},
    }


def _quota(client: httpx.Client) -> dict[str, Any]:
    response = client.get(f"{API_ROOT}/quota")
    response.raise_for_status()
    remaining = response.json()
    if not isinstance(remaining, int) or isinstance(remaining, bool):
        raise ValueError("ThinkPol quota response must be an integer.")
    return {
        "source_id": SOURCE_ID,
        "operation": "quota",
        "records": [
            {
                "entity": "ApiQuota",
                "remaining": remaining,
                "source_url": f"{API_ROOT}/quota",
            }
        ],
        "page": {},
    }


def _analyze_profile(input: dict[str, Any], client: httpx.Client) -> dict[str, Any]:
    username = _required_string(input, "username")
    params: dict[str, Any] = {}
    model = input.get("model")
    if model is not None:
        if model not in PROFILE_MODELS:
            raise ValueError("model is not one of ThinkPol's documented analysis models.")
        params["model"] = model
    for field in ("latest", "refresh", "sources"):
        value = _boolean_param(input, field)
        if value is not None:
            params[field] = value
    use_case = input.get("use_case")
    if use_case is not None:
        if use_case != "law_enforcement":
            raise ValueError("use_case must be `law_enforcement` when supplied.")
        params["use_case"] = use_case

    response = client.get(
        f"{API_ROOT}/analyze/{quote(username, safe='')}",
        params=params or None,
    )
    response.raise_for_status()
    profile = response.json()
    if not isinstance(profile, dict):
        raise ValueError("ThinkPol profile response must be a JSON object.")
    canonical_username = profile.get("username") or username
    record = {
        "entity": "InferredRedditProfile",
        "username": canonical_username,
        "age": profile.get("age"),
        "sex": profile.get("sex"),
        "location": profile.get("location"),
        "country": profile.get("country"),
        "occupation": profile.get("occupation"),
        "relationship": profile.get("relationship"),
        "income_level": profile.get("income_level"),
        "interests": profile.get("interests"),
        "brand_mentions": profile.get("brand_mentions"),
        "life_stage": profile.get("life_stage"),
        "personality": profile.get("personality"),
        "sources": profile.get("sources"),
        "source_url": f"https://www.reddit.com/user/{quote(canonical_username, safe='')}/",
    }
    return {
        "source_id": SOURCE_ID,
        "operation": "analyze_profile",
        "records": [record],
        "page": {},
    }


def run(input: dict[str, Any], ctx) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {ctx.get_key('thinkpol')}"}
    with httpx.Client(headers=headers, timeout=90) as client:
        operation = _operation(input)
        if operation == "user_history":
            return _user_history(input, client)
        if operation == "subreddit_users":
            return _subreddit_users(input, client)
        if operation == "quota":
            return _quota(client)
        if operation == "analyze_profile":
            return _analyze_profile(input, client)
        return _search(input, client)
