import html
import os
import re
import sys

import feedparser
import requests


# 固定发布到 WordPress 分类 slug：57storecctv
# 对应 WordPress 后台 Posts → Categories 里面的 slug。
CATEGORY_SLUG = "57storecctv"


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value.rstrip("/") if name.endswith("URL") else value


WP_BASE_URL = env("WP_BASE_URL")
WP_USERNAME = env("WP_USERNAME")
WP_APP_PASSWORD = env("WP_APP_PASSWORD")
YOUTUBE_CHANNEL_ID = env("YOUTUBE_CHANNEL_ID")

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


def get_category_id_by_slug(slug: str) -> int:
    items = wp_get("categories", {"slug": slug, "per_page": 100})
    if items:
        return int(items[0]["id"])

    raise RuntimeError(f"Category not found by slug: {slug}")


def get_latest_youtube_video() -> tuple[str, str]:
    feed_url = (
        "https://www.youtube.com/feeds/videos.xml"
        f"?channel_id={YOUTUBE_CHANNEL_ID}"
    )
    feed = feedparser.parse(feed_url)

    if not feed.entries:
        raise RuntimeError("No YouTube videos found in feed.")

    latest = feed.entries[0]
    title = latest.get("title", "YouTube")

    video_id = latest.get("yt_videoid")
    if not video_id:
        link = latest.get("link", "")
        match = re.search(r"v=([^&]+)", link)
        if not match:
            raise RuntimeError(f"Could not find video id from link: {link}")
        video_id = match.group(1)

    return title, video_id


def make_video_url(video_id: str) -> str:
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

    return f'''<!-- wp:embed {{"url":"{escaped_url}","type":"video","providerNameSlug":"youtube","responsive":false,"className":"wp-embed-aspect-16-9 wp-has-aspect-ratio"}} -->
<figure class="wp-block-embed is-type-video is-provider-youtube wp-block-embed-youtube wp-embed-aspect-16-9 wp-has-aspect-ratio"><div class="wp-block-embed__wrapper">
{escaped_url}
</div></figure>
<!-- /wp:embed -->'''


def main() -> None:
    title, video_id = get_latest_youtube_video()
    video_url = make_video_url(video_id)
    slug = make_post_slug(video_id)

    if post_already_exists(slug):
        print(f"Skip existing YouTube post: {title} ({video_url})")
        return

    category_id = get_category_id_by_slug(CATEGORY_SLUG)
    content = make_youtube_embed_block(video_url)

    payload = {
        "status": "publish",
        "title": title,
        "slug": slug,
        "content": content,
        "categories": [category_id],
        "format": "video",
    }

    post = wp_post("posts", payload)
    print(f"Published YouTube post: {title} -> {post.get('link')}")


if __name__ == "__main__":
    main()
