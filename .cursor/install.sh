#!/usr/bin/env bash
# Cloud Agent install: idempotent setup of tap_tone_pi's runtime + dev deps.
# Runs after the repository is checked out. Safe to re-run.
set -euo pipefail

cd "$(dirname "$0")/.."

# ---- System packages -------------------------------------------------------
# Native libs required by the toolchain:
#   - libportaudio2            -> sounddevice (audio capture)
#   - Qt/xcb/GL/font libs      -> PyQt6 desktop analyzer
#   - python3-tk / tk          -> Tkinter timeline GUI (tap_tone_pi.gui)
#   - xvfb + x11-utils         -> headless rendering for the GUIs
#   - pulseaudio + alsa plugin -> virtual audio device (see start.sh)
SYS_PKGS=(
  libportaudio2
  libgl1 libegl1 libglib2.0-0 libdbus-1-3
  libxkbcommon0 libxkbcommon-x11-0
  libxcb1 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1
  libxcb-randr0 libxcb-render0 libxcb-render-util0 libxcb-shape0
  libxcb-shm0 libxcb-sync1 libxcb-util1 libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1
  libxrender1 libxi6 libfontconfig1 libfreetype6
  xvfb x11-utils
  python3-tk tk
  python-is-python3
  pulseaudio pulseaudio-utils libasound2-plugins
)

missing=()
for pkg in "${SYS_PKGS[@]}"; do
  dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done
if [ "${#missing[@]}" -gt 0 ]; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends "${missing[@]}"
fi

# Route ALSA's default device through PulseAudio so PortAudio (sounddevice)
# can see the virtual microphone created in start.sh.
if [ ! -f /etc/asound.conf ]; then
  printf 'pcm.!default pulse\nctl.!default pulse\n' | sudo tee /etc/asound.conf >/dev/null
fi

# Point every PulseAudio client at a fixed daemon socket so any agent shell can
# reach the daemon started by start.sh without needing XDG_RUNTIME_DIR set.
sudo tee /etc/pulse/client.conf >/dev/null <<'EOF'
default-server = unix:/tmp/ttp-pulse.socket
autospawn = no
EOF

# ---- Python packages -------------------------------------------------------
# System interpreter is PEP 668 "externally managed"; this is a disposable
# Cloud Agent VM, so installing into it (with the override) is intentional and
# gives every shell a global `ttp` / `pytest` without venv activation.
PIP=(python3 -m pip install --break-system-packages -q)

"${PIP[@]}" -r requirements-dev.txt -r requirements.txt
"${PIP[@]}" -e ".[dev,server]"

echo "install.sh complete: $(python3 -c 'import tap_tone_pi, sys; print("tap_tone_pi", getattr(tap_tone_pi, "__version__", ""))' 2>/dev/null || echo 'tap_tone_pi importable')"
