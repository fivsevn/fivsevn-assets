# fivsevn-assets

Static images and shared assets used by [fivsevn.com](https://fivsevn.com/), plus the current Bygone image and YouTube publishing automations.

---
## update log

- 2026.10.29 Savour 图片与发布流程由 [fivsevn-savour](https://github.com/fivsevn/fivsevn-savour) 管理。
- 2026.10.18 flux 图片与文字已统一迁至 [fivsevn-flux](https://github.com/fivsevn/fivsevn-flux)，后续在该仓库发布和管理。
- 2026.06.11 `post/flux/`（原 `post/stream/`） 和 `natsci/fieldlog/` 支持从 commit extended description 生成图片下方正文。
- 2026.06.07 新增 GitHub Actions 自动发图和视频同步。
  - 自动发图 [image post automation](#image-post-automation)
  - 视频同步 [YouTube post automation](#youtube-post-automation)
  - ⚠️备忘 [editing note](#editing-note)
- 2026.05.23 新增 `stills/`，整理一下库库。
- 2025.11.01 重构一下库库。
- 2025.03.29 我崭新的库库。

---
## repository structure

```text
fivsevn-assets/
├── homepage/                    Shared homepage images
├── avatar/                      Avatar assets
├── common/                      Common images and icons
├── pages/                       Assets for individual pages
├── post/                        Dated article-image archives
├── stills/                      Photography assets
│   └── bygone/                  Current WordPress image publishing input
├── docs/                        Saved shortcut file
├── scripts/
│   ├── publish_image_posts.py
│   └── publish_youtube_posts.py
├── tests/                       Offline publishing checks
└── .github/workflows/
    ├── publish-image-posts.yml
    └── publish-youtube-posts.yml
```

## independent boards

These boards own their content, upload inputs, and GitHub Pages publishing. They do not use this repository as a publishing input.

| Board | Content repository | Image input | Public page |
|---|---|---|---|
| Flux | [fivsevn-flux](https://github.com/fivsevn/fivsevn-flux) | [`trigger_imgs/`](https://github.com/fivsevn/fivsevn-flux/tree/main/trigger_imgs) | [flux.fivsevn.com](https://flux.fivsevn.com/) |
| Savour | [fivsevn-savour](https://github.com/fivsevn/fivsevn-savour) | [`trigger_imgs/`](https://github.com/fivsevn/fivsevn-savour/tree/main/trigger_imgs) | [savour.fivsevn.com](https://savour.fivsevn.com/) |
| Fieldlog | [fivsevn-devlog](https://github.com/fivsevn-agy/fivsevn-devlog) | [`natsci/fieldlog/trigger_imgs/`](https://github.com/fivsevn-agy/fivsevn-devlog/tree/main/natsci/fieldlog/trigger_imgs) | [devlog.fivsevn.com/natsci/fieldlog/](https://devlog.fivsevn.com/natsci/fieldlog/) |

Use each board's current README when configuring Working Copy or a phone shortcut. The saved signed shortcut in `docs/` is not the current configuration guide for these independent boards.

---
## image post automation

The current image publishing target is **`stills/bygone/` only**. Flux, Savour, and Fieldlog uploads are ignored by this publisher.

| GitHub folder | WordPress category | WordPress tags | Title | Post content |
|---|---|---|---|---|
| `stills/bygone/` | `bygone` | none | Filename, with underscores and hyphens replaced by spaces | One native WordPress image block |

Supported inputs are `.jpg`, `.jpeg`, `.png`, `.webp`, and `.gif`, with case-insensitive extensions. Images remain in this repository and are referenced through `CDN_BASE_URL`; they are not uploaded into the WordPress Media Library.

The two maintained files are [`.github/workflows/publish-image-posts.yml`](.github/workflows/publish-image-posts.yml) and [`scripts/publish_image_posts.py`](scripts/publish_image_posts.py). The workflow starts for Bygone image changes or changes to the publisher, its tests, or the workflow itself. It checks out complete Git history, installs `requests`, runs offline target/payload tests, then runs the publisher.

The publisher reads `WP_BASE_URL`, `WP_USERNAME`, `WP_APP_PASSWORD`, and `CDN_BASE_URL`, together with the event's `GITHUB_BEFORE` and `GITHUB_SHA`. `TITLE_TIMEZONE` is retained as an optional setting for the generic commit-time title helper; the current Bygone target uses filenames.

Publishing steps:

1. Read changed paths between the push's before and after commits.
2. Keep existing supported images inside `stills/bygone/`.
3. Build the filename title, CDN image URL, and stable path-derived post slug.
4. Skip a post when that slug already exists.
5. Resolve the `bygone` category and create a published WordPress post containing its native image block.

Deleting an asset does not delete a WordPress post. Edit or remove existing Bygone posts in WordPress, and retain their referenced media while they remain in use.

---
## YouTube post automation

- This repository includes a scheduled YouTube-to-WordPress automation for the `fivsevn` channel.

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
YOUTUBE_FIVSEVN_CHANNEL_ID  
```

### current rules

| YouTube channel | WordPress category | Post format | Post content |
|---|---|---|---|
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

* The automation only publishes the latest video from the configured YouTube channel.
* Duplicate publishing is prevented by checking whether a WordPress post with the generated YouTube slug already exists.
* YouTube Shorts URLs are normalized into regular `watch?v=` URLs before being inserted into WordPress.
* The video itself stays on YouTube; WordPress only stores the embed block.
* `fivsevn` videos are published to the `motion` category.
* Reads have a 10-second connection timeout and a 30-second read timeout. If RSS returns 404/408/429/5xx, a network error, malformed data, or no videos, the script checks the same channel's official public uploads playlist page. It verifies the playlist ID and owner before selecting the first public upload, supports Shorts and regular videos, and rejects unknown page layouts rather than choosing an older or unrelated video. No extra key or third-party mirror is used.
* If both sources fail, reads are retried up to four rounds, with waits of 5, 15, and 30 seconds. Exhausted retries fail the run visibly; they are not treated as successful synchronization. The public-page fallback depends on YouTube's page structure; the offline tests cover the supported layouts.
* Scheduled and manual YouTube runs are serialized to avoid concurrent duplicate posts. WordPress writes are not automatically retried. The hourly schedule, latest-video rule, category, title tags, and embed format are unchanged.


---
## editing note

The current WordPress automations create Gutenberg block markup: an image block for Bygone and a YouTube embed block for Motion. Later edits should preserve those block structures, preferably through the WordPress block editor.

For local offline checks:

```sh
python -m pip install requests feedparser
python -m unittest discover -s tests -v
```
