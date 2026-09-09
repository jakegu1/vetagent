"""Identifiers that were moved out of the public repo must not come back.

W13. The Cloudflare account id and zone id sat in docs/HANDOFF.md in plain text from
2026-09-03 to 2026-09-09. Neither is a secret and neither can be rotated -- Cloudflare
treats both as public identifiers -- so this is not credential hygiene. The threat is
narrower and more plausible: combined with the maintainer's real name, email, and the
`jake-gu95.workers.dev` subdomain, all still public and reasonably so, they are exactly
what makes a "Cloudflare security team" phishing message sound like it already has access.

**This test cannot prevent the original exposure.** Both values are still in public commit
`5a16721` and always will be. What it prevents is the second, third and fourth time
somebody pastes them back into a file while writing a deploy note -- which is how they got
here in the first place.

Why it stores hashes rather than the values: a guard that contains the string it forbids
fails on itself, and then gets an exemption, and then the exemption is the hole. So this
finds every 32-hex-character token in every TRACKED file, hashes each one, and compares
against known-bad digests. The forbidden values appear nowhere in this file.

Run: python tests/test_no_private_identifiers.py
"""

import hashlib
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# sha256 of the Cloudflare account id and the vetagent.dev zone id. The values live in
# ../vetagent-private-notes.md, outside the repository.
FORBIDDEN = {
    "a89787c357c622790eaf0fb988e18ac4fc003a2d96c34201184ff75f3450d4f3": "Cloudflare account id",
    "7963e3b464a7de6f9515c33e33f9c850ef0b98aabd7ae9b32f30a04653026ee1": "vetagent.dev zone id",
}

HEX32 = re.compile(r"\b[0-9a-f]{32}\b")

_PASSED = 0
_FAILURES = []


def check(name, ok, detail=""):
    global _PASSED
    if ok:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def tracked_files():
    """Only files git actually tracks. `.wrangler/` holds the account id and is ignored."""
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         encoding="utf-8", errors="replace").stdout
    return [p for p in out.splitlines() if p.strip()]


def test_the_identifiers_are_not_in_any_tracked_file():
    print("\n[W13] identifiers moved to a private note have not come back")
    files = tracked_files()
    check("git ls-files returned something -- an empty list would pass vacuously",
          len(files) > 20, "%d files" % len(files))

    hits = []
    for rel in files:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        try:
            with io.open(path, encoding="utf-8", errors="ignore") as f:
                for lineno, line in enumerate(f, 1):
                    for token in HEX32.findall(line):
                        digest = hashlib.sha256(token.encode()).hexdigest()
                        if digest in FORBIDDEN:
                            hits.append((rel, lineno, FORBIDDEN[digest]))
        except OSError:
            continue

    check("no tracked file carries either identifier", not hits,
          "; ".join("%s:%d is the %s" % h for h in hits))


def test_the_private_note_exists_and_is_outside_the_repo():
    """The values have to live somewhere, and that somewhere must not be here."""
    print("\n[W13] the private note is outside the repository")
    note = os.path.join(os.path.dirname(ROOT), "vetagent-private-notes.md")
    check("the note exists", os.path.exists(note), note)
    if not os.path.exists(note):
        return
    inside = os.path.abspath(note).startswith(os.path.abspath(ROOT) + os.sep)
    check("and it is not inside the repo", not inside, note)
    check("so git does not track it",
          "vetagent-private-notes.md" not in tracked_files())


def test_the_guard_actually_catches_the_thing():
    """A guard nobody has watched fail is not a guard. Watch it here, every run."""
    print("\n[W13] the guard fires on a planted value")
    note = os.path.join(os.path.dirname(ROOT), "vetagent-private-notes.md")
    if not os.path.exists(note):
        check("cannot self-test without the note", False, "note missing")
        return
    with io.open(note, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    found = set()
    for token in HEX32.findall(text):
        digest = hashlib.sha256(token.encode()).hexdigest()
        if digest in FORBIDDEN:
            found.add(FORBIDDEN[digest])
    # The note is the one place both values are supposed to be, so it doubles as the
    # fixture: if the detector cannot find them there, it would not find them anywhere.
    check("the detector finds both values where they legitimately are",
          len(found) == 2, "found %s" % (sorted(found) or "nothing"))


def main():
    print("=" * 68)
    print("W13: private identifiers stay out of the public repository")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        fn()
    print("\n" + "=" * 68)
    print("%d passed, %d failed" % (_PASSED, len(_FAILURES)))
    if _FAILURES:
        print("\nFailures:")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("All passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
