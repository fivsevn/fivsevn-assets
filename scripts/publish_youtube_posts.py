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

if not YOUTUBE_CHANNEL_ID.startswith("UC"):
    raise RuntimeError(
        "YOUTUBE_CHANNEL_ID must be the UC... channel id only, "
        "not a handle or URL. "
        f"Current value starts with: {YOUTUBE_CHANNEL_ID[:30]}"
    )

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

    print(f"YOUTUBE_CHANNEL_ID starts with: {YOUTUBE_CHANNEL_ID[:12]}...")
    print(f"Feed URL: {feed_url}")

    feed = feedparser.parse(feed_url)

    print(f"Feed status: {getattr(feed, 'status', 'unknown')}")
    print(f"Feed bozo: {getattr(feed, 'bozo', 'unknown')}")
    print(f"Feed href: {getattr(feed, 'href', 'unknown')}")
    print(f"Feed entries count: {len(feed.entries)}")

    if getattr(feed, "bozo", False):
        print(f"Feed bozo exception: {getattr(feed, 'bozo_exception', 'unknown')}")

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

    print(f"Latest video title: {title}")
    print(f"Latest video id: {video_id}")

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

    return f'''<!-- wp:embed {{"url":"{escaped_url}","type":"video","providerNameSlug":"youtube","responsive":false}} -->
<figure class="wp-block-embed is-type-video is-provider-youtube wp-block-embed-youtube"><div class="wp-block-embed__wrapper">
{escaped_url}
</div></figure>
<!-- /wp:embed -->'''


def main() -> None:
    title, video_id = get_latest_youtube_video()
    video_url = make_video_url(video_id)
    slug = make_post_slug(video_id)

    print(f"Post slug: {slug}")
    print(f"Video URL: {video_url}")

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
