<!--
DRAFT B (revision 2) for the website's docs-src/install.md, Linux section only. Not published.
Replaces the current "## Linux" block (Snap / Fedora / pipx).

Structure: distro names are the headings; architecture is a note inside each
heading, never a heading of its own. Ubuntu leads with Snap and says no more
(owner's call, 20 Nov 2026: people comfortable with other routes will find them).
Everyone else leads with their own route.

Facts used are only the ones the current page already states: Snap is amd64 and
--edge only; Copr is Fedora 43 x86_64; pipx/uv works anywhere with Python and
needs FFmpeg installed by the reader.

[CHECK] marks something nobody has run. Delete each marker, or the line, once
checked. Do not publish with any left.
  1. Linux Mint blocks Snap by default: CHECKED 20 Nov 2026 (nosnap.pref; Mint 22
     release notes and Snapcraft's Mint page). Debian not shipping snapd: from
     memory, not yet checked.
  2. `sudo pacman -S ffmpeg` on Arch.
  3. Bristlenose installing and running on Raspberry Pi OS. Unknown: 32-bit
     Raspberry Pi OS (dependency wheels), and whether transcription is fast
     enough on a Pi to be useful. If only 64-bit works, say "64-bit only".
  4. pipx itself: the steps assume it is installed. `sudo apt install pipx` on
     Debian/Raspberry Pi OS needs confirming; Fedora and Arch not checked.
-->

## Linux

Find your distribution below.

| OS | Install with |
|---|---|
| Ubuntu | [Snap](#ubuntu) |
| Fedora | [Fedora package](#fedora) on release 43, otherwise [pipx](#install-with-pipx) |
| Debian, Raspberry Pi OS, Linux Mint, Arch and anything else | [pipx](#install-with-pipx) |

### Ubuntu

```
sudo snap install bristlenose --edge
```

The Snap bundles Python and FFmpeg, so there is nothing else to install. The transcription model downloads the first time you run an analysis.

The `--edge` flag is needed because there is no stable release on the Snap Store yet. The Snap is built for 64-bit Intel and AMD computers (x86_64); on an ARM computer, [install with pipx](#install-with-pipx) instead.

Recordings in your home directory work straight away. If yours are on a USB stick or an external drive, grant access once:

```
sudo snap connect bristlenose:removable-media
```

### Debian, Raspberry Pi OS and Linux Mint

These systems don't use Snap: Debian doesn't include it, and Linux Mint blocks it by default. [CHECK 1] Install with pipx, using `apt` for FFmpeg:

```
sudo apt install ffmpeg pipx
pipx install bristlenose
```

[CHECK 3, 4] This works on 64-bit and ARM systems alike, including a Raspberry Pi.

### Fedora

On Fedora 43 for x86_64:

```bash
sudo dnf copr enable cassiocassio/bristlenose
sudo dnf install bristlenose
```

Copr is Fedora's community build service, the equivalent of a PPA. The first command adds the repository, the second installs from it, and `sudo dnf upgrade` keeps it current.

The package bundles Python and everything Bristlenose needs, and pulls FFmpeg from Fedora's own repositories. `ffmpeg-free` handles everything Teams, Zoom and Meet produce; it cannot decode HEVC, the format phones use, so those recordings get no thumbnail in the report. They still transcribe normally. You do not need RPM Fusion.

On another Fedora release, or on an ARM computer, [install with pipx](#install-with-pipx), using `sudo dnf install ffmpeg-free` for FFmpeg.

### Arch and other distributions

[Install with pipx](#install-with-pipx). On Arch, install FFmpeg with `sudo pacman -S ffmpeg` [CHECK 2]; on other systems, use your package manager.

### Install with pipx

This works on any Linux system with Python, on any processor.

1. Install FFmpeg with your package manager.
   - Debian, Raspberry Pi OS, Linux Mint: `sudo apt install ffmpeg`
   - Fedora: `sudo dnf install ffmpeg-free`
   - Arch: `sudo pacman -S ffmpeg` [CHECK 2]
2. Install Bristlenose: `pipx install bristlenose` (or `uv tool install bristlenose`).
