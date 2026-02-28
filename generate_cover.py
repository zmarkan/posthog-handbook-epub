#!/usr/bin/env python3
"""
Generate a cover image for the PostHog Handbook EPUB.

Creates a 1600x2400 cover with PostHog-inspired design:
dark background, bold typography, geometric hedgehog motif.
"""

import math
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def generate_cover(output_path: Path, build_date: str | None = None):
    """Generate the handbook cover image."""
    if build_date is None:
        build_date = datetime.now(timezone.utc).strftime("%B %Y")

    W, H = 1600, 2400
    img = Image.new("RGB", (W, H), "#151A26")
    draw = ImageDraw.Draw(img)

    # Fonts
    try:
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 130)
        font_subtitle = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 56)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        font_author = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    except OSError:
        font_bold = ImageFont.load_default()
        font_subtitle = font_bold
        font_small = font_bold
        font_tiny = font_bold
        font_author = font_bold

    # ── Background texture: subtle diagonal lines ──
    accent = "#F7A501"  # PostHog yellow/amber
    blue = "#1D4AFF"    # PostHog blue

    # Draw subtle grid pattern in the background
    for y in range(0, H, 80):
        draw.line([(0, y), (W, y)], fill="#1A2030", width=1)

    # ── Geometric hedgehog motif (top area) ──
    # A stylized hedgehog made of radiating lines — like spines
    cx, cy = W // 2, 580
    radius = 280
    num_spines = 24

    # Draw spines radiating outward (top half only — like a hedgehog's back)
    for i in range(num_spines):
        angle = math.pi + (math.pi * i / (num_spines - 1))  # 180° to 360°
        # Alternating lengths for visual interest
        spine_len = radius + (40 if i % 2 == 0 else 0)
        inner_r = radius * 0.45

        x1 = cx + inner_r * math.cos(angle)
        y1 = cy + inner_r * math.sin(angle)
        x2 = cx + spine_len * math.cos(angle)
        y2 = cy + spine_len * math.sin(angle)

        # Gradient effect: center spines are brighter
        dist_from_center = abs(i - num_spines // 2) / (num_spines // 2)
        if dist_from_center < 0.3:
            color = accent
            width = 6
        elif dist_from_center < 0.6:
            color = "#D48B01"
            width = 5
        else:
            color = "#8B6914"
            width = 4

        draw.line([(x1, y1), (x2, y2)], fill=color, width=width)

    # Body: a filled semicircle at the bottom of the spines
    body_box = [cx - radius * 0.5, cy - radius * 0.15, cx + radius * 0.5, cy + radius * 0.45]
    draw.ellipse(body_box, fill="#2A3040", outline="#3A4050", width=2)

    # Eye
    draw.ellipse([cx - 35, cy + 10, cx - 10, cy + 35], fill="#FFFFFF")
    draw.ellipse([cx - 30, cy + 15, cx - 15, cy + 30], fill="#151A26")

    # Nose
    draw.ellipse([cx - 60, cy + 20, cx - 42, cy + 38], fill="#1A1A1A")

    # ── Accent line ──
    line_y = 860
    line_margin = 200
    draw.line([(line_margin, line_y), (W - line_margin, line_y)], fill=accent, width=4)

    # ── Title ──
    title_y = 940
    title_lines = ["The PostHog", "Handbook"]

    for i, line in enumerate(title_lines):
        bbox = draw.textbbox((0, 0), line, font=font_bold)
        tw = bbox[2] - bbox[0]
        x = (W - tw) // 2
        y = title_y + i * 160
        draw.text((x, y), line, fill="#FFFFFF", font=font_bold)

    # ── Subtitle ──
    subtitle = "How we work"
    bbox = draw.textbbox((0, 0), subtitle, font=font_subtitle)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 1310), subtitle, fill="#9CA3AF", font=font_subtitle)

    # ── Accent line below subtitle ──
    draw.line([(line_margin, 1420), (W - line_margin, 1420)], fill=accent, width=4)

    # ── Description block ──
    desc_lines = [
        "Strategy · Values · Culture",
        "Engineering · Product · Growth",
        "People · Operations · Content",
    ]
    for i, line in enumerate(desc_lines):
        bbox = draw.textbbox((0, 0), line, font=font_small)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, 1500 + i * 60), line, fill="#6B7280", font=font_small)

    # ── Author ──
    author = "PostHog"
    bbox = draw.textbbox((0, 0), author, font=font_author)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 1850), author, fill="#FFFFFF", font=font_author)

    # ── Build info at bottom ──
    build_text = f"Auto-generated from source · {build_date}"
    bbox = draw.textbbox((0, 0), build_text, font=font_tiny)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 2280), build_text, fill="#4B5563", font=font_tiny)

    # ── Bottom accent bar ──
    draw.rectangle([(0, H - 12), (W, H)], fill=accent)

    # ── Top accent bar ──
    draw.rectangle([(0, 0), (W, 12)], fill=accent)

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "JPEG", quality=90)
    print(f"  📕 Cover: {output_path} ({output_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    generate_cover(Path("cover.jpg"))
