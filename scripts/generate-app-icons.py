#!/usr/bin/env python3
"""Generate macOS app icon assets for Bristlenose.

Creates:
1. Layered PNGs for Icon Composer (foreground + background)
2. Flat composite PNGs at all 10 required sizes for AppIcon.appiconset
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path("/home/user/bristlenose")
SRC_LIGHT = REPO / "bristlenose/theme/images/bristlenose.png"
SRC_DARK = REPO / "bristlenose/theme/images/bristlenose-dark.png"
APPICONSET = REPO / "desktop/Bristlenose/Bristlenose/Assets.xcassets/AppIcon.appiconset"
LAYERS_DIR = APPICONSET / "layers"

# macOS icon sizes: (point_size, scale, pixel_size)
ICON_SIZES = [
    (16, 1, 16),
    (16, 2, 32),
    (32, 1, 32),
    (32, 2, 64),
    (128, 1, 128),
    (128, 2, 256),
    (256, 1, 256),
    (256, 2, 512),
    (512, 1, 512),
    (512, 2, 1024),
]

# Brand colours (from the fish images / theme)
BG_COLOR_LIGHT = (240, 245, 250)  # Soft blue-grey, clean and professional
BG_GRADIENT_TOP = (225, 238, 250)  # Lighter top
BG_GRADIENT_BOTTOM = (200, 220, 240)  # Slightly deeper bottom
ACCENT = (59, 130, 246)  # Blue accent (similar to --bn-colour-accent)


def remove_background(img: Image.Image, threshold: int = 230) -> Image.Image:
    """Remove white/near-white background from the fish image."""
    img = img.convert("RGBA")
    data = img.getdata()
    new_data = []
    for r, g, b, a in data:
        # If pixel is near-white, make transparent
        if r > threshold and g > threshold and b > threshold:
            new_data.append((r, g, b, 0))
        else:
            # Partial transparency for edge pixels (anti-aliasing)
            brightness = (r + g + b) / 3
            if brightness > threshold - 30:
                alpha = int(255 * (1 - (brightness - (threshold - 30)) / 30))
                alpha = max(0, min(255, alpha))
                new_data.append((r, g, b, alpha))
            else:
                new_data.append((r, g, b, a))
    img.putdata(new_data)
    return img


def create_background_layer(size: int = 1024) -> Image.Image:
    """Create a gradient background layer for Icon Composer.

    This is a simple gradient — Icon Composer will apply the Liquid Glass
    material on top. The background should be a solid or gradient fill
    that works well under glass translucency.
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Radial gradient: lighter center, slightly deeper edges
    cx, cy = size // 2, size // 2
    max_dist = math.sqrt(cx**2 + cy**2)

    for y in range(size):
        for x in range(size):
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2) / max_dist
            dist = min(1.0, dist)
            r = int(BG_GRADIENT_TOP[0] * (1 - dist) + BG_GRADIENT_BOTTOM[0] * dist)
            g = int(BG_GRADIENT_TOP[1] * (1 - dist) + BG_GRADIENT_BOTTOM[1] * dist)
            b = int(BG_GRADIENT_TOP[2] * (1 - dist) + BG_GRADIENT_BOTTOM[2] * dist)
            img.putpixel((x, y), (r, g, b, 255))

    return img


def create_background_layer_fast(size: int = 1024) -> Image.Image:
    """Fast version: vertical gradient background."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)

    for y in range(size):
        t = y / size
        r = int(BG_GRADIENT_TOP[0] * (1 - t) + BG_GRADIENT_BOTTOM[0] * t)
        g = int(BG_GRADIENT_TOP[1] * (1 - t) + BG_GRADIENT_BOTTOM[1] * t)
        b = int(BG_GRADIENT_TOP[2] * (1 - t) + BG_GRADIENT_BOTTOM[2] * t)
        draw.line([(0, y), (size - 1, y)], fill=(r, g, b, 255))

    return img


def create_foreground_layer(src_path: Path, size: int = 1024) -> Image.Image:
    """Create the foreground layer: fish on transparent background.

    The fish is centered with padding for the macOS icon safe zone.
    Apple recommends keeping artwork within ~80% of the canvas.
    """
    src = Image.open(src_path)
    fish = remove_background(src)

    # Scale fish to ~72% of canvas (leave room for padding + icon mask)
    fish_size = int(size * 0.72)
    fish = fish.resize((fish_size, fish_size), Image.LANCZOS)

    # Center on transparent canvas
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset_x = (size - fish_size) // 2
    offset_y = (size - fish_size) // 2
    canvas.paste(fish, (offset_x, offset_y), fish)

    return canvas


def create_composite(bg: Image.Image, fg: Image.Image) -> Image.Image:
    """Composite foreground over background for flat icon."""
    result = bg.copy()
    result.paste(fg, (0, 0), fg)
    return result


def generate_all_sizes(composite_1024: Image.Image) -> None:
    """Generate all 10 required icon sizes from the 1024×1024 composite."""
    for pt_size, scale, px_size in ICON_SIZES:
        suffix = f"@{scale}x" if scale > 1 else ""
        filename = f"icon_{pt_size}x{pt_size}{suffix}.png"
        icon = composite_1024.resize((px_size, px_size), Image.LANCZOS)
        # Convert to RGB for smaller file size (macOS icons are opaque)
        icon_rgb = Image.new("RGB", (px_size, px_size), BG_COLOR_LIGHT)
        icon_rgb.paste(icon, (0, 0), icon)
        icon_rgb.save(APPICONSET / filename, "PNG", optimize=True)
        print(f"  {filename} ({px_size}×{px_size})")


def main():
    APPICONSET.mkdir(parents=True, exist_ok=True)
    LAYERS_DIR.mkdir(parents=True, exist_ok=True)

    print("Creating layered artwork for Icon Composer...")

    # Background layer (1024×1024)
    print("  Background layer (vertical gradient)...")
    bg = create_background_layer_fast(1024)
    bg.save(LAYERS_DIR / "background.png", "PNG", optimize=True)
    print("  Saved layers/background.png")

    # Foreground layer — light variant (default appearance)
    print("  Foreground layer (light / default)...")
    fg_light = create_foreground_layer(SRC_LIGHT, 1024)
    fg_light.save(LAYERS_DIR / "foreground-default.png", "PNG", optimize=True)
    print("  Saved layers/foreground-default.png")

    # Foreground layer — dark variant
    print("  Foreground layer (dark)...")
    fg_dark = create_foreground_layer(SRC_DARK, 1024)
    fg_dark.save(LAYERS_DIR / "foreground-dark.png", "PNG", optimize=True)
    print("  Saved layers/foreground-dark.png")

    # Mono foreground (for tinted appearance — white silhouette)
    print("  Foreground layer (mono / tinted)...")
    # Convert dark variant to white silhouette
    mono = fg_dark.copy()
    data = mono.getdata()
    new_data = []
    for r, g, b, a in data:
        if a > 0:
            new_data.append((255, 255, 255, a))
        else:
            new_data.append((0, 0, 0, 0))
    mono.putdata(new_data)
    mono.save(LAYERS_DIR / "foreground-mono.png", "PNG", optimize=True)
    print("  Saved layers/foreground-mono.png")

    # Composite flat icons for backward compatibility
    print("\nGenerating flat PNG icons for asset catalog...")
    composite = create_composite(bg, fg_light)
    generate_all_sizes(composite)

    print("\nDone! Files created:")
    print(f"  Layers: {LAYERS_DIR}")
    print(f"  Icons:  {APPICONSET}")


if __name__ == "__main__":
    main()
