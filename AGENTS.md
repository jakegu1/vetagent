<!-- lead-kit:start — managed by the lead kit. Change settings in lead/config.yml; re-run lead-adopt to refresh this block. -->
## How this project is run

This project uses the lead workflow. The Owner (jakegu1, the repository owner) decides money,
legal and privacy text, anything published under their name, irreversible actions, product
taste, and the agents' own permission files. An AI lead plans and coordinates; executors
implement one task spec each; reviewers verify with fresh eyes.

- **State lives in `lead/`:** `STATE.md` (in flight, next, waiting), `OWNER.md` (the Owner's
  dashboard), `QUALITY.md` (gates and ceremony levels), `tasks/` (specs), `decisions/` (ADRs),
  `config.yml` (settings).
- **Project rules and known traps:** the invariants in `lead/QUALITY.md`, and `CLAUDE.md`.
- **Starting a session as the lead:** use the `lead` skill, or read `lead/STATE.md` and follow it.
- **Implementing a task:** use `lead-execute` with the task's spec. The first commit adds the
  acceptance tests alone; they are not changed afterwards except as the spec names.
- **Reviewing:** use `lead-review` (or `lead-redteam`). Reproduce the evidence yourself and post
  your verdict yourself.
- **Never:** merge your own work; push to `master` unless you are the lead acting within
  `lead/config.yml`; put secrets in chat, commits or logs; edit agent permission files; work
  around a safety check.
- **Language:** text for the Owner is written in Chinese (zh-CN), in chat. Files in this
  repository are English only (`tests/test_english_only.py`).
<!-- lead-kit:end -->
