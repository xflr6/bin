#!/bin/sh

SSH_ENV="${HOME}/.ssh/environment"

start_agent() {
    echo "Starting new ssh-agent..."
    /usr/bin/ssh-agent -s -a "${HOME}/.ssh/auth.sock" | head -2 > "${SSH_ENV}"
    chmod 600 "${SSH_ENV}"
    source "${SSH_ENV}"
}

if [ -z "${SSH_AUTH_SOCK}" ]; then
    if [ -f "${SSH_ENV}" ]; then
        source "${SSH_ENV}"
        kill -0 "${SSH_AGENT_PID}" 2> /dev/null || { start_agent; }
    else
        start_agent;
    fi
fi
