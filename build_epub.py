#!/usr/bin/env python3
"""
PostHog Handbook → EPUB converter

Converts the PostHog company handbook from its source markdown files
into a well-structured EPUB e-book with proper chapter ordering,
table of contents, and clean formatting.

Usage:
    python build_epub.py --repo-path /path/to/posthog.com --output handbook.epub
"""

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import markdown
import yaml
from ebooklib import epub
from PIL import Image, ImageDraw, ImageFont

from generate_cover import generate_cover


def get_git_info(repo_path: Path) -> dict:
    """Extract git commit info from the source repo."""
    info = {
        "commit_hash": "unknown",
        "commit_short": "unknown",
        "commit_date": "unknown",
        "commit_message": "",
        "commit_url": "",
    }
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H%n%h%n%aI%n%s"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            if len(lines) >= 4:
                info["commit_hash"] = lines[0]
                info["commit_short"] = lines[1]
                info["commit_date"] = lines[2]
                info["commit_message"] = lines[3]
                info["commit_url"] = (
                    f"https://github.com/PostHog/posthog.com/commit/{lines[0]}"
                )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Parse commit date into something readable
    try:
        dt = datetime.fromisoformat(info["commit_date"])
        info["commit_date_human"] = dt.strftime("%d %B %Y at %H:%M UTC")
    except (ValueError, TypeError):
        info["commit_date_human"] = info["commit_date"]

    return info


# ──────────────────────────────────────────────────────────────────────
# Section definitions: maps directory names to human-readable part titles
# and controls ordering of the operational sections after the core chapters.
# ──────────────────────────────────────────────────────────────────────
SECTION_ORDER = [
    ("company", "Company"),
    ("people", "People"),
    ("engineering", "Engineering"),
    ("product", "Product"),
    ("content", "Content"),
    ("marketing", "Marketing"),
    ("growth", "Growth"),
    ("support", "Support"),
    ("cs-and-onboarding", "CS & Onboarding"),
    ("brand", "Brand"),
    ("community", "Community"),
    ("getting-started", "Getting Started"),
    ("exec", "Exec"),
    ("onboarding", "Onboarding"),
    ("docs-and-wizard", "Docs & Wizard"),
]

# CSS for the EPUB — optimized for e-ink readers and reading apps
BOOK_CSS = """
body {
    font-family: Georgia, "Times New Roman", serif;
    line-height: 1.6;
    margin: 1em;
    color: #1a1a1a;
}
h1 {
    font-size: 1.8em;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
    page-break-before: always;
}
h2 {
    font-size: 1.4em;
    margin-top: 1.2em;
    margin-bottom: 0.4em;
}
h3 {
    font-size: 1.15em;
    margin-top: 1em;
    margin-bottom: 0.3em;
}
p {
    margin-bottom: 0.8em;
    text-align: justify;
}
a {
    color: #1d4ed8;
    text-decoration: underline;
}
code {
    font-family: "Courier New", Courier, monospace;
    font-size: 0.9em;
    background-color: #f3f4f6;
    padding: 0.1em 0.3em;
    border-radius: 3px;
}
pre {
    background-color: #f3f4f6;
    padding: 1em;
    overflow-x: auto;
    border-radius: 4px;
    font-size: 0.85em;
    line-height: 1.4;
    margin: 1em 0;
}
pre code {
    background: none;
    padding: 0;
}
blockquote {
    border-left: 3px solid #d1d5db;
    margin-left: 0;
    padding-left: 1em;
    color: #4b5563;
    font-style: italic;
}
img {
    max-width: 100%;
    height: auto;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    font-size: 0.9em;
}
th, td {
    border: 1px solid #d1d5db;
    padding: 0.5em;
    text-align: left;
}
th {
    background-color: #f9fafb;
    font-weight: bold;
}
ul, ol {
    margin-bottom: 0.8em;
    padding-left: 1.5em;
}
li {
    margin-bottom: 0.3em;
}
hr {
    border: none;
    border-top: 1px solid #e5e7eb;
    margin: 2em 0;
}
.part-title {
    font-size: 2em;
    text-align: center;
    margin-top: 3em;
    margin-bottom: 1em;
    font-weight: bold;
}
.part-subtitle {
    text-align: center;
    color: #6b7280;
    font-size: 1.1em;
    margin-bottom: 2em;
}
.build-info {
    text-align: center;
    color: #9ca3af;
    font-size: 0.85em;
    margin-top: 2em;
}
"""


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from a markdown file."""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
                body = parts[2]
                return meta, body
            except yaml.YAMLError:
                pass
    return {}, content


def clean_mdx(content: str) -> str:
    """Strip MDX/JSX components and imports that won't render in EPUB."""
    # Remove import statements
    content = re.sub(r'^import\s+.*$', '', content, flags=re.MULTILINE)

    # Remove self-closing JSX tags like <ComparisonRow ... />
    content = re.sub(r'<[A-Z][A-Za-z]*\s+[^>]*/>', '', content)

    # Remove JSX block components (opening + closing) but keep inner content
    # e.g., <CalloutBox>...</CalloutBox>
    content = re.sub(r'<([A-Z][A-Za-z]*)[^>]*>(.*?)</\1>', r'\2', content, flags=re.DOTALL)

    # Remove remaining self-closing JSX
    content = re.sub(r'<[A-Z][A-Za-z]*\s*/>', '', content)

    # Remove JSX opening/closing tags that might remain
    content = re.sub(r'</?[A-Z][A-Za-z]*[^>]*>', '', content)

    # Remove export statements
    content = re.sub(r'^export\s+.*$', '', content, flags=re.MULTILINE)

    # Convert PostHog internal links to plain text references
    # /handbook/foo/bar → "Handbook: foo/bar"
    content = re.sub(
        r'\[([^\]]+)\]\(/handbook/([^)]+)\)',
        r'\1',
        content
    )

    # Convert other internal links to just the text
    content = re.sub(
        r'\[([^\]]+)\]\(/([^)]+)\)',
        r'\1',
        content
    )

    # Clean up excessive blank lines
    content = re.sub(r'\n{4,}', '\n\n\n', content)

    return content


