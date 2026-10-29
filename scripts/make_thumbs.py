"""Make small feed thumbnails for every image in all_images/.

Writes thumbs/<same file name>, at most 540 px wide, webp quality 75.
Skips images whose thumbnail is already newer than the source.
If a thumbnail would come out bigger than its source, the source is copied as-is.

usage: python scripts/make_thumbs.py [--src all_images] [--out thumbs]
"""
import argparse
import os
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor

from PIL import Image

MAX_W = 540
QUALITY = 75


def make(args):
    src, dst = args
    if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        return "skip"
    tmp = dst + ".tmp"
    with Image.open(src) as im:
        im.load()
        if im.width > MAX_W:
            h = round(im.height * MAX_W / im.width)
            im = im.resize((MAX_W, h), Image.LANCZOS)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "transparency" in im.info or im.mode in ("LA", "P") else "RGB")
        im.save(tmp, "WEBP", quality=QUALITY, method=4)
    if os.path.getsize(tmp) >= os.path.getsize(src):
        os.remove(tmp)
        shutil.copyfile(src, dst)
        return "copy"
    os.replace(tmp, dst)
    return "made"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--src", default="all_images")
    p.add_argument("--out", default="thumbs")
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    names = sorted(n for n in os.listdir(a.src) if n.lower().endswith((".webp", ".jpg", ".jpeg", ".png")))
    jobs = []
    for n in names:
        # thumbs are always webp but keep the source file name, so the app can swap the folder only
        jobs.append((os.path.join(a.src, n), os.path.join(a.out, n)))
    counts = {"made": 0, "copy": 0, "skip": 0}
    failed = []
    with ProcessPoolExecutor() as ex:
        for (src, _), r in zip(jobs, ex.map(_safe, jobs, chunksize=16)):
            if r.startswith("error"):
                failed.append(f"{src}: {r}")
            else:
                counts[r] += 1
    # drop thumbnails whose source image was deleted
    keep = set(names)
    removed = 0
    for n in os.listdir(a.out):
        if n not in keep:
            os.remove(os.path.join(a.out, n))
            removed += 1
    print(f"thumbs: {counts['made']} made, {counts['copy']} copied, {counts['skip']} up to date, {removed} removed")
    if failed:
        print("FAILED:\n" + "\n".join(failed), file=sys.stderr)
        sys.exit(1)


def _safe(job):
    try:
        return make(job)
    except Exception as e:  # report every bad file, don't stop at the first
        return f"error {e}"


if __name__ == "__main__":
    main()
