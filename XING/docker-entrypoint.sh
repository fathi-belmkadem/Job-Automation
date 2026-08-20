#!/bin/sh
set -e

# headless=False is used throughout the pipeline (tuned to reduce bot
# detection on XING) — start a virtual display instead of switching the
# scraping code to headless mode. xvfb-run itself proved unreliable inside
# this base image (its SIGUSR1 ready-signal handshake with Xvfb never
# fires), so start Xvfb directly and poll for its socket instead.
Xvfb :99 -screen 0 1280x1024x24 -nolisten tcp &

ready=""
for i in $(seq 1 20); do
    if [ -e /tmp/.X11-unix/X99 ]; then
        ready=1
        break
    fi
    sleep 0.5
done

if [ -z "$ready" ]; then
    echo "FATAL: Xvfb did not come up within 10s — refusing to start with a broken display." >&2
    exit 1
fi

export DISPLAY=:99

exec gunicorn --chdir src -b 0.0.0.0:5000 --timeout 120 --workers 1 dashboard:app
