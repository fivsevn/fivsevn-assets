状态：待整理。

# Homepage Assets

This folder contains images used exclusively for the website homepage — including banners, hero sections, and background visuals.

---

## File Format Guidelines
- **.webp** → Recommended for main banners and hero images; high compression efficiency.  
- **.jpg** → Use for photographic content requiring wide compatibility.  
- **.png** → For transparent overlays or graphic elements.  
- **.svg** → Vector graphics such as logos or geometric icons.  

Color profile: **sRGB**  
Recommended DPI: **72–96** (web standard)

---

## Size Standards
| Use Case | Recommended Width | Notes |
|-----------|------------------|-------|
| Main Banner / Hero | **1200 px** | Primary layout width for most devices |
| Large Screen Variant | **1600–1920 px** | For Retina or full-width layout |
| Mobile / Compact | **800 px** | Optional export for mobile optimization |
| Background Texture | Flexible | Should tile or fade cleanly |

> ⚠️ Keep the 1200-px version as your reference layout image.  
> Maintain aspect ratio between versions to prevent layout shift.

---

## Naming Convention
- File names follow the pattern:  
  **`<section><YYYYMM><descriptor><size>.<ext>`**
  - Example: `homepage202506banner1200.webp`
- Elements:
  - **section** → folder or page name (`homepage`, `avatar`, `links`, etc.)  
  - **YYYYMM** → export batch or update timestamp (e.g., `202506`)  
  - **descriptor** → content type (`banner`, `cover`, `bg`, `logo`)  
  - **size** → primary width indicator (optional but useful)
- Use only lowercase letters and digits; no spaces or underscores.

---

## Optimization Notes
- Target file size: **150–400 KB** per major image.  
- WebP at `quality = 80` is typically indistinguishable from source.  
- Always keep an archived version (PSD / Procreate) outside this repo.

---

## Notes
- Provide a `.jpg` fallback when embedding on platforms with incomplete WebP support.  
- Maintain tonal consistency across homepage elements.  
- Update timestamps in filenames when revising visual batches.
