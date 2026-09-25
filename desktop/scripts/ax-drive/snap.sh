#!/bin/zsh
# One snapshot of the real app: window, split-view children, web area, and the
# SPA rects WebKit exposes (.center, the first TOC entry). Pair with the
# sidebar-fit trace (README). Usage: BNDRIVE_PID=<pid> ./snap.sh "<label>"
HERE=${0:A:h}
BN="$HERE/bndrive"
[ -x "$BN" ] || { echo "build first: cd $HERE && swiftc -O -framework AppKit -o bndrive bndrive.swift" >&2; exit 2; }
echo "----- SNAP: $1  ($(date '+%H:%M:%S'))"
"$BN" window | head -1
"$BN" summary | grep -E 'child:|AXWebArea|AXOutline' | grep -v 'web child' | cut -c1-200
for c in layout toc-sidebar center tags-sidebar; do "$BN" find "$c" | grep -E "dom\.([^ ]*,)?$c(,| )" | grep -vE 'AXStaticText|AXButton' | head -2 | sed -E 's/orient=[^ ]+ //' | cut -c1-160; done
"$BN" find signal-entry | head -1 | sed -E "s/orient=[^ ]+ //" | cut -c1-140
"$BN" tree 3 0 | grep -E 'AXButton desc="(Hide|Show) Sidebar"' | cut -c1-120
[ -n "$BNDRIVE_TRACE" ] && echo "trace lines: $(wc -l < "$BNDRIVE_TRACE")"
