import html
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# 不同目录对应不同 WordPress 分类、tags、图片 class。
# category_slug 对应 WordPress 后台里的 slug。
# image_class 为空时，不额外加 class，走 WordPress 默认 image block 样式。
TARGETS = {
    "foodie/eastwindx1": {
        "category_slug": "foodie",
        "tags": ["daily", "东风一只bowl"],
        "image_class": "foodie-photo-square",
    },
    "foodie/byme": {
        "category_slug": "foodie",
        "tags": ["daily", "史诗级大厨"],
        "image_class": "foodie-photo-square",
    },
    "foodie/nothomecooked": {
        "category_slug": "foodie",
        "tags": ["daily"],
        "image_class": "foodie-photo-square",
    },
    "natsci/fieldlog": {
        "category_slug": "fieldlog",
        "tags": [],
        "image_class": "",
    },
    "post/stream": {
        "category_slug": "posts",
        "tags": [],
        "image_class": "",
    },
    "stills/bygone": {
        "category_slug": "bygone",
        "tags": [],
        "image_class": "",
    },
}


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()

    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")

    return value.rstrip("/") if name.endswith("URL") else value


WP_BASE_URL = env("WP_BASE_URL")
WP_USERNAME = env("WP_USERNAME")
WP_APP_PASSWORD = env("WP_APP_PASSWORD")
CDN_BASE_URL = env("CDN_BASE_URL")
TITLE_TIMEZONE = os.environ.get("TITLE_TIMEZONE", "Asia/Tokyo").strip() or "Asia/Tokyo"

AUTH = (WP_USERNAME, WP_APP_PASSWORD)


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    return result.stdout.strip()


def is_target_image(path: str) -> bool:
    p = Path(path)

    if p.suffix.lower() not in IMAGE_EXTENSIONS:
        return False

    if not p.is_file():
        return False

    return any(path.startswith(f"{target_dir}/") for target_dir in TARGETS.keys())


def get_changed_images() -> list[str]:
    before = os.environ.get("GITHUB_BEFORE", "").strip()
    after = os.environ.get("GITHUB_SHA", "HEAD").strip()
    target_dirs = list(TARGETS.keys())

    if not before or before == "0000000000000000000000000000000000000000":
        candidates = []

        for target_dir in target_dirs:
            output = run_git(["ls-files", target_dir])
            candidates.extend(output.splitlines())
    else:
        output = run_git(
            [
                "diff",
                "--name-status",
                before,
                after,
                "--",
                *target_dirs,
            ]
        )

        candidates = []

        for line in output.splitlines():
            parts = line.split("\t")

            if not parts:
                continue

            status = parts[0]

            if status.startswith("D"):
                continue

            path = parts[-1]
            candidates.append(path)

    images = [path for path in candidates if is_target_image(path)]

    return sorted(set(images))


def get_target_dir_for_path(path: str) -> str:
    for target_dir in TARGETS.keys():
        if path.startswith(f"{target_dir}/"):
            return target_dir

    raise RuntimeError(f"No target config found for path: {path}")


def get_config_for_path(path: str) -> dict:
    target_dir = get_target_dir_for_path(path)

    return TARGETS[target_dir]


def get_file_commit_time(path: str) -> datetime:
    iso_time = run_git(["log", "-1", "--format=%cI", "--", path])
    dt = datetime.fromisoformat(iso_time)

    return dt.astimezone(ZoneInfo(TITLE_TIMEZONE))


def format_title(dt: datetime) -> str:
    # 例：06 Jun, 2026 05:51
    return dt.strftime("%d %b, %Y %H:%M")


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
    response.raise_for_status()

    return response.json()


def get_category_id_by_slug(slug: str) -> int:
    items = wp_get("categories", {"slug": slug, "per_page": 100})

    if items:
        return int(items[0]["id"])

    items = wp_get("categories", {"search": slug, "per_page": 100})

    for item in items:
        if item.get("slug") == slug:
            return int(item["id"])

    for item in items:
        if item.get("name") == slug:
            return int(item["id"])

    available = [
        f'{item.get("name")} ({item.get("slug")})'
        for item in items
    ]

    raise RuntimeError(
        f"Category not found: {slug}. Search results: {available}"
    )


def get_or_create_tag_id(name: str) -> int:
    items = wp_get("tags", {"search": name, "per_page": 100})

    for item in items:
        if item.get("name") == name:
            return int(item["id"])

    created = wp_post("tags", {"name": name})

    return int(created["id"])


def make_post_slug(path: str) -> str:
    safe = (
        path.lower()
        .replace("/", "-")
        .replace("_", "-")
        .replace(".", "-")
    )

    return f"asset-{safe}"


def post_already_exists(slug: str) -> bool:
    items = wp_get(
        "posts",
        {
            "slug": slug,
            "status": "publish,draft,private",
            "per_page": 10,
        },
    )

    return bool(items)


def make_image_url(path: str) -> str:
    return f"{CDN_BASE_URL}/{path}"


def make_image_block(image_url: str, title: str, image_class: str) -> str:
    escaped_url = html.escape(image_url, quote=True)
    escaped_title = html.escape(title, quote=True)
    escaped_class = html.escape(image_class, quote=True)

    if image_class:
        return f'''<!-- wp:image {{"url":"{escaped_url}","alt":"{escaped_title}","linkDestination":"none","className":"{escaped_class}"}} -->
<figure class="wp-block-image {escaped_class}">
    <img src="{escaped_url}" alt="{escaped_title}" />
</figure>
<!-- /wp:image -->'''

    return f'''<!-- wp:image {{"url":"{escaped_url}","alt":"{escaped_title}","linkDestination":"none"}} -->
<figure class="wp-block-image">
    <img src="{escaped_url}" alt="{escaped_title}" />
</figure>
<!-- /wp:image -->'''


def publish_image(
    path: str,
    category_cache: dict[str, int],
    tag_cache: dict[str, int],
) -> None:
    config = get_config_for_path(path)

    category_slug = config["category_slug"]
    tag_names = config["tags"]
    image_class = config["image_class"]

    dt = get_file_commit_time(path)
    title = format_title(dt)
    image_url = make_image_url(path)
    slug = make_post_slug(path)

    if post_already_exists(slug):
        print(f"Skip existing post: {path}")
        return

    if category_slug not in category_cache:
        category_cache[category_slug] = get_category_id_by_slug(category_slug)

    category_id = category_cache[category_slug]

    tag_ids = []

    for tag_name in tag_names:
        if tag_name not in tag_cache:
            tag_cache[tag_name] = get_or_create_tag_id(tag_name)

        tag_ids.append(tag_cache[tag_name])

    content = make_image_block(image_url, title, image_class)

    payload = {
        "status": "publish",
        "title": title,
        "slug": slug,
        "content": content,
        "categories": [category_id],
    }

    if tag_ids:
        payload["tags"] = tag_ids

    post = wp_post("posts", payload)

    print(
        f"Published: {path} -> {post.get('link')} "
        f"category={category_slug} tags={tag_names}"
    )


def main() -> None:
    images = get_changed_images()

    if not images:
        print("No new images found.")
        return

    category_cache: dict[str, int] = {}
    tag_cache: dict[str, int] = {}

    for image in images:
        publish_image(image, category_cache, tag_cache)


if __name__ == "__main__":
    main()
