---
id: assets-readme
title: fivsevn-assets

module: assets
submodule: guide
topic: null

type: index
status: active
canonical: true

summary: null

parents: []
related: []

tags: []

audience:
- self
- internal
languages:
- en

maturity: evolving
confidence: null

visibility: public
source_of_truth: assets

filename_policy: entrypoint

created: null
updated: '2026-11-01'
metadata_updated: '2026-11-01'
---

# fivsevn-assets

Shared images for [fivsevn.com](https://fivsevn.com/): homepage artwork, avatars, icons, page illustrations and dated article assets. Existing shared asset paths remain stable for their consumers.

## Source layout

| Path | Content |
|---|---|
| `homepage/` | Homepage and navigation artwork |
| `avatar/` | Reused profile images |
| `common/` | Shared images and icons |
| `pages/` | Assets used by individual pages |
| `post/YYYY/` | Article illustrations |
| `docs/` | Saved shortcut reference |

Upload or replace a shared asset in its existing directory and update the consuming page if its path changes. The public repository can be referenced by raw GitHub or CDN URLs. A commit updates the stored asset; it does not create a blog post. There are no publishing Actions in this repository.

## Content publishing

| Board | Repository | Publishing entry |
|---|---|---|
| Flux | [fivsevn-flux](https://github.com/fivsevn/fivsevn-flux) | `trigger_text.md`, `trigger_imgs/` |
| Savour | [fivsevn-savour](https://github.com/fivsevn/fivsevn-savour) | `trigger_imgs/` |
| Fieldlog | [fivsevn-devlog](https://github.com/fivsevn-agy/fivsevn-devlog) | `natsci/fieldlog/trigger_imgs/` |
| Stills | [fivsevn-roll](https://github.com/fivsevn/fivsevn-roll) | `stills/trigger_imgs/` |
| Motion | [fivsevn-roll](https://github.com/fivsevn/fivsevn-roll) | YouTube public uploads |

Each content repository owns its saved packages, image naming, upload state and deployment. Follow its publishing guide when configuring Working Copy or phone shortcuts. Shared assets use their existing naming; publication packages follow the [media naming contract](https://github.com/fivsevn-agy/fivsevn-spec/blob/main/content/spec-content-media-naming-001.md).

## update log

- 2026.10.29 savour 图片与发布流程由 [fivsevn-savour](https://github.com/fivsevn/fivsevn-savour) 管理。
- 2026.10.18 flux 图片与文字已统一迁至 [fivsevn-flux](https://github.com/fivsevn/fivsevn-flux)，后续在该仓库发布和管理。
- 2026.06.11 `post/flux/`（原 `post/stream/`） 和 `natsci/fieldlog/` 支持从 commit extended description 生成图片下方正文。
- 2026.06.07 新增 GitHub Actions 自动发图和视频同步。
  - 自动发图 [image post automation](#image-post-automation)
  - 视频同步 [YouTube post automation](#youtube-post-automation)
  - ⚠️备忘 [editing note](#editing-note)
- 2026.05.23 新增 `stills/`，整理一下库库。
- 2025.11.01 重构一下库库。
- 2025.03.29 我崭新的库库。
