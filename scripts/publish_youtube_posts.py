"""Reconcile the channel's public uploads with WordPress Motion posts."""
import argparse
from datetime import datetime, timezone
import html
import os
import re
import sys

import requests

from youtube_source import Video, get_channel_videos, get_video_metadata


TARGETS = [
    {
        "name": "fivsevn",
        "channel_id_env": "YOUTUBE_FIVSEVN_CHANNEL_ID",
        "category_slug": "motion",
        "extract_title_tags": True,
    },
]
POST_STATUSES = "publish,draft,private,future,pending"
VIDEO_URL_PATTERN = re.compile(
    r"(?:https?:)?//(?:www\.|m\.)?(?:"
    r"youtube(?:-nocookie)?\.com/(?:watch\?[^\s\"'<>]*?v=|embed/|shorts/|live/)"
    r"|youtu\.be/)([A-Za-z0-9_-]{11})(?![A-Za-z0-9_-])",
    re.IGNORECASE,
)


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value.rstrip("/") if name.endswith("URL") else value


def wp_get(endpoint: str, params: dict | None = None):
    response = requests.get(
        f"{env('WP_BASE_URL')}/wp-json/wp/v2/{endpoint.lstrip('/')}",
        params=params,
        auth=(env("WP_USERNAME"), env("WP_APP_PASSWORD")),
        timeout=(10, 30),
    )
    response.raise_for_status()
    return response.json()


def wp_post(endpoint: str, payload: dict):
    # A timed-out write may already have succeeded; never replay a POST blindly.
    response = requests.post(
        f"{env('WP_BASE_URL')}/wp-json/wp/v2/{endpoint.lstrip('/')}",
        json=payload,
        auth=(env("WP_USERNAME"), env("WP_APP_PASSWORD")),
        timeout=(10, 30),
    )
    if not response.ok:
        print(response.status_code, response.text, file=sys.stderr)
    response.raise_for_status()
    return response.json()


def get_channel_id(target: dict) -> str:
    channel_id = env(target["channel_id_env"])
    if not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", channel_id):
        raise RuntimeError(f"{target['name']}: channel id must be the complete UC... ID")
    return channel_id


def get_category_id_by_slug(slug: str) -> int:
    items = wp_get("categories", {"slug": slug, "per_page": 100})
    if items:
        return int(items[0]["id"])
    raise RuntimeError(f"Category not found by slug: {slug}")


def split_youtube_title_and_tags(raw_title: str) -> tuple[str, list[str]]:
    parts = raw_title.split("#")
    title = parts[0].strip() or raw_title.strip() or "YouTube"
    return title, list(dict.fromkeys(part.strip() for part in parts[1:] if part.strip()))


def get_or_create_tag_id(name: str) -> int:
    items = wp_get("tags", {"search": name, "per_page": 100})
    for item in items:
        if item.get("name", "").strip().lower() == name.strip().lower():
            return int(item["id"])
    return int(wp_post("tags", {"name": name})["id"])


def get_tag_ids(names: list[str]) -> list[int]:
    return [get_or_create_tag_id(name) for name in names]


def make_video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def make_post_slug(video_id: str) -> str:
    return f"youtube-{video_id}".lower()


def video_ids_in_post(post: dict) -> set[str]:
    content = post.get("content", {})
    if isinstance(content, dict):
        content = "\n".join(content.get(field, "") for field in ("raw", "rendered"))
    # Raw Gutenberg attributes may escape slashes; rendered embeds encode '&'.
    content = html.unescape(content.replace("\\/", "/"))
    return set(VIDEO_URL_PATTERN.findall(content))


