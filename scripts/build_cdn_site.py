"""Build the folder that gets published to Cloudflare Pages.

site/
  all_images/   full images (copied from all_images/)
  thumbs/       540 px feed thumbnails, same file names
  *.json        the five list files the app reads
  _headers      cache rules

usage: python scripts/build_cdn_site.py [--out site]
"""
import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_FILES = ["app_config.json", "manifest.json", "templates_db.json", "imageTexts.json", "imagePositions.json"]

# Pages free plan limits
MAX_FILES = 20000
MAX_FILE_BYTES = 25 * 1024 * 1024

# Images: 1 day for now, because plain admin uploads can reuse a deleted file's name.
# Once every new upload name carries a hash, raise to "public, max-age=31536000, immutable".
IMAGE_CACHE = "public, max-age=86400"
# Lists: short, so admin changes reach phones within about 5 minutes.
LIST_CACHE = "public, max-age=300"


def headers_file():
    lines = []
    for folder in ("all_images", "thumbs"):
        lines += [f"/{folder}/*", f"  Cache-Control: {IMAGE_CACHE}", ""]
    for f in APP_FILES:
        lines += [f"/{f}", f"  Cache-Control: {LIST_CACHE}", "  Content-Type: application/json; charset=utf-8", ""]
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="site")
    out = os.path.abspath(p.parse_args().out)
    src_images = os.path.join(ROOT, "all_images")

    os.makedirs(out, exist_ok=True)
    # full images: mirror all_images exactly (drop files deleted from the repo)
    dst_images = os.path.join(out, "all_images")
    if os.path.isdir(dst_images):
        shutil.rmtree(dst_images)
    shutil.copytree(src_images, dst_images)

    # thumbnails (make_thumbs skips ones already up to date and drops orphans)
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "make_thumbs.py"),
                    "--src", src_images, "--out", os.path.join(out, "thumbs")], check=True)

    for f in APP_FILES:
        shutil.copyfile(os.path.join(ROOT, f), os.path.join(out, f))
    with open(os.path.join(out, "_headers"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(headers_file())

    count, total, too_big = 0, 0, []
    for dirpath, _, files in os.walk(out):
        for n in files:
            path = os.path.join(dirpath, n)
            size = os.path.getsize(path)
            count += 1
            total += size
            if size > MAX_FILE_BYTES:
                too_big.append(path)
    print(f"site: {count} files, {total / 1e6:.0f} MB")
    if count > MAX_FILES or too_big:
        print(f"Over the Cloudflare Pages limits: {count} files (max {MAX_FILES}); too big: {too_big}", file=sys.stderr)
        sys.exit(1)
    if count > MAX_FILES * 0.8:
        print(f"WARNING: {count} files is over 80% of the Pages limit of {MAX_FILES}.", file=sys.stderr)


if __name__ == "__main__":
    main()
