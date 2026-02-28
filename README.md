# PostHog Handbook EPUB

Converts the [PostHog company handbook](https://posthog.com/handbook) into a well-structured EPUB e-book, built automatically from the [posthog.com source repo](https://github.com/PostHog/posthog.com).

Written by the humans and hogs of PostHog. Compiled and ebookified by [Zan Markan](https://github.com/zmarkan).

## What you get

- A proper EPUB with cover art, table of contents, and 280+ chapters
- Organised into parts: core handbook, engineering, product, people, growth, and more
- Monthly editions tagged by date with source commit info
- Clean formatting optimised for e-readers

## Quick start

```bash
# Set up venv
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Clone the PostHog website repo
git clone --depth 1 https://github.com/PostHog/posthog.com.git /tmp/posthog.com

# Build the EPUB
python build_epub.py --repo-path /tmp/posthog.com --output posthog-handbook.epub
```

Open the generated `.epub` in Apple Books, Calibre, or your favourite e-reader.

## Usage

```
python build_epub.py --repo-path /path/to/posthog.com --output handbook.epub [--cover cover.png]
```

| Flag | Description | Default |
|------|-------------|---------|
| `--repo-path` | Path to a clone of `PostHog/posthog.com` | `.` |
| `--output` | Output EPUB file path | `posthog-handbook.epub` |
| `--cover` | Custom cover image (PNG/JPG) | Uses bundled `assets/cover.png` |

## CI/CD

A CircleCI pipeline runs monthly (1st of each month at 09:00 UTC) and:

1. Clones the latest PostHog website repo
2. Builds the EPUB
3. Creates a GitHub Release tagged `YYYY-MM` with the EPUB attached

### Setup

Add a `GITHUB_TOKEN` environment variable in your CircleCI project settings with a fine-grained token that has **Contents** (read/write) permission on this repo.

## Project structure

```
├── build_epub.py        # Main build script
├── generate_cover.py    # Fallback cover generator (Pillow)
├── assets/
│   └── cover.png        # Cover artwork
├── requirements.txt     # Python dependencies
└── .circleci/
    └── config.yml       # Monthly build + GitHub Release pipeline
```

## License

The handbook content is © PostHog. This tool is an unofficial community project.
