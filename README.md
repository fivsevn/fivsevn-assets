# fivsevn-assets

A repository for storing images and assets used in my blog: fivsevn.com

---
## update log

- 2026.06.06 新增 GitHub Actions 自动发图文：向指定目录上传图片后，会自动在 WordPress 创建对应分类的图片 post。
- 2026.05.23 新增`stills/`，整理一下库库。
- 2025.11.01 重构一下库库。
- 2025.03.29 我崭新的库库。

---
## image post automation

Some folders in this repository are used as image inboxes.  
When new image files are pushed into these folders, GitHub Actions will create WordPress posts automatically.

Supported image types:

```text
.jpg / .jpeg / .png / .webp / .gif
```

Current rules:

| GitHub folder | WordPress category | WordPress tags | Post content |
|---|---|---|---|
| `foodie/eastwindx1/` | `foodie` | `daily`, `东风一只bowl` | one image block |
| `foodie/byme/` | `foodie` | `daily`, `史诗级大厨` | one image block |
| `foodie/nothomecooked/` | `foodie` | `daily` | one image block |
| `natsci/fieldlog/` | `fieldlog` | none | one image block |
| `post/stream/` | `posts` | none | one image block |

Notes:

- Each uploaded image becomes one separate WordPress post.
- The post title uses the image commit time, formatted like `06 Jun, 2026 05:51`.
- The image itself stays in this GitHub repository and is inserted into WordPress through the CDN URL.
- WordPress does not upload the image into the Media Library.
- The generated content is a native WordPress image block.
- `foodie` images use the `foodie-photo-square` class so they can be displayed as square images through WordPress Additional CSS.
- `fieldlog` and `stream` images use the default WordPress image block style.

The automation files are:

```text
.github/workflows/publish-image-posts.yml
scripts/publish_image_posts.py
```

---
## structure
  
```
fivsevn-assets/
├── homepage/
│   ├── ...
│   ├── homepage20251101head.webp
│   ├── homepage20251101nvesvif.webp
│   └── homepage20251105bio.webp
├── avatar/
│   ├── ...
│   ├── avatar202511dev512.png
│   ├── avatar202511main512.png
│   └── avatar202511nvesvif512.png
├── pages/
│   ├── ...
│   └── 57store/
│       ├── ...
│       └── ...
├── foodie/
│   ├── eastwindx1/
│   │   ├── .keep
│   │   └── xxx.jpg
│   ├── byme/
│   │   ├── .keep
│   │   └── xxx.jpg
│   └── nothomecooked/
│       ├── .keep
│       └── xxx.jpg
├── natsci/
│   └── fieldlog/
│       ├── .keep
│       └── xxx.jpg
├── post/
│   ├── stream/
│   │   ├── .keep
│   │   └── xxx.jpg
│   ├── 2026/
│   │   ├── 202602/
│   │   │   ├── ...
│   │   │   ├── xxx.jpg
│   │   │   ├── xxx.webp
│   │   └── 202601/
│   │       ├── ...
│   │       └── xxx.png
│   └── 2025/
│       ├── 202504/
│       │   ├── ...
│       │   ├── 20250408streetlight.mp4
│       │   └── 20250403pigpdevlog.jpeg
│       └── 202503/
│           ├── ...
│           └── 20250331corpus.jpeg
├── stills/
│   ├── ...
│   └── 20190406originalfivsevn/
│       └── ...
├── scripts/
│   └── publish_image_posts.py
└── .github/
    └── workflows/
        └── publish-image-posts.yml
```