def md_to_html(content: str) -> str:
    """Convert cleaned markdown to HTML."""
    md = markdown.Markdown(
        extensions=[
            'tables',
            'fenced_code',
            'codehilite',
            'toc',
            'nl2br',
            'sane_lists',
        ],
        extension_configs={
            'codehilite': {'css_class': 'highlight', 'guess_lang': False},
        }
    )
    return md.convert(content)


def load_nav(repo_path: Path) -> list[dict]:
    """Load the handbook navigation JSON for chapter ordering."""
    nav_path = repo_path / "src" / "navs" / "handbook.json"
    if nav_path.exists():
        with open(nav_path) as f:
            nav = json.load(f)
        if nav and len(nav) > 0:
            return nav[0].get("links", [])
    return []


def resolve_path(repo_path: Path, url_path: str) -> Path | None:
    """Resolve a handbook URL path to a file on disk."""
    # /handbook/foo → contents/handbook/foo.md or .mdx
    slug = url_path.replace("/handbook/", "")
    base = repo_path / "contents" / "handbook"

    for ext in [".md", ".mdx"]:
        candidate = base / f"{slug}{ext}"
        if candidate.exists():
            return candidate
        # Try index file in directory
        candidate = base / slug / f"index{ext}"
        if candidate.exists():
            return candidate
    return None


def get_section_files(repo_path: Path, section_dir: str) -> list[tuple[str, Path]]:
    """Get all markdown files in a handbook section directory, sorted."""
    base = repo_path / "contents" / "handbook" / section_dir
    if not base.exists():
        return []

    files = []
    for p in sorted(base.rglob("*.md")):
        # Skip snippet files
        if "/_snippets/" in str(p):
            continue
        meta, _ = parse_frontmatter(p.read_text(errors="replace"))
        title = meta.get("title", p.stem.replace("-", " ").title())
        files.append((title, p))

    for p in sorted(base.rglob("*.mdx")):
        if "/_snippets/" in str(p):
            continue
        meta, _ = parse_frontmatter(p.read_text(errors="replace"))
        title = meta.get("title", p.stem.replace("-", " ").title())
        files.append((title, p))

    return files


def create_chapter(file_path: Path, title: str, file_id: str) -> epub.EpubHtml:
    """Create an EPUB chapter from a markdown file."""
    raw = file_path.read_text(errors="replace")
    meta, body = parse_frontmatter(raw)

    # Use frontmatter title if available
    title = meta.get("title", title)

    # Clean MDX artifacts and convert
    cleaned = clean_mdx(body)
    html_body = md_to_html(cleaned)

    chapter = epub.EpubHtml(
        title=title,
        file_name=f"{file_id}.xhtml",
        lang="en",
    )
    chapter.content = f"<h1>{title}</h1>\n{html_body}"
    return chapter


