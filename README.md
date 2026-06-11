# fivsevn-assets

- A repository for storing images and assets used in my blog: fivsevn.com

---
## update log

- 2026.06.07 新增 GitHub Actions 自动发图和视频同步。
  - 自动发图 [image post automation](#image-post-automation)
  - 视频同步 [YouTube post automation](#youtube-post-automation)
  - ⚠️备忘 [editing note](#editing-note)
- 2026.05.23 新增 `stills/`，整理一下库库。
- 2025.11.01 重构一下库库。
- 2025.03.29 我崭新的库库。

---
## repository structure

- This repository stores static assets for fivsevn.com and related surfaces.

```text
fivsevn-assets/
├── homepage/
│   ├── ...
│   ├── homepage20251101head.webp
│   ├── homepage20251105bio.webp
│   └── homepage20260531motion.webp
├── avatar/
│   ├── ...
│   ├── avatar202511main512.png
│   ├── avatar20260225whow.webp
│   └── avatar202603fragment169.webp
├── common/
│   ├── ...
│   └── icon/
│       ├── ...
│       ├── discord.png
│       └── youtube.png
├── pages/
│   ├── ...
│   └── 57store/
│       ├── ...
│       ├── 57store20260224f.webp
│       └── 57store20260224p.webp
├── foodie/
│   ├── eastwindx1/
│   │   ├── ...
│   │   ├── IMG_6820.JPG
│   │   └── IMG_6851.WEBP
│   ├── byme/
│   │   ├── ...
│   │   └── IMG_6827.JPG
│   └── nothomecooked/
│       ├── ...
│       └── IMG_6825.JPG
├── natsci/
│   └── fieldlog/
│       ├── ...
│       ├── IMG_6852.JPG
│       └── IMG_6856.JPG
├── post/
│   ├── stream/
│   │   ├── ...
│   │   ├── IMG_6858.GIF
│   │   └── IMG_6891.PNG
│   ├── 2026/
│   │   └── 202605/
│   │       ├── ...
│   │       ├── IMG_6880.JPG
│   │       └── IMG_6885.PNG
│   └── 2025/
│       ├── 202504/
│       │   ├── ...
│       │   ├── 20250403pigpdevlog.jpeg
│       │   └── 20250421concreteutilitypole1.jpg
│       └── 202503/
│           ├── ...
│           ├── 20250313poirotgoestoegyptalexandria.JPG
│           └── 20250331corpus.jpeg
├── stills/
│   ├── ...
│   ├── bygone/
│   │   └── ...
│   └── 20190406originalfivsevn/
│       └── ...
├── scripts/
│   ├── ...
│   ├── publish_image_posts.py
│   └── publish_youtube_posts.py
└── .github/
    ├── ...
    └── workflows/
        ├── ...
        ├── publish-image-posts.yml
        └── publish-youtube-posts.yml
```

---
## image post automation

- Some folders in this repository are used as image inboxes.

- When new image files are pushed into these folders, GitHub Actions will create WordPress posts automatically.

- Supported image types:

```text
.jpg / .jpeg / .png / .webp / .gif
```

### current rules

| GitHub folder | WordPress category | WordPress tags | Post content |
|---|---|---|---|
| `foodie/eastwindx1/` | `foodie` | `daily`, `东风一只bowl` | one image block |
| `foodie/byme/` | `foodie` | `daily`, `史诗级大厨` | one image block |
| `foodie/nothomecooked/` | `foodie` | `daily` | one image block |
| `natsci/fieldlog/` | `fieldlog` | none | one image block |
| `post/stream/` | `posts` | none | one image block |
| `stills/bygone/` | `posts` | none | one image block |

### how it works

- The automation is split into two files:

```text
.github/workflows/publish-image-posts.yml  
scripts/publish_image_posts.py  
```

- The workflow runs on pushes to main, but only when files under these paths change:

```text
foodie/eastwindx1/**  
foodie/byme/**  
foodie/nothomecooked/**  
natsci/fieldlog/**  
post/stream/**
stills/bygone/**  
```

- The workflow checks out the repository with full Git history, sets up Python 3.11, installs requests, and then runs:

```text
python scripts/publish_image_posts.py  
```

- The script reads the following GitHub Actions secrets / environment variables:

```text
WP_BASE_URL  
WP_USERNAME  
WP_APP_PASSWORD  
CDN_BASE_URL  
TITLE_TIMEZONE  
GITHUB_BEFORE  
GITHUB_SHA  
```

### Basic publishing flow

1. Detect changed files between GITHUB_BEFORE and GITHUB_SHA.
2. Keep only supported image files inside configured target folders.
3. Match each image path to its WordPress category, tags, and optional image class.
4. Read the image file’s latest commit time.
5. Use that commit time as the WordPress post title, formatted like:

```
06 Jun, 2026 05:51  
```

6. Build the image URL from CDN_BASE_URL plus the repository path.
7. Generate a stable WordPress slug from the image path.
8. Skip publishing if a post with the same slug already exists.
9. Resolve the WordPress category by slug.
10. Find or create required WordPress tags.
11. Create a published WordPress post through the WordPress REST API.

### notes

* Each uploaded image becomes one separate WordPress post.
* The post title uses the image commit time, formatted like 06 Jun, 2026 05:51.
* The image itself stays in this GitHub repository and is inserted into WordPress through the CDN URL.
* WordPress does not upload the image into the Media Library.
* The generated content is a native WordPress image block.
* foodie images use the foodie-photo-square class so they can be displayed as square images through WordPress Additional CSS.
* fieldlog and stream images use the default WordPress image block style.
* Duplicate publishing is prevented by checking whether a WordPress post with the generated slug already exists.

---
## YouTube post automation

- This repository also includes a scheduled YouTube-to-WordPress automation.

- The automation is split into two files:

```text
.github/workflows/publish-youtube-posts.yml  
scripts/publish_youtube_posts.py  
```

- The workflow runs once every hour and can also be triggered manually from GitHub Actions.

```text
0 * * * *
```

- The workflow sets up Python 3.11, installs `requests` and `feedparser`, and then runs:

```text
python scripts/publish_youtube_posts.py
```

- The script reads the following GitHub Actions secrets / environment variables:

```text
WP_BASE_URL  
WP_USERNAME  
WP_APP_PASSWORD  
YOUTUBE_57STORE_CHANNEL_ID  
YOUTUBE_FIVSEVN_CHANNEL_ID  
```

### current rules

| YouTube channel | WordPress category | Post format | Post content |
|---|---|---|---|
| `57store.fivsevn` | `57storecctv` | `video` | one YouTube embed block |
| `fivsevn` | `motion` | `video` | one YouTube embed block |

### how it works

Basic publishing flow:

1. Read the configured YouTube channel IDs from GitHub Actions secrets.
2. Fetch each channel’s latest video from the YouTube RSS feed.
3. Extract the video title and video ID.
4. Normalize the video URL into a regular YouTube watch URL, like:

```text
https://www.youtube.com/watch?v=VIDEO_ID  
```

5. Generate a stable WordPress slug from the video ID, like:

```text
youtube-VIDEO_ID  
```

6. Skip publishing if a WordPress post with the same slug already exists.
7. Resolve the target WordPress category by slug.
8. Create a published WordPress post through the WordPress REST API.
9. Insert the video as a native WordPress YouTube embed block.

### notes

* The automation only publishes the latest video from each configured YouTube channel.
* Duplicate publishing is prevented by checking whether a WordPress post with the generated YouTube slug already exists.
* YouTube Shorts URLs are normalized into regular `watch?v=` URLs before being inserted into WordPress.
* The video itself stays on YouTube; WordPress only stores the embed block.
* `57store.fivsevn` videos are published to the `57storecctv` category.
* `fivsevn` videos are published to the `motion` category.

---
## editing note

- ⚠️ 自动化发布到 WordPress 时，脚本不是直接塞普通 HTML，而是生成 WordPress / Gutenberg 识别的 block markup，比如 image block 和 YouTube embed block；这样图片尺寸更好控制，视频嵌入效果也比手写 HTML 更稳定，后续最好继续用 WordPress 区块编辑器修改。

The automation writes WordPress block markup directly into the `content` field of the WordPress REST API payload.

For image posts, the script uses a native WordPress image block instead of plain HTML:

```python
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
```

For YouTube posts, the script uses a native WordPress YouTube embed block:

```python
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
```

These blocks are then passed into the WordPress post payload as `content`:

```python
content = make_image_block(image_url, title, image_class)

payload = {
    "status": "publish",
    "title": title,
    "slug": slug,
    "content": content,
    "categories": [category_id],
}
```

```python
content = make_youtube_embed_block(video_url)

payload = {
    "status": "publish",
    "title": title,
    "slug": slug,
    "content": content,
    "categories": [category_id],
    "format": "video",
}
```

This means the automation is not simply inserting raw HTML. It is creating content in the same block format that WordPress / Gutenberg expects.

This is important because:

* Image size and layout are easier to control when the image is a WordPress image block.
* YouTube videos render more reliably as native YouTube embed blocks than as manually written HTML embeds.
* Later edits should be made in the WordPress block editor / Gutenberg editor, so the generated block structure is preserved.
* Manually rewriting the generated markup as plain HTML may break the expected block structure or make later visual editing less predictable.

