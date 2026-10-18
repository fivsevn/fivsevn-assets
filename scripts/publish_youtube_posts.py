import html
import json
import os
import re
import sys
import time

import feedparser
import requests


TARGETS = [
    {
        "name": "fivsevn",
        "channel_id_env": "YOUTUBE_FIVSEVN_CHANNEL_ID",
        "category_slug": "motion",
        "extract_title_tags": True,
    },
]

FEED_RETRY_DELAYS = (5, 15, 30)
FEED_TIMEOUT = (10, 30)


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value.rstrip("/") if name.endswith("URL") else value


WP_BASE_URL = env("WP_BASE_URL")
WP_USERNAME = env("WP_USERNAME")
WP_APP_PASSWORD = env("WP_APP_PASSWORD")

AUTH = (WP_USERNAME, WP_APP_PASSWORD)


def wp_get(endpoint: str, params: dict | None = None):
    response = requests.get(
        f"{WP_BASE_URL}/wp-json/wp/v2/{endpoint.lstrip('/')}",
        params=params,
        auth=AUTH,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def wp_post(endpoint: str, payload: dict):
    response = requests.post(
        f"{WP_BASE_URL}/wp-json/wp/v2/{endpoint.lstrip('/')}",
        json=payload,
        auth=AUTH,
        timeout=30,
    )
    if not response.ok:
        print(response.status_code, response.text, file=sys.stderr)
    response.raise_for_status()
    return response.json()


def get_channel_id(target: dict) -> str:
    channel_id = env(target["channel_id_env"])
    if not channel_id.startswith("UC"):
        raise RuntimeError(
            f"{target['name']}: channel id must be the UC... id only, "
            f"not a handle or URL. Current value starts with: {channel_id[:30]}"
        )
    return channel_id


def get_category_id_by_slug(slug: str) -> int:
    items = wp_get("categories", {"slug": slug, "per_page": 100})
    if items:
        return int(items[0]["id"])

    raise RuntimeError(f"Category not found by slug: {slug}")


def split_youtube_title_and_tags(raw_title: str) -> tuple[str, list[str]]:
    parts = raw_title.split("#")
    title = parts[0].strip()

    if not title:
        title = raw_title.strip() or "YouTube"

    tags: list[str] = []
    for part in parts[1:]:
        tag = part.strip()
        if tag:
            tags.append(tag)

    return title, tags


def get_or_create_tag_id(name: str) -> int:
    items = wp_get("tags", {"search": name, "per_page": 100})
    for item in items:
        if item.get("name", "").strip().lower() == name.strip().lower():
            return int(item["id"])

    created = wp_post("tags", {"name": name})
    return int(created["id"])


def get_tag_ids(names: list[str]) -> list[int]:
    return [get_or_create_tag_id(name) for name in names]


def renderers(node, name):
    if isinstance(node, dict):
        if name in node:
            yield node[name]
        for value in node.values():
            yield from renderers(value, name)
    elif isinstance(node, list):
        for value in node:
            yield from renderers(value, name)


def youtube_text(value: dict) -> str:
    return value.get("simpleText") or "".join(run.get("text", "") for run in value.get("runs", []))


def parse_uploads_page(document: str, channel_id: str) -> tuple[str, str]:
    """Read only the owner's uploads list, never recommendations elsewhere on the page."""
    marker = re.search(r"var ytInitialData\s*=\s*", document)
    if not marker:
        raise ValueError("uploads page has no initial data")
    data, _ = json.JSONDecoder().raw_decode(document[marker.end():])
    headers = list(renderers(data.get("header", {}), "playlistHeaderRenderer"))
    if len(headers) != 1:
        raise ValueError("uploads page has no unique playlist header")
    header = headers[0]
    playlist_id = "UU" + channel_id[2:]
    owner = header.get("ownerEndpoint", {}).get("browseEndpoint", {}).get("browseId")
    if header.get("playlistId") != playlist_id or owner != channel_id:
        raise RuntimeError("YouTube uploads playlist identity does not match the configured channel")

    contents = data.get("contents", {})
    lists = list(renderers(contents, "playlistVideoListRenderer")) + list(renderers(contents, "richGridRenderer"))
    if len(lists) != 1:
        raise ValueError("uploads page has no unique video list")
    for item in lists[0].get("contents", []):
        if "continuationItemRenderer" in item:
            continue
        card = item.get("richItemRenderer", {}).get("content", item)
        if "playlistVideoRenderer" in card or "videoRenderer" in card:
            video = card.get("playlistVideoRenderer", card.get("videoRenderer"))
            if video.get("isPlayable") is False:
                continue
            video_id, title = video.get("videoId"), youtube_text(video.get("title", {}))
        elif "shortsLockupViewModel" in card:
            video = card["shortsLockupViewModel"]
            video_id = video.get("onTap", {}).get("innertubeCommand", {}).get("reelWatchEndpoint", {}).get("videoId")
            title = video.get("overlayMetadata", {}).get("primaryText", {}).get("content")
        elif "lockupViewModel" in card:
            video = card["lockupViewModel"]
            if video.get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO":
                raise ValueError("unexpected item in uploads list")
            video_id = video.get("contentId")
            title = video.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {}).get("content")
        else:
            raise ValueError("unrecognized first uploads item; refusing to select an older video")
        if not isinstance(video_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) or not isinstance(title, str) or not title.strip():
            raise ValueError("uploads item has no valid video ID or title")
        return title, video_id
    raise ValueError("uploads playlist contains no public videos")