def _overlay_cover_text(image_path: Path, edition_label: str) -> bytes:
    """Overlay title text onto the cover image's empty top area."""
    import io

    img = Image.open(image_path).convert("RGBA")
    W, H = img.size
    draw = ImageDraw.Draw(img)

    # Try to load a nice font, fall back to default
    try:
        font_title = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", W // 12
        )
        font_sub = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", W // 22
        )
    except OSError:
        # macOS font paths
        try:
            font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", W // 12)
            font_sub = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", W // 22)
        except OSError:
            font_title = ImageFont.load_default()
            font_sub = font_title

    # Draw text in the dark empty area at the top
    title_lines = ["The PostHog", "Handbook"]
    y = int(H * 0.04)
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(((W - tw) // 2, y), line, fill="#FFFFFF", font=font_title)
        y += th + int(H * 0.015)

    # Edition label below title
    y += int(H * 0.01)
    bbox = draw.textbbox((0, 0), edition_label, font=font_sub)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), edition_label, fill="#F7A501", font=font_sub)

    # Save to bytes as PNG
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_epub(repo_path: Path, output_path: Path, cover_image: Path | None = None):
    """Build the complete EPUB from the handbook source."""
    print(f"Building EPUB from {repo_path}")

    now = datetime.now(timezone.utc)
    build_date = now.strftime("%Y-%m-%d")
    build_month = now.strftime("%B %Y")
    edition_label = now.strftime("%B %Y Edition")

    # ── Git info ──
    git = get_git_info(repo_path)
    print(f"  Source: {git['commit_short']} ({git['commit_date_human']})")

    book = epub.EpubBook()

    # ── Metadata ──
    book.set_identifier(f"posthog-handbook-{git['commit_short']}-{build_date}")
    book.set_title(f"The PostHog Handbook — {edition_label}")
    book.set_language("en")
    book.add_author("PostHog")
    book.add_metadata("DC", "description",
                       f"The PostHog company handbook — {edition_label}. "
                       f"Built from commit {git['commit_short']}.")
    book.add_metadata("DC", "date", build_date)
    book.add_metadata("DC", "publisher", "PostHog (unofficial EPUB build)")

    # ── Cover Image ──
    if cover_image and cover_image.exists():
        print(f"  📕 Using custom cover: {cover_image}")
        cover_with_text = _overlay_cover_text(cover_image, edition_label)
    else:
        # Use bundled cover image
        bundled = Path(__file__).parent / "assets" / "cover.png"
        if bundled.exists():
            print(f"  📕 Using bundled cover: {bundled}")
            cover_with_text = _overlay_cover_text(bundled, edition_label)
        else:
            # Fallback: generate a cover from scratch
            cover_path = output_path.parent / "cover.jpg"
            generate_cover(cover_path, build_date=build_month)
            cover_with_text = cover_path.read_bytes()

    book.set_cover("cover.png", cover_with_text, create_page=False)

    # ── Stylesheet ──
    css = epub.EpubItem(
        uid="style",
        file_name="style/default.css",
        media_type="text/css",
        content=BOOK_CSS,
    )
    book.add_item(css)

    all_chapters = []
    toc = []

    # ── Credits Page (placed right after cover) ──
    repo_url = "https://github.com/PostHog/posthog.com"
    edition_page = epub.EpubHtml(title="About This Edition", file_name="edition.xhtml", lang="en")
    edition_page.content = f"""
    <div style="text-align: center; margin-top: 6em; margin-bottom: 2em;">
        <h1 style="font-size: 2em; margin-bottom: 0.2em;">The PostHog Handbook</h1>
        <p style="font-size: 1.3em; color: #F7A501; font-weight: bold; margin-bottom: 1.5em;">{edition_label}</p>
    </div>

    <hr style="width: 40%; margin: 0 auto 2em; border-color: #e5e7eb;" />

    <div style="text-align: center; font-size: 0.85em; color: #9ca3af; line-height: 2;">
        <p>Written by the humans and hedgehogs of PostHog</p>
        <p>Compiled and ebookified by Zan Markan</p>
        <p style="font-style: italic; margin-top: 0.5em;">No hedgehog habitat was destroyed during the making or printing of this ebook.</p>
    </div>

    <hr style="width: 40%; margin: 0 auto 2em; border-color: #e5e7eb;" />

    <div style="text-align: center; font-size: 0.85em; color: #9ca3af; line-height: 2;">
        <p>Source: <a href="{repo_url}">{repo_url}</a></p>
        <p>Commit: <a href="{git['commit_url']}" style="font-family: monospace;">{git['commit_short']}</a>
           &middot; {git['commit_date_human']}</p>
        <p>Built: {build_date}</p>
    </div>

    <div style="text-align: center; margin-top: 3em; font-size: 0.8em; color: #6b7280;">
        <p>Handbook content is &copy; PostHog. This is an unofficial community build.</p>
        <p>For the live version, visit
            <a href="https://posthog.com/handbook">posthog.com/handbook</a>.</p>
    </div>
    """
    edition_page.add_item(css)
    book.add_item(edition_page)
    spine = [edition_page, "nav"]

    # ── Part I: Core Chapters (from handbook.json nav) ──
    nav_links = load_nav(repo_path)
    if nav_links:
        # Part divider
        part1 = epub.EpubHtml(title="Part I: The Story", file_name="part1.xhtml", lang="en")
        part1.content = """
        <div class="part-title">Part I</div>
        <div class="part-subtitle">The PostHog Story</div>
        <p style="text-align: center; color: #6b7280;">
            The core handbook — why PostHog exists, how we work, and where we're going.
        </p>
        """
        part1.add_item(css)
        book.add_item(part1)
        spine.append(part1)

        part1_chapters = []
        for i, link in enumerate(nav_links):
            file_path = resolve_path(repo_path, link["to"])
            if file_path is None:
                print(f"  ⚠ Could not find: {link['to']}")
                continue

            chapter_id = f"ch_{i+1:02d}"
            title = link.get("name", file_path.stem)
            print(f"  Chapter {i+1}: {title}")

            ch = create_chapter(file_path, title, chapter_id)
            ch.add_item(css)
            book.add_item(ch)
            all_chapters.append(ch)
            part1_chapters.append(ch)
            spine.append(ch)

        toc.append((epub.Section("Part I: The PostHog Story"), part1_chapters))

    # ── Part II+: Operational Sections ──
    # Track which files we've already included in Part I
    included_files = set()
    for link in nav_links:
        fp = resolve_path(repo_path, link["to"])
        if fp:
            included_files.add(str(fp))

    part_num = 2
    for section_dir, section_title in SECTION_ORDER:
        files = get_section_files(repo_path, section_dir)
        # Filter out already-included files
        files = [(t, p) for t, p in files if str(p) not in included_files]
        if not files:
            continue

        print(f"\n  Part {part_num}: {section_title} ({len(files)} pages)")

        # Part divider page
        part_page = epub.EpubHtml(
            title=f"Part {part_num}: {section_title}",
            file_name=f"part{part_num}.xhtml",
            lang="en",
        )
        part_page.content = f"""
        <div class="part-title">Part {part_num}</div>
        <div class="part-subtitle">{section_title}</div>
        """
        part_page.add_item(css)
        book.add_item(part_page)
        spine.append(part_page)

        section_chapters = []
        for j, (title, file_path) in enumerate(files):
            chapter_id = f"s{part_num}_{j+1:02d}"
            ch = create_chapter(file_path, title, chapter_id)
            ch.add_item(css)
            book.add_item(ch)
            all_chapters.append(ch)
            section_chapters.append(ch)
            spine.append(ch)
            included_files.add(str(file_path))

        toc.append((epub.Section(f"{section_title}"), section_chapters))
        part_num += 1

    # ── Colophon ──
    colophon = epub.EpubHtml(title="Colophon", file_name="colophon.xhtml", lang="en")
    colophon.content = f"""
    <h1>Colophon</h1>
    <p><strong>{edition_label}</strong></p>
    <p>Built from commit
    <a href="{git['commit_url']}" style="font-family: monospace;">{git['commit_short']}</a>
    ({git['commit_date_human']}).</p>
    <p>The handbook content is © PostHog and is available under their
    <a href="https://github.com/PostHog/posthog.com/blob/master/LICENSE">repository license</a>.</p>
    <p>This is an unofficial community build. For the live version,
    visit <a href="https://posthog.com/handbook">posthog.com/handbook</a>.</p>
    <p>Some interactive elements, images, and embedded components from
    the web version may not render in this format.</p>
    """
    colophon.add_item(css)
    book.add_item(colophon)
    spine.append(colophon)

    # ── Assemble ──
    book.toc = toc
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Set the edition/credits page as the opening page
    book.guide.append({
        "type": "text",
        "title": "About This Edition",
        "href": "edition.xhtml",
    })

    # Write
    output_path.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(output_path), book, {})
    
    file_size = output_path.stat().st_size / 1024
    print(f"\n✅ Built: {output_path} ({file_size:.0f} KB)")
    print(f"   {len(all_chapters)} chapters across {part_num - 1} parts")


def main():
    parser = argparse.ArgumentParser(description="Build PostHog Handbook EPUB")
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=Path("."),
        help="Path to the posthog.com repository clone",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("posthog-handbook.epub"),
        help="Output EPUB file path",
    )
    parser.add_argument(
        "--cover",
        type=Path,
        default=None,
        help="Custom cover image (JPG/PNG). If omitted, generates one automatically.",
    )
    args = parser.parse_args()

    if not (args.repo_path / "contents" / "handbook").exists():
        print(f"❌ Handbook not found at {args.repo_path / 'contents' / 'handbook'}")
        print("   Make sure --repo-path points to a posthog.com repo clone.")
        raise SystemExit(1)

    build_epub(args.repo_path, args.output, cover_image=args.cover)


if __name__ == "__main__":
    main()
