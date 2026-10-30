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
│   ├── publish_youtube_posts.py
│   └── youtube_source.py
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

This repository synchronizes public uploads from the `fivsevn` YouTube channel to WordPress. It scans the complete official uploads playlist, including continuation pages, so multiple uploads between runs and older missed videos can all be synchronized.

The maintained files are [`.github/workflows/publish-youtube-posts.yml`](.github/workflows/publish-youtube-posts.yml), [`scripts/publish_youtube_posts.py`](scripts/publish_youtube_posts.py), and [`scripts/youtube_source.py`](scripts/youtube_source.py).

The workflow runs hourly (`0 * * * *`), supports manual runs from GitHub Actions, and runs when the publisher, its source reader, `tests/test_youtube_*.py`, or the workflow itself changes on `main`. These triggers share one concurrency group to prevent overlapping publishers. Each run has a 20-minute timeout, sets up Python 3.11, installs `requests` and `feedparser`, and runs the YouTube tests before publishing:

```sh
python -m unittest discover -s tests -p 'test_youtube_*.py' -v
python scripts/publish_youtube_posts.py
```

The script reads these GitHub Actions secrets or environment variables:

```text
WP_BASE_URL
WP_USERNAME
WP_APP_PASSWORD
YOUTUBE_FIVSEVN_CHANNEL_ID
```

`YOUTUBE_FIVSEVN_CHANNEL_ID` must contain the full `UC...` channel ID.

### current rules

| YouTube channel | WordPress category | Post format | Post content |
|---|---|---|---|
| `fivsevn` | `motion` | `video` | one YouTube embed block |

### how it works

1. Read and verify the configured channel's complete official uploads playlist, following every continuation page.
2. Read the YouTube RSS entries for titles and original publication timestamps. The feed's top-level channel ID may omit its `UC` prefix; both official forms are accepted for the configured channel.
3. Read existing WordPress posts with `publish`, `draft`, `private`, `future`, and `pending` status. Match both the generated slug and embedded video IDs, including older articles with custom slugs. Existing drafts and other unpublished posts are preserved.
4. For each missing video without complete RSS metadata, read its official watch page, verify its video ID and channel, and obtain the original publication timestamp. If playback metadata is unavailable, verify the page's SEO video identifier against its current video endpoint and the main content's owner channel before using its exact `datePublished` metadata.
5. Finish reading and validating metadata for every missing video before creating any posts.
6. Publish missing videos from oldest to newest, setting WordPress `date_gmt` to the original YouTube publication time in UTC. Use a stable `youtube-<lowercase-video-id>` slug, the `motion` category, `video` format, and one native WordPress YouTube embed block.

To inspect the complete publishing plan without writing to WordPress, use the same environment variables and run:

```sh
python scripts/publish_youtube_posts.py --dry-run
```

### notes

* Multiple videos with the same title are distinct uploads and are matched by video ID.
* Hashtags in YouTube titles become WordPress tags and are removed from the article title.
* YouTube Shorts URLs are normalized into regular `watch?v=` URLs. The video stays on YouTube; WordPress stores the embed block.
* YouTube HTTP-200 error or consent pages without usable initial data are retried with 5/15/30-second waits before failing.
* YouTube page layouts and channel identity are validated. Incomplete reads or invalid metadata fail the run visibly before publishing; no extra API key or third-party mirror is used.
* WordPress requests share a 1.5-second minimum start interval. GET requests retry transient failures up to four times with 5/15/30/60-second backoff, honoring `Retry-After` seconds or dates. A requested wait longer than five minutes fails visibly for a later run.
* WordPress writes are not automatically retried. Later runs check existing video IDs and slugs again, so they can continue after a partially completed run without republishing successful posts.


---
## editing note

The current WordPress automations create Gutenberg block markup: an image block for Bygone and a YouTube embed block for Motion. Later edits should preserve those block structures, preferably through the WordPress block editor.

For local offline checks:

```sh
python -m pip install requests feedparser
python -m unittest discover -s tests -v
```
