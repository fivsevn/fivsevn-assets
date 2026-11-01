---
id: assets-homepage-readme
title: 主页素材

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

# 主页素材

本目录存放网站主页专用的图片，包括横幅、主视觉区域及背景图片。

---

## 文件格式
- **.webp** → 主横幅和主视觉图片的推荐格式，压缩效率较高。  
- **.jpg** → 需要广泛兼容性的摄影图片。  
- **.png** → 带透明背景的叠加图片或图形元素。  
- **.svg** → 标志、几何图标等矢量图片。  

色彩配置：**sRGB**  
建议 DPI：**72–96**（网页标准）

---

## 尺寸标准
| 用途 | 建议宽度 | 说明 |
|-----------|------------------|-------|
| 主横幅 / 主视觉 | **1200 px** | 适合多数设备的主要布局宽度 |
| 大屏版本 | **1600–1920 px** | 用于 Retina 或全宽布局 |
| 手机 / 紧凑布局 | **800 px** | 可选的移动端优化导出版本 |
| 背景纹理 | 按需设置 | 应能自然平铺或渐变衔接 |

> ⚠️ 将 1200 px 版本作为布局参考图保留。  
> 各版本保持相同比例，避免布局偏移。

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

---

## 优化说明
- 每张主要图片的目标大小为 **150–400 KB**。  
- WebP 使用 `quality = 80` 时，通常在视觉上难以与原图区分。  
- 始终在仓库之外保留存档版本（PSD / Procreate）。

---

## 注意事项
- 为不完全支持 WebP 的平台提供 `.jpg` 后备版本。  
- 主页各图片保持一致的色调。  
- 修改图片批次时，更新文件名中的时间标识。
