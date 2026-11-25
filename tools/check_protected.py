#!/usr/bin/env python3
"""Refuse to publish anything but the page, its styles, its script and flat pictures.

  python tools/check_protected.py                 what is staged for the next commit (used by the hooks)
  python tools/check_protected.py --tree          every file in the folder, as it is on disk
  python tools/check_protected.py --history       every file in every commit reachable from HEAD
  python tools/check_protected.py --history A..B  every file in the commits of that range (used before a push)

Exit code 1 and a list of problems if anything is found.

How it decides (rewritten 2026-11-24 after an independent review broke the first version):
  1. EXACT PATHS. Only the files named in MANIFEST may exist. Anything else is refused, whatever
     its extension, including names with characters outside A-Z a-z 0-9 . _ / -
  2. STAGED CONTENT. In the default mode the bytes come from the git index, not from the disk,
     so what is checked is exactly what would be committed. Symlinks and submodules are refused.
  3. PICTURES. A .webp must be a complete WebP file and nothing more: the size in its header must
     equal the file size, it may hold only image chunks (no EXIF, XMP, ICC or unknown chunks),
     nothing may follow the image, and its canvas and byte size are capped.
  4. TEXT. Each text file has a small size cap. It must be plain UTF-8, with no embedded vector
     drawing, no data: URI, no long base64 run and no table of decimal numbers, and it must not
     contain a patent application number, a filing reference or a local disk path.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = 1024
MAX_TOTAL = 6 * KB * KB          # everything together
MAX_CANVAS = 1900                # pixels, either side of any picture

# path pattern -> (kind, max bytes, max decimal literals)
MANIFEST = [
    (r"index\.html",                                   "text", 40 * KB, 30),
    (r"README\.md",                                    "text", 8 * KB, 30),
    (r"assets/style\.css",                             "text", 20 * KB, 200),
    (r"assets/app\.js",                                "text", 8 * KB, 30),
    (r"assets/side-view\.webp",                        "webp", 60 * KB, 0),
    (r"assets/hero/f[0-3][0-9]\.webp",                 "webp", 120 * KB, 0),
    (r"assets/figures/fig-07-advance-cycle\.webp",     "webp", 200 * KB, 0),
    (r"assets/figures/fig-12-mission-schematic\.webp", "webp", 200 * KB, 0),
    (r"tools/check_protected\.py",                     "text", 24 * KB, 30),
    (r"\.githooks/pre-commit",                         "text", 2 * KB, 0),
    (r"\.githooks/pre-merge-commit",                   "text", 2 * KB, 0),
    (r"\.githooks/pre-push",                           "text", 2 * KB, 0),
    (r"\.github/workflows/protect\.yml",               "text", 4 * KB, 0),
    (r"\.gitignore",                                   "text", 2 * KB, 0),
    (r"\.nojekyll",                                    "empty", 0, 0),
]
SAFE_PATH = re.compile(r"[A-Za-z0-9._/-]+")
WEBP_CHUNKS = {b"VP8X", b"ALPH", b"VP8 ", b"VP8L"}


def _rx(*pieces, flags=0):
    # patterns are assembled from pieces so that this file does not match its own rules
    return re.compile("".join(pieces), flags)


TEXT_RULES = [
    (_rx(r"\b(?:63|1[5-9])\s?", r"/\s?\d{3}[,\s]?\d{3}\b"), "looks like a patent application number"),
    (_rx(r"\b63", r"\d{6}\b"), "looks like a patent application number"),
    (_rx("PCT", "/US"), "looks like an international application number"),
    (_rx(r"&#0*47;|&#x0*2f;", flags=re.I), "encoded slash (hides a number or path)"),
    # the next three need a digit after the words, so prose that merely names the idea is allowed
    (_rx(r"\bconf(?:irmation)?\.?\s*", r"(?:no\b\.?|number|#)\s*[:#]?\s*\d", flags=re.I), "filing confirmation reference"),
    (_rx(r"\bEF", r"S\b"), "filing system reference"),
    (_rx("dock", r"et\s*(?:no\b\.?|number|#)?\s*[:#]?\s*[A-Z0-9-]*\d", flags=re.I), "docket reference"),
    (_rx(r"application\s+", r"(?:no\b\.?|number|serial)\D{0,12}\d", flags=re.I), "application number reference"),
    (_rx(r"(?<![A-Za-z])[A-Za-z]:", r"[\\/](?!/)"), "local disk path"),
    (_rx("/Us", "ers/"), "local disk path"),
    (_rx("/ho", "me/"), "local disk path"),
    (_rx("One", "Drive", flags=re.I), "local sync folder"),
    (_rx("ems", r"ki(?!m0910)", flags=re.I), "local user name"),
    (_rx("Claude", r"\s+Context", flags=re.I), "local folder name"),
    (_rx("Micro", "-TBM", flags=re.I), "local folder name"),
    (_rx("%", r"(?:USERPROFILE|APPDATA|LOCALAPPDATA|HOMEPATH)", "%", flags=re.I), "local disk path"),
    (_rx("<", r"(?:svg|path|polyline|polygon)\b", flags=re.I), "embedded vector drawing"),
    (_rx("data", r":[a-z]+/", flags=re.I), "embedded data: URI"),
    (_rx(r"[A-Za-z0-9+/=]{200,}"), "long encoded run (possible embedded file)"),
]
DECIMAL = re.compile(r"\d+\.\d+")


def rule_for(path):
    for pattern, kind, max_bytes, max_dec in MANIFEST:
        if re.fullmatch(pattern, path):
            return kind, max_bytes, max_dec
    return None


def check_webp(data):
    problems = []
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return ["not a WebP image"]
    if int.from_bytes(data[4:8], "little") + 8 != len(data):
        problems.append("WebP header size does not match the file (data appended or cut)")
    pos, seen = 12, []
    while pos + 8 <= len(data):
        tag = data[pos:pos + 4]
        size = int.from_bytes(data[pos + 4:pos + 8], "little")
        body = data[pos + 8:pos + 8 + size]
        seen.append(tag)
        if tag not in WEBP_CHUNKS:
            problems.append("WebP holds a non-image chunk %r" % tag)
        if tag == b"VP8X" and size >= 10:
            if body[0] & 0b00101110:
                problems.append("WebP declares metadata, color profile or animation")
            w = int.from_bytes(body[4:7], "little") + 1
            h = int.from_bytes(body[7:10], "little") + 1
            if w > MAX_CANVAS or h > MAX_CANVAS:
                problems.append("picture is %d x %d, over the %d pixel cap" % (w, h, MAX_CANVAS))
        pos += 8 + size + (size & 1)
    if pos != len(data):
        problems.append("bytes left over after the last WebP chunk")
    if not seen or seen[0] != b"VP8X":
        problems.append("WebP has no canvas header")
    return problems


def check_text(path, data, max_dec):
    if b"\x00" in data:
        return ["contains NUL bytes (not plain text)"]
    if data[:3] == b"\xef\xbb\xbf":
        return ["starts with a byte-order mark"]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return ["is not valid UTF-8 text"]
    problems = []
    for rx, what in TEXT_RULES:
        m = rx.search(text)
        if m:
            problems.append("%s: %r" % (what, m.group(0)[:40]))
    n = len(DECIMAL.findall(text))
    if n > max_dec:
        problems.append("%d decimal numbers, over the limit of %d (looks like a data table)" % (n, max_dec))
    return problems


def check(path, mode, data):
    """Problems for one file. data is None if the content could not be read."""
    if not SAFE_PATH.fullmatch(path):
        return ["file name has characters outside A-Z a-z 0-9 . _ / -"]
    if mode not in ("100644", "100755"):
        return ["not a regular file (mode %s)" % mode]
    rule = rule_for(path)
    if rule is None:
        return ["not on the list of files this site may contain"]
    if data is None:
        return ["content could not be read"]
    kind, max_bytes, max_dec = rule
    problems = []
    if len(data) > max_bytes:
        problems.append("%d bytes, over its limit of %d" % (len(data), max_bytes))
    if kind == "empty":
        return problems
    if kind == "webp":
        return problems + check_webp(data)
    return problems + check_text(path, data, max_dec)


# ---- where the files come from ------------------------------------------------------------
def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True)


def staged():
    out = git("ls-files", "-s", "-z")
    if out.returncode != 0:
        sys.exit("check_protected: git is not available here; use --tree")
    for rec in out.stdout.split(b"\0"):
        if not rec:
            continue
        meta, _, raw = rec.partition(b"\t")
        mode, sha, _stage = meta.decode().split()
        blob = git("cat-file", "blob", sha)
        yield raw.decode("utf-8", "replace"), mode, (blob.stdout if blob.returncode == 0 else None), "staged"


def tree():
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d != ".git"]
        for n in names:
            full = os.path.join(base, n)
            rel = os.path.relpath(full, ROOT).replace("\\", "/")
            if os.path.islink(full):
                yield rel, "120000", None, "on disk"
                continue
            with open(full, "rb") as f:
                yield rel, "100644", f.read(), "on disk"


def history(rev):
    revs = git("rev-list", rev)
    if revs.returncode != 0:
        sys.exit("check_protected: cannot list commits for %s" % rev)
    seen = set()
    for commit in revs.stdout.decode().split():
        out = git("ls-tree", "-r", "-z", commit)
        for rec in out.stdout.split(b"\0"):
            if not rec:
                continue
            meta, _, raw = rec.partition(b"\t")
            mode, kind, sha = meta.decode().split()
            path = raw.decode("utf-8", "replace")
            if (path, sha) in seen:
                continue
            seen.add((path, sha))
            blob = git("cat-file", "blob", sha) if kind == "blob" else None
            data = blob.stdout if blob is not None and blob.returncode == 0 else None
            yield path, mode, data, "commit " + commit[:8]


def main():
    args = sys.argv[1:]
    if "--tree" in args:
        files, label = tree(), "folder"
    elif "--history" in args:
        i = args.index("--history")
        rev = args[i + 1] if len(args) > i + 1 else "HEAD"
        files, label = history(rev), "history " + rev
    else:
        files, label = staged(), "staged files"
    bad = count = total = 0
    for path, mode, data, where in files:
        count += 1
        total += len(data or b"")
        for p in check(path, mode, data):
            print("BLOCKED  %s (%s): %s" % (path.encode("ascii", "backslashreplace").decode(), where, p))
            bad += 1
    if label != "history" and not label.startswith("history") and total > MAX_TOTAL:
        print("BLOCKED  the site is %d bytes in all, over the limit of %d" % (total, MAX_TOTAL))
        bad += 1
    if bad:
        print("\n%d problem(s) in %s. Nothing with design data may be published from this folder." % (bad, label))
        return 1
    print("check_protected: %d files in %s, all display-only." % (count, label))
    return 0


if __name__ == "__main__":
    sys.exit(main())
