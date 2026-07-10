#!/bin/bash
# PreToolUse hook: the FIRST time a session writes/edits a *.swift file, inject
# the native-primitives-first checklist into context. Fires once per session
# (sentinel keyed on session_id), non-blocking — a nudge, never a gate.
#
# Why this exists: the native-first rule already lives at three passive
# altitudes — the feedback_native_primitives_first.md memory, the MEMORY.md
# hot-index line, and desktop/CLAUDE.md §"Native primitives first" (which
# overrides default behaviour). All three are AMBIENT context the model is
# trusted to recall at design time. On 2026-07-10 it had all three and still
# proposed a bespoke NSSavePanel-cosplay dialog that what-would-gruber-say had
# to drag back to Mac reality. The gap wasn't knowledge, it was activation
# TIMING. This hook is the only mechanism that fires mechanically at the moment
# Swift is authored, turning the passive rule into an active interrupt.
# (Chose the once-per-session variant over content-signal grepping to keep it
# near-zero-noise / near-zero-maintenance — the goal is to catch "starting
# Swift work", not to police every edit.)
#
# Matching is on the full absolute path with a `*.swift` glob — the repo dir and
# package dir are both named `bristlenose`, so repo-relative slicing is unsafe
# (see frontend-stale-reminder.sh for the same caution).

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[ -z "$FILE_PATH" ] && exit 0

case "$FILE_PATH" in
  *.swift) ;;
  *) exit 0 ;;
esac

# Once per session. session_id is stable for the life of the conversation.
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "nosession"')
SENTINEL="${TMPDIR:-/tmp}/bn-swift-native-first-${SESSION_ID}"
[ -f "$SENTINEL" ] && exit 0
: > "$SENTINEL"

MSG="Swift edit this session — native-primitives-first checklist (desktop/CLAUDE.md §Native primitives first). macOS ships opinionated, correct, accessible primitives; the burden of proof is on DEPARTING from them. Before drawing UI: (1) Name the stock primitive that already does this job and default to it — NSSavePanel/NSOpenPanel for location/save/create-folder (also the ONLY thing that grants sandbox powerbox access), NSOutlineView for hierarchical lists, a sheet for a committed modal task, a popover for a transient light-dismiss choice, NSAlert for a confirm, SF Symbols / real file icons for glyphs. Custom is the exception that needs the written sentence 'the system primitive is X; we depart because Z' — if you can't write it, use X. (2) Never ape a system panel you aren't — copying Save As:/Where: chrome onto a hand-drawn sheet is uncanny-valley and, when sandboxed, functionally hollow. (3) Sheet vs popover: consequential/committed → sheet; transient/light-dismiss → popover; don't mix. (4) No self-narration (a field with a cursor is self-evidently editable; Cancel self-evidently cancels) and no emoji as chrome. Run what-would-gruber-say on novel native UI BEFORE the mockup, not after — if Gruber is dragging it back to Mac reality, this step got skipped."

jq -n --arg msg "$MSG" '{hookSpecificOutput: {hookEventName: "PreToolUse", additionalContext: $msg}}'
exit 0
