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
_UNCHECKED = []


def check(name, ok, detail=""):
    global _PASSED
    if ok:
        _PASSED += 1
        print("  PASS  %s" % name)
    else:
        _FAILURES.append((name, detail))
        print("  FAIL  %s  %s" % (name, detail))


def unchecked(name, why):
    """Report a dimension this environment cannot observe. Not a pass, not a failure.

    The first version of this file asserted that the private note exists, which is true on
    the maintainer's machine and false on a CI runner that checks out only the repository.
    It turned the build red on eight consecutive commits.

    Deleting the assertion would have been the wrong repair: "we could not look" would
    then have been indistinguishable from "we looked and it was fine", which is the single
    most repeated serious bug in this project. So it is reported as its own third state and
    printed in the summary.
    """
    _UNCHECKED.append((name, why))
    print("  ----  %s  (not checked here: %s)" % (name, why))


def _scan_text(text, forbidden):
    """Every 32-hex token in `text` whose digest is in `forbidden`. One place, so the
    self-test below exercises exactly the code the real scan runs."""
    return [forbidden[hashlib.sha256(t.encode()).hexdigest()]
            for t in HEX32.findall(text)
            if hashlib.sha256(t.encode()).hexdigest() in forbidden]


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
                    for what in _scan_text(line, FORBIDDEN):
                        hits.append((rel, lineno, what))
        except OSError:
            continue

    check("no tracked file carries either identifier", not hits,
          "; ".join("%s:%d is the %s" % h for h in hits))


def test_the_private_note_exists_and_is_outside_the_repo():
    """The values have to live somewhere, and that somewhere must not be here.

    Only observable where the note is: on a CI runner the repository is checked out alone,
    so its parent directory is the runner's workspace and the note is legitimately absent.
    That is reported as unchecked rather than asserted either way.
    """
    print("\n[W13] the private note is outside the repository")
    note = os.path.join(os.path.dirname(ROOT), "vetagent-private-notes.md")

    # This half is checkable everywhere and is the one that matters: whatever else is
    # true, the note must never be a tracked file.
    check("git does not track a private note",
          "vetagent-private-notes.md" not in tracked_files())

    if not os.path.exists(note):
        unchecked("the note exists and holds the values",
                  "no note beside the repo -- expected on a CI runner, "
                  "a real problem on the maintainer's machine")
        return
    inside = os.path.abspath(note).startswith(os.path.abspath(ROOT) + os.sep)
    check("and it is not inside the repo", not inside, note)


def test_the_guard_actually_catches_the_thing():
    """A guard nobody has watched fail is not a guard. Watch it here, on every run.

    The fixture is synthesised rather than read from the private note. Using the note was
    the original design and it was wrong twice over: it could not run in CI, and it tested
    the *data* rather than the *machinery*. This plants a value that exists only inside
    this function, so the regex, the hashing and the lookup are exercised everywhere the
    suite runs -- including on a runner that has never seen the real identifiers.
    """
    print("\n[W13] the guard fires on a planted value")
    planted = "0123456789abcdef0123456789abcdef"
    digest = hashlib.sha256(planted.encode()).hexdigest()
    fixture = {digest: "a synthetic control value"}

    hits = _scan_text("deploy with account %s today" % planted, fixture)
    check("the detector finds a planted identifier", len(hits) == 1, str(hits))

    check("and does not fire on an unrelated 32-hex token",
          not _scan_text("md5 was ffffffffffffffffffffffffffffffff", fixture))

    check("and does not fire on a 40-char git sha",
          not _scan_text("commit 5a16721" + "a" * 33, fixture))

    # The real digests must still be the ones the real scan uses.
    check("the real forbidden list is non-empty and hashed",
          len(FORBIDDEN) == 2 and all(len(d) == 64 for d in FORBIDDEN),
          str(list(FORBIDDEN)[:1]))


def main():
    print("=" * 68)
    print("W13: private identifiers stay out of the public repository")
    print("=" * 68)
    for _, fn in sorted((k, v) for k, v in globals().items() if k.startswith("test_")):
        fn()
    print("\n" + "=" * 68)
    print("%d passed, %d failed, %d not checked here"
          % (_PASSED, len(_FAILURES), len(_UNCHECKED)))
    for name, why in _UNCHECKED:
        print("  ----  %s  (%s)" % (name, why))
    if _FAILURES:
        print("\nFailures:")
        for name, detail in _FAILURES:
            print("  - %s  %s" % (name, detail))
        return 1
    print("All passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
