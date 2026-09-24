#!/usr/bin/env bash
# Cloud Agent start: per-boot runtime state. Brings up a headless PulseAudio
# server exposing a virtual microphone that carries a steady test tone, so the
# audio-capture code paths (sounddevice / PortAudio) and their tests work on a
# machine with no sound card. Idempotent: safe to run on every boot.
#
# The daemon listens on a fixed unix socket (/tmp/ttp-pulse.socket) that
# /etc/pulse/client.conf (written by install.sh) points every client at, so
# capture works from any agent shell regardless of XDG_RUNTIME_DIR.
#
# AGENT-ONLY / DISPOSABLE IMAGE, Debian/Ubuntu + PulseAudio assumed. This starts
# a headless PulseAudio daemon and loads virtual audio modules for the whole
# machine; it is meant for a throwaway Cursor Cloud Agent VM, not a workstation.
# See .cursor/README.md for the full operational contract.
set -euo pipefail

SOCK=/tmp/ttp-pulse.socket
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/ttp-xdg-runtime}"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

# Start the daemon (listening on the fixed socket) if it is not reachable yet.
# Use -D rather than --start: client.conf pins default-server, which makes
# `pulseaudio --start` refuse to autospawn.
if ! pactl --server "unix:$SOCK" info >/dev/null 2>&1; then
  pulseaudio --daemonize=yes --exit-idle-time=-1 --log-target=stderr \
    --load="module-native-protocol-unix socket=$SOCK auth-anonymous=1"
  for _ in $(seq 1 20); do
    pactl --server "unix:$SOCK" info >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

pa() { pactl --server "unix:$SOCK" "$@"; }

# Idempotently create: null sink -> virtual source (mic) <- steady sine tone.
if ! pa list short modules | grep -q "sink_name=virtual_speaker"; then
  pa load-module module-null-sink \
    sink_name=virtual_speaker \
    sink_properties=device.description=virtual_speaker >/dev/null
fi

if ! pa list short modules | grep -q "source_name=virtual_mic"; then
  pa load-module module-virtual-source \
    source_name=virtual_mic master=virtual_speaker.monitor \
    source_properties=device.description=virtual_mic >/dev/null
fi

if ! pa list short modules | grep -q "module-sine"; then
  pa load-module module-sine sink=virtual_speaker frequency=220 >/dev/null
fi

pa set-default-source virtual_mic >/dev/null 2>&1 || true

echo "start.sh: PulseAudio virtual mic ready on unix:$SOCK"
pa list short sources 2>/dev/null || true
