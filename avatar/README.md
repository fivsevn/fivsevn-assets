---
id: assets-avatar-readme
title: 头像素材

module: assets
submodule: guide
topic: null

type: note
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
- zh

maturity: evolving
confidence: null

visibility: public
source_of_truth: assets

filename_policy: entrypoint

created: null
updated: '2026-11-01'
---

# 头像素材

本目录存放用于不同平台和场景的个人头像图片。

---

## 文件格式
- **.jpg** → 通用主格式，与 WordPress、GitHub 和邮件客户端兼容性最好。  
- **.png** → 需要透明背景或清晰边缘时使用。  
- **.webp** → 适用于现代浏览器的可选优化格式；保留 `.jpg` 后备版本。  

色彩配置：**sRGB**  
建议 DPI：**72–96**（网页显示）

---

## 尺寸标准
| 用途 | 建议尺寸 | 说明 |
|-----------|------------------|-------|
| 原始母版 | 1024×1024 px | 作为可编辑的原始版本保留 |
| 网站 / CMS | 512×512 px | 兼顾清晰度和加载速度 |
| 社交平台 / GitHub | 400×400 px | 适合多数平台的默认显示尺寸 |
| 缩略图 / 网站图标 | 128×128 px | 用于小尺寸预览、元信息图片或图标 |

> ⚠️ 始终存档保留 **1024×1024** 母版。  
> 需要时从母版导出小尺寸版本，不要将缩小后的图片放大。

---

## 命名规则
- 文件名格式：  
  **`<section><YYYYMM><descriptor><size>.<ext>`**
  - 示例：`homepage202506banner1200.webp`
- 各部分含义：
  - **section** → 版块或页面名称（如 `homepage`、`avatar`、`links`）  
  - **YYYYMM** → 导出批次或更新年月（如 `202506`）  
  - **descriptor** → 内容类型（如 `banner`、`cover`、`bg`、`logo`）  
  - **size** → 主要宽度标识（可选，但便于识别）
- 只使用小写字母和数字，不使用空格或下划线。

> <模块><年月><描述><尺寸>  
> 示例：avatar202506main512.jpg、homepage202506banner1200.webp。  

---

## 注意事项
- 保持统一的取景和边距，避免社交平台自动裁切。  
- 文件大小保持在 **100–300 KB** 左右，以便快速加载。  
- 网页嵌入默认使用 JPG，WebP 作为性能优化的替代版本。
