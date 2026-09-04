"""test_english_only.py — the repo has one language, and it is English.

Why this is a test rather than a convention: the project is public and aimed at an
international audience, and it was written by someone whose first language is not
English. Without a check, Chinese creeps back in one comment at a time, and nobody
notices until a would-be contributor bounces off a file they cannot read.

Scope is deliberate:
  - Our own source, tests, docs, workflows and page copy: must be English.
  - Upstream data we merely stored (API fixtures, the labelled dataset, snapshots):
    exempt. Those contain real token names, some of which are Chinese, and rewriting
    third-party data to pass a style check would be falsifying evidence.

Checks CJK specifically, not "non-ASCII". Em dashes, curly quotes and accented names
are legitimate English typography, and a check that fails on punctuation is a check
someone will switch off.

Run:  python tests/test_english_only.py
"""

import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

TEXT_EXT = (".py", ".md", ".yml", ".yaml", ".html", ".txt", ".json", ".jsonc", ".toml")

# Files we own that carry no extension, so the suffix check above skips them. This list
# exists because it had to: .gitignore sat here with Chinese comments in it for weeks
# while this test reported PASS on every run. A check that silently declines to look at
# a file is worse than no check, because it buys confidence it has not earned.
TEXT_NAMES = {".gitignore", ".gitattributes", ".dockerignore", ".editorconfig",
              "Dockerfile", "Makefile", "LICENSE", "CODEOWNERS", "Procfile"}

# Directories holding data we received rather than wrote.
EXEMPT_DIRS = {
    os.path.normpath("bench/fixtures"),
    os.path.normpath("bench/snapshots"),
    os.path.normpath("bench/cache"),
    os.path.normpath("tests/fixtures"),
    os.path.normpath(".git"),
    os.path.normpath(".venv"),
    os.path.normpath(".venv-workers"),
    os.path.normpath("node_modules"),
    os.path.normpath("__pycache__"),
}
EXEMPT_FILES = {
    os.path.normpath("bench/dataset.json"),   # upstream token metadata
    os.path.normpath("bench/results.json"),   # generated from that dataset
}


def is_cjk(ch):
    # Ranges are written as code points, not as example characters, so that this
    # file does not flag itself.
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF        # CJK unified ideographs
            or 0x3400 <= o <= 0x4DBF     # extension A
            or 0x3000 <= o <= 0x303F     # CJK punctuation
            or 0xFF00 <= o <= 0xFFEF)    # fullwidth forms


def walk():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel_dir = os.path.normpath(os.path.relpath(dirpath, ROOT))
        dirnames[:] = [d for d in dirnames
                       if os.path.normpath(os.path.join(rel_dir, d)) not in EXEMPT_DIRS
                       and d not in {"__pycache__", ".git", "node_modules"}]
        if rel_dir in EXEMPT_DIRS:
            continue
        for fn in filenames:
            if not fn.endswith(TEXT_EXT) and fn not in TEXT_NAMES:
                continue
            rel = os.path.normpath(os.path.join(rel_dir, fn))
            if rel in EXEMPT_FILES:
                continue
            yield rel, os.path.join(dirpath, fn)


def main():
    print("=" * 66)
    print("English-only check")
    print("=" * 66)
    offenders = []
    scanned = 0
    for rel, full in walk():
        try:
            with open(full, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        scanned += 1
        hits = []
        for lineno, line in enumerate(text.splitlines(), 1):
            bad = [c for c in line if is_cjk(c)]
            if bad:
                hits.append((lineno, "".join(bad)[:24], line.strip()[:70]))
        if hits:
            offenders.append((rel, hits))

    print("scanned %d files" % scanned)
    if not offenders:
        print("\nno CJK found outside the exempt data directories")
        print("PASS")
        return 0

    total = sum(len(h) for _, h in offenders)
    print("\n%d lines across %d files still contain CJK:\n" % (total, len(offenders)))
    for rel, hits in offenders:
        print("  %s  (%d lines)" % (rel, len(hits)))
        for lineno, chars, preview in hits[:3]:
            print("      %d: %s | %s" % (lineno, chars, preview))
        if len(hits) > 3:
            print("      ... and %d more" % (len(hits) - 3))
    print("\nFAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
