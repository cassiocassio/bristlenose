#!/bin/bash
# staged-app-check.sh <share> — is there an app to install into tonight's clone?
#
# Exit 0: <share>/app-current.tar is a readable, non-empty file (a symlink to one
# counts): install it. Exit 3: it is missing, a dangling link, or empty; stdout is
# the reason, and the walk must halt with it, because the alternative is walking
# the app frozen into the base, a 30-day alpha build that ages out. Exit 4: the
# same, but GW_FROZEN_APP=1 says the owner wants the base's own app: skip the
# install. Silence here used to mean "walk the old app"; it must never again.
share="${1:?share dir}"
tar="$share/app-current.tar"
if [ -f "$tar" ] && [ -r "$tar" ] && [ -s "$tar" ]; then exit 0; fi
if [ "${GW_FROZEN_APP:-0}" = 1 ]; then exit 4; fi
if [ -L "$tar" ] && [ ! -e "$tar" ]; then
    echo "app-current.tar is a dangling link (to $(readlink "$tar"))"
elif [ -e "$tar" ] && [ ! -s "$tar" ]; then
    echo "app-current.tar is empty"
elif [ -e "$tar" ] && [ ! -f "$tar" ]; then
    echo "app-current.tar is not a file"
elif [ -e "$tar" ]; then
    echo "app-current.tar is not readable"
else
    echo "no app-current.tar in $share (stage the release build, or set GW_FROZEN_APP=1 to walk the base's own app)"
fi
exit 3
