#!/bin/sh
# attach to tmux grouped session mimicking 'screen -xRR'

set -e

base_session=${1:-main}

if ! tmux has-session -t "$base_session" 2> /dev/null; then
    echo "create base session $base_session"
    tmux new-session -d -s "$base_session"
    startup="$HOME/bin/$base_session.tmux"
    if [ -f $startup ]; then
        echo "source startup file $startup"
        tmux source-file "$startup"
    fi
fi

session="$base_session-$((
    $(tmux list-sessions -F "#{session_name}" | \
    sed -rn "s/^$base_session-([0-9]+)/\1/p" | \
    sort -n | tail -1)
    +  1 ))"

echo "attach to linked session $session"
tmux new-session -t "$base_session" -s "$session" \; \
    set-option destroy-unattached
