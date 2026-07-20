# UP05-WP02 — Rollback

Phase A source rollback is a forward, reviewable return from the Phase A branch
to `3f01a6b2baef51a27caa09914b5ec75dff365e55`; it is rehearsed in an isolated
worktree and never destructively performed in the canonical checkout.

Removing the source feature does not remove user-managed runtime/model bytes.
The acquisition directory contains only owned partial and staging bytes; a
rollback never targets unrelated models, chats, settings, or any selected user
files. A restart with predecessor source continues to use only the existing
validated catalog installation behavior.
