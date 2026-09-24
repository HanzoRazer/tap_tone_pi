# Cloud Agent environment (`.cursor/`)

These files configure a **Cursor Cloud Agent** environment for `tap_tone_pi` so
an agent can install, run, test, and demo the toolchain headlessly.

- `environment.json` — default base image with `install` and `start` hooks.
- `install.sh` — one-time-per-image dependency bootstrap.
- `start.sh` — per-boot runtime state (a headless PulseAudio virtual microphone).

## Operational contract — read before reusing these scripts

**Agent-only / disposable image. Not a developer-workstation setup.** These
scripts intentionally make machine-wide changes that are appropriate for a
throwaway Cloud Agent VM and inappropriate for a shared or personal machine:

- install system packages via `apt-get`;
- write `/etc/asound.conf` — routes ALSA's default device to PulseAudio (written
  only if absent);
- write `/etc/pulse/client.conf` — pins a fixed PulseAudio socket so any agent
  shell reaches the daemon without `XDG_RUNTIME_DIR` (rewritten on each install
  so the socket setting is authoritative);
- install Python packages into the **system interpreter** with
  `pip --break-system-packages` (see below);
- run a headless PulseAudio daemon and load virtual audio modules for the whole
  machine (`start.sh`).

Do not run these on a machine whose global audio or Python configuration you
care about.

### Runtime assumption (explicit)

The bootstrap assumes a **Debian/Ubuntu-based** image providing:

- `sudo` available non-interactively, and `apt-get`;
- the Debian/Ubuntu package names listed in `install.sh` (`SYS_PKGS`);
- PulseAudio (`pulseaudio`, `pulseaudio-utils`, `libasound2-plugins`), started
  per boot by `start.sh`.

On any other distribution or package manager, the commands do not apply.

### Why a virtual microphone

`tap_tone_pi` has audio-capture tests gated by `@requires_sounddevice`. Once
PortAudio is installed those tests run rather than skip, so `start.sh` provides a
virtual input device carrying a steady 220 Hz tone — this lets the tests pass on
a machine with no sound card instead of masking them.

### Intentional design choices (reviewed, not defects)

- **System Python via `--break-system-packages`.** Deliberate: the image is
  dedicated to this repository, and this gives every shell a global `ttp` /
  `pytest` without venv activation. The trade-off is less isolation than a venv,
  so this image should not be reused for unrelated projects that might collide on
  dependencies. Not something to "fix" with a venv here.
- **grep-based PulseAudio idempotency.** `start.sh` checks
  `pactl list short modules` with `grep` before loading each module. This is a
  pragmatic guard, not a PulseAudio management layer. If a future base image
  changes module string formats and modules start double-loading or failing,
  harden it then using explicit `pactl` source/module enumeration — otherwise
  leave it alone.