def existing_video_index() -> tuple[set[str], set[str]]:
    """Include unpublished posts, legacy slugs, and every WordPress result page."""
    video_ids, slugs = set(), set()
    page = 1
    while True:
        items = wp_get("posts", {
            "context": "edit",
            "status": POST_STATUSES,
            "per_page": 100,
            "offset": (page - 1) * 100,
            "orderby": "id",
            "order": "asc",
            "_fields": "id,slug,content,status",
        })
        for item in items:
            slugs.add(item.get("slug", "").lower())
            video_ids.update(video_ids_in_post(item))
        if len(items) < 100:
            return video_ids, slugs
        page += 1
        # Offset returns [] past the last page, including exact multiples of 100.


def post_already_exists(slug: str) -> bool:
    # Also protect posts moved out of Motion while retaining their stable slug.
    return bool(wp_get("posts", {"slug": slug, "status": POST_STATUSES, "per_page": 10}))


def make_youtube_embed_block(video_url: str) -> str:
    escaped_url = html.escape(video_url, quote=True)
    return f"""
<!-- wp:embed {{"url":"{escaped_url}","type":"video","providerNameSlug":"youtube","responsive":false}} -->
<figure class="wp-block-embed is-type-video is-provider-youtube wp-block-embed-youtube">
    <div class="wp-block-embed__wrapper">
    {escaped_url}
    </div>
</figure>
<!-- /wp:embed -->
""".strip()


def publication_time(video: Video) -> datetime:
    if not video.published_at or "T" not in video.published_at:
        raise ValueError(f"{video.video_id}: missing exact YouTube publication time")
    value = datetime.fromisoformat(video.published_at.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError(f"{video.video_id}: publication time has no timezone")
    value = value.astimezone(timezone.utc)
    if value > datetime.now(timezone.utc):
        raise ValueError(f"{video.video_id}: video is scheduled in the future")
    return value


def build_publish_plan(target: dict) -> list[Video]:
    channel_id = get_channel_id(target)
    videos = get_channel_videos(channel_id, target["name"])
    existing_ids, slugs = existing_video_index()
    missing = []
    for video in videos:
        if video.video_id in existing_ids or make_post_slug(video.video_id) in slugs:
            continue
        if post_already_exists(make_post_slug(video.video_id)):
            continue
        # Verify all missing metadata before the first write. Watch pages supply
        # exact publication times for uploads that have aged out of the RSS feed.
        if not video.published_at:
            video = get_video_metadata(video.video_id, channel_id)
        publication_time(video)
        missing.append(video)
        existing_ids.add(video.video_id)
    # Python's stable sort preserves source order when timestamps are identical.
    # Uploads are newest-first, so reverse first to publish oldest-first.
    missing.reverse()
    missing.sort(key=publication_time)
    print(f"[{target['name']}] {len(videos)} public uploads; {len(missing)} missing posts.", flush=True)
    return missing


def publish_for_target(target: dict, *, dry_run: bool = False) -> None:
    category_id = get_category_id_by_slug(target["category_slug"])
    plan = build_publish_plan(target)
    for video in plan:
        timestamp = publication_time(video).strftime("%Y-%m-%dT%H:%M:%S")
        print(f"{'Would publish' if dry_run else 'Publishing'} {timestamp}Z {video.video_id} {video.title}", flush=True)
        if dry_run:
            continue
        # Recheck immediately before writing; a previous interrupted run or a
        # manual publish may have created the same stable slug in the meantime.
        if post_already_exists(make_post_slug(video.video_id)):
            continue
        title, tags = split_youtube_title_and_tags(video.title) if target.get("extract_title_tags") else (video.title, [])
        payload = {
            "status": "publish",
            "title": title,
            "slug": make_post_slug(video.video_id),
            "date_gmt": timestamp,
            "content": make_youtube_embed_block(make_video_url(video.video_id)),
            "categories": [category_id],
            "format": "video",
        }
        if tags:
            payload["tags"] = get_tag_ids(tags)
        post = wp_post("posts", payload)
        print(f"Published {video.video_id} -> {post.get('link')}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Read and print the ordered plan without writing posts or tags")
    args = parser.parse_args()
    for target in TARGETS:
        publish_for_target(target, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
