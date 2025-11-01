待整理。以下是整理规则备忘。

# Avatar Assets

This folder contains personal avatar images used across different platforms and contexts.

---

## File Format Guidelines
- **.jpg** → Primary universal format, best compatibility across WordPress, GitHub, and email clients.  
- **.png** → Use when transparency or sharp edges are needed.  
- **.webp** → Optional optimized format for modern browsers; keep a `.jpg` fallback.  

Color profile: **sRGB**  
Recommended DPI: **72–96** (for web display)

---

## Size Standards
| Use Case | Recommended Size | Notes |
|-----------|------------------|-------|
| Master Source | 1024×1024 px | Keep this as the original editable version |
| Website / CMS | 512×512 px | Good balance between clarity and load time |
| SNS / GitHub | 400×400 px | Default display size for most platforms |
| Thumbnail / Favicon | 128×128 px | For small previews, meta images, or icons |

> ⚠️ Always keep the **1024×1024** master version archived.  
> From it, export smaller versions when needed—never upscale a reduced image.

---

## Naming Convention
- `main-<size>.ext` → Primary avatar images (e.g., `main-512.webp`)  
- `thumbnail-<size>.ext` → Small variants or icons  
- Avoid spaces, uppercase letters, or platform-specific names like `github-avatar.jpg`.

---

## Notes
- Maintain consistent framing and margins to prevent auto-cropping on SNS platforms.  
- Keep file size around **100–300 KB** for fast web load.  
- When embedding on web pages, use JPG as default and WebP as the performance-optimized alternative.  

