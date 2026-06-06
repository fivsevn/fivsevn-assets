import html
import os
import re
import sys

import feedparser
import requests


# 两个 YouTube 频道分别发布到不同 WordPress 分类。
TARGETS = [
    {
        "name": "57store.fivsevn",
        "channel_id_env": "YOUTUBE_57STORE_CHANNEL_ID",
        "category_slug": "57storecctv",
    },
    {
        "name": "fivsevn",
        "channel_id_env": "YOUTUBE_FIVSEVN_CHANNEL_ID",
        "category_slug": "motion",

        # 只对 @fivsevn 生效：
        # YouTube 标题里的 # 后面内容，不进入 WordPress 标题，
        # 而是转成 WordPress tag。
        #
        # 例：
        # "Silence Turns Red. #可灵AI"
        # WordPress title => "Silence Turns Red."
        # WordPress tag   => "可灵AI"
        "extract_title_tags": True,
    },
]


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
    """
    把 YouTube 标题拆成 WordPress 标题和 WordPress tags。

    规则：
    - 第一个 # 前面的内容，作为 WordPress 标题。
    - 每个 # 后面的内容，作为 tag。
    - tag 去掉首尾空格。
    - tag 去重，但保留原顺序。

    例：
    "Glass Eats Color. #Firefly"
    => title: "Glass Eats Color."
    => tags: ["Firefly"]

    "Something. #Runway #可灵AI"
    => title: "Something."
    => tags: ["Runway", "可灵AI"]
    """
    parts = raw_title.split("#")

    clean_title = parts[0].strip()
    if not clean_title:
        clean_title = raw_title.strip() or "YouTube"

    tag_names: list[str] = []
    seen: set[str] = set()

    for part in parts[1:]:
        tag_name = part.strip()
        if not tag_name:
            continue

        # 用小写去重，避免 Runway / runway 重复。
        dedupe_key = tag_name.lower()
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        tag_names.append(tag_name)

    return clean_title, tag_names


def get_or_create_tag_id(name: str) -> int:
    """
    WordPress 创建文章时，tags 字段要传 tag ID，不是 tag 名称。
    所以这里先按名称搜索，找不到就创建。
    """
    clean_name = name.strip()
    if not clean_name:
        raise RuntimeError("Tag name cannot be empty")

    items = wp_get("tags", {"search": clean_name, "per_page": 100})

    for item in items:
        existing_name = str(item.get("name", "")).strip()
        if existing_name.lower() == clean_name.lower():
            return int(item["id"])

    created = wp_post("tags", {"name": clean_name})
    return int(created["id"])


def get_tag_ids(names: list[str]) -> list[int]:
    tag_ids: list[int] = []

    for name in names:
        tag_ids.append(get_or_create_tag_id(name))

    return tag_ids


def get_latest_youtube_video(channel_id: str, target_name: str) -> tuple[str, str]:
    feed_url = (
        "https://www.youtube.com/feeds/videos.xml"
        f"?channel_id={channel_id}"
    )

    feed = feedparser.parse(feed_url)

    if getattr(feed, "status", None) and feed.status != 200:
        raise RuntimeError(
            f"{target_name}: YouTube feed returned status {feed.status}: {feed_url}"
        )

    if getattr(feed, "bozo", False):
        print(
            f"{target_name}: feed parse warning: "
            f"{getattr(feed, 'bozo_exception', 'unknown')}"
        )

    if not feed.entries:
        raise RuntimeError(f"{target_name}: no YouTube videos found in feed: {feed_url}")

    latest = feed.entries[0]

    title = latest.get("title", "YouTube")
    video_id = latest.get("yt_videoid")

    if not video_id:
        link = latest.get("link", "")
        match = re.search(r"(?:v=|/shorts/)([^?&/]+)", link)
        if not match:
            raise RuntimeError(f"{target_name}: could not find video id from link: {link}")
        video_id = match.group(1)

    return title, video_id


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
<!-- wp:embed {{"url":"{escaped_url}","type":"video","providerNameSlug":"youtube","responsive":true,"className":"wp-embed-aspect-16-9 wp-has-aspect-ratio"}} -->
<figure class="wp-block-embed is-type-video is-provider-youtube wp-block-embed-youtube wp-embed-aspect-16-9 wp-has-aspect-ratio">
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
        f"category={category_slug} "
        f"tags={tag_names}"
    )


def main() -> None:
    category_cache: dict[str, int] = {}

    for target in TARGETS:
        publish_latest_for_target(target, category_cache)


if __name__ == "__main__":
    main()