def get_latest_uploads_video(channel_id: str) -> tuple[str, str]:
    response = requests.get(
        "https://www.youtube.com/playlist?list=UU" + channel_id[2:] + "&hl=en",
        headers={"User-Agent": "Mozilla/5.0 (compatible; fivsevn-youtube-sync/1.0)", "Accept": "text/html"},
        timeout=FEED_TIMEOUT,
    )
    response.raise_for_status()
    return parse_uploads_page(response.text, channel_id)


def get_latest_youtube_video(channel_id: str, target_name: str) -> tuple[str, str]:
    feed_url = (
        "https://www.youtube.com/feeds/videos.xml"
        f"?channel_id={channel_id}"
    )

    attempts = len(FEED_RETRY_DELAYS) + 1
    reason = "no response"
    for attempt in range(attempts):
        try:
            # Download explicitly: feedparser's URL fetch has no per-request timeout.
            # Only this read is retried; a WordPress POST must never be replayed blindly.
            response = requests.get(
                feed_url,
                headers={"User-Agent": "fivsevn-youtube-sync/1.0", "Accept": "application/atom+xml"},
                timeout=FEED_TIMEOUT,
            )
        except requests.RequestException as error:
            reason = f"network error ({type(error).__name__})"
        else:
            if response.status_code != 200:
                reason = f"HTTP {response.status_code}"
                if response.status_code not in {404, 408, 429} and not 500 <= response.status_code < 600:
                    raise RuntimeError(f"{target_name}: YouTube feed returned {reason}")
            else:
                feed = feedparser.parse(response.content)
                if feed.get("bozo") or not feed.get("version"):
                    reason = "invalid feed document"
                elif not feed.entries:
                    reason = "feed contains no videos"
                else:
                    source_channel = feed.feed.get("yt_channelid")
                    if source_channel and source_channel != channel_id:
                        raise RuntimeError(f"{target_name}: YouTube feed belongs to another channel")
                    latest = feed.entries[0]
                    title = latest.get("title", "YouTube")
                    video_id = latest.get("yt_videoid")
                    if not video_id:
                        match = re.search(r"(?:v=|/shorts/)([^?&/]+)", latest.get("link", ""))
                        video_id = match.group(1) if match else None
                    if video_id:
                        print(f"Read latest YouTube video [{target_name}] on attempt {attempt + 1}/{attempts}.", flush=True)
                        return title, video_id
                    reason = "latest feed entry has no video ID"

        # YouTube can keep returning 404 for both of its XML feed endpoints while
        # the same channel's official public uploads playlist remains available.
        print(f"YouTube feed [{target_name}]: {reason}; checking the official uploads page.", flush=True)
        try:
            title, video_id = get_latest_uploads_video(channel_id)
        except (requests.RequestException, ValueError) as error:
            reason += f"; uploads page unavailable ({type(error).__name__})"
        else:
            print(f"Read latest YouTube video [{target_name}] from the verified official uploads page on attempt {attempt + 1}/{attempts}.", flush=True)
            return title, video_id

        if attempt < len(FEED_RETRY_DELAYS):
            delay = FEED_RETRY_DELAYS[attempt]
            print(
                f"YouTube feed [{target_name}]: {reason}; attempt {attempt + 1}/{attempts} "
                f"failed, retrying in {delay}s.",
                flush=True,
            )
            time.sleep(delay)

    raise RuntimeError(f"{target_name}: could not read YouTube feed after {attempts} attempts ({reason})")


def make_video_url(video_id: str) -> str:
    # 统一转成普通 YouTube watch 链接。
    # Shorts 原链接如：
    # https://youtube.com/shorts/64mxEOPAHLc?si=...
    # 会被写成：
    # https://www.youtube.com/watch?v=64mxEOPAHLc
    return f"https://www.youtube.com/watch?v={video_id}"


def make_post_slug(video_id: str) -> str:
    return f"youtube-{video_id}"


def post_already_exists(slug: str) -> bool:
    items = wp_get(
        "posts",
        {
            "slug": slug,
            "status": "publish,draft,private,future,pending",
            "per_page": 10,
        },
    )
    return bool(items)


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


def publish_latest_for_target(target: dict, category_cache: dict[str, int]) -> None:
    target_name = target["name"]
    category_slug = target["category_slug"]
    channel_id = get_channel_id(target)

    raw_title, video_id = get_latest_youtube_video(channel_id, target_name)

    if target.get("extract_title_tags"):
        title, tag_names = split_youtube_title_and_tags(raw_title)
    else:
        title = raw_title
        tag_names = []

    video_url = make_video_url(video_id)
    slug = make_post_slug(video_id)

    if post_already_exists(slug):
        print(f"Skip existing YouTube post [{target_name}]: {title} ({video_url})")
        return

    if category_slug not in category_cache:
        category_cache[category_slug] = get_category_id_by_slug(category_slug)

    category_id = category_cache[category_slug]
    content = make_youtube_embed_block(video_url)

    payload = {
        "status": "publish",
        "title": title,
        "slug": slug,
        "content": content,
        "categories": [category_id],
        "format": "video",
    }

    if tag_names:
        payload["tags"] = get_tag_ids(tag_names)

    post = wp_post("posts", payload)

    print(
        f"Published YouTube post [{target_name}]: "
        f"{title} -> {post.get('link')} "
        f"category={category_slug}"
    )


def main() -> None:
    category_cache: dict[str, int] = {}
    for target in TARGETS:
        publish_latest_for_target(target, category_cache)


if __name__ == "__main__":
    main()
