import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
TARGET_DIR = "foodie/eastwindx1"

CATEGORY_SLUG = "foodie"
TAG_NAMES = ["daily", "东风一只"]

# 270px：260 偏小，280 偏大，取中间值。
IMAGE_SIZE_PX = 270


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


def get_changed_images() -> list[str]:
    before = os.environ.get("GITHUB_BEFORE", "").strip()
    after = os.environ.get("GITHUB_SHA", "HEAD").strip()

    if not before or before == "0000000000000000000000000000000000000000":
        output = run_git(["ls-files", TARGET_DIR])
        candidates = output.splitlines()
    else:
        output = run_git([
            "diff",
            "--name-status",
            before,
            after,
            "--",
            TARGET_DIR,
        ])

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

    images = []
    for path in candidates:
        p = Path(path)
        if (
            str(path).startswith(f"{TARGET_DIR}/")
            and p.suffix.lower() in IMAGE_EXTENSIONS
            and p.is_file()
        ):
            images.append(str(p))

    return sorted(set(images))


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
    if not items:
        raise RuntimeError(f"Category not found: {slug}")
    return int(items[0]["id"])


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
    return f"foodie-{safe}"


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


def make_square_image_block(image_url: str, title: str) -> str:
    size = IMAGE_SIZE_PX

    return f'''<!-- wp:html -->
<div class="foodie-photo-square" style="width:{size}px; height:{size}px; max-width:100%; overflow:hidden; margin:0 auto;">
  <img
    src="{image_url}"
    alt="{title}"
    loading="lazy"
    style="width:{size}px; height:{size}px; max-width:100%; object-fit:cover; display:block;"
  />
</div>
<!-- /wp:html -->'''


def publish_image(path: str, category_id: int, tag_ids: list[int]) -> None:
    dt = get_file_commit_time(path)
    title = format_title(dt)
    image_url = make_image_url(path)
    slug = make_post_slug(path)

    if post_already_exists(slug):
        print(f"Skip existing post: {path}")
        return

    content = make_square_image_block(image_url, title)

    payload = {
        "status": "publish",
        "title": title,
        "slug": slug,
        "content": content,
        "categories": [category_id],
        "tags": tag_ids,
    }

    post = wp_post("posts", payload)
    print(f"Published: {path} -> {post.get('link')}")


def main() -> None:
    images = get_changed_images()

    if not images:
        print("No new images found.")
        return

    category_id = get_category_id_by_slug(CATEGORY_SLUG)
    tag_ids = [get_or_create_tag_id(name) for name in TAG_NAMES]

    for image in images:
        publish_image(image, category_id, tag_ids)


if __name__ == "__main__":
    main()
