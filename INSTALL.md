# Installing Bristlenose

Bristlenose is a user research interview analysis tool. It takes a folder of interview recordings and produces a browsable HTML report with quotes, themes, and insights.

Pick your platform below. Each section is self-contained — you only need to read the one that applies to you.

---

## macOS

### Recommended: Homebrew

Homebrew handles Python, FFmpeg, and all dependencies for you. One command:

```bash
brew install cassiocassio/bristlenose/bristlenose
```

Then trust the formula, so `brew upgrade` keeps Bristlenose current:

```bash
brew trust --formula cassiocassio/bristlenose/bristlenose
```

Homebrew 6.0 and later skip formulae from third-party taps during `brew upgrade` unless you trust them. Without this step Bristlenose installs and runs fine, but silently stops receiving updates.

**Don't have Homebrew?** Open Terminal (press Cmd + Space, type "Terminal", hit Enter) and paste:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the prompts, then run the `brew install` command above.

### Alternative: pipx

If you prefer not to use Homebrew:

1. **Check Python is installed** (macOS ships with Python 3 since Catalina):

   ```bash
   python3 --version
   ```

   If this prints a version number (3.10 or higher), you're good. If not, download Python from [python.org/downloads](https://www.python.org/downloads/).

2. **Install pipx:**

   ```bash
   python3 -m pip install --user pipx
   python3 -m pipx ensurepath
   ```

   Close and reopen Terminal.

3. **Install bristlenose:**

   ```bash
   pipx install bristlenose
   ```

4. **Install FFmpeg** (needed for audio/video processing):

   ```bash
   brew install ffmpeg
   ```

   If you don't have Homebrew, download FFmpeg from [ffmpeg.org/download.html](https://ffmpeg.org/download.html).

> If you use [uv](https://docs.astral.sh/uv/): `uv tool install bristlenose`

---

## Windows

### Step 1: Install Python

1. Go to [python.org/downloads](https://www.python.org/downloads/) and click the big yellow **"Download Python install manager"** button
2. Open the downloaded file and click **"Install Python"**
3. A black console window then asks a few questions. Each one waits for you to type `y` or `n` and press Enter. Read the brackets: `[y/N]` means pressing Enter answers No, `[Y/n]` means it answers Yes:
   - *"…allow paths longer than 260 characters… Update setting now?"* — type **`y`**. Without it some packages may fail to install. It takes effect after your next restart
   - *"…Add commands directory to your PATH now?"* — type **`y`**. This is the step older guides call "Add python.exe to PATH"
   - *"Install CPython now? [Y/n]"*, if it asks — press **Enter** (Yes). This is the step that installs Python itself. (Answered No by mistake? No harm done: the `python --version` check below installs it the first time you run it.)
   - *"View online help?"*, if it asks — type **`n`**

   Which questions appear, and in what order, depends on your machine. Some may not appear at all, so read each one rather than counting.

To verify it worked, open a terminal (press Win + X, then click "Terminal") and type:

```
python --version
```

You should see a version number, 3.10 or higher (for example `Python 3.14.8`).

> **Prefer the classic installer?** Use the "standalone installer" link under the yellow button instead, and on its first screen tick **"Add python.exe to PATH"**.

> **Windows on Arm** (Snapdragon laptops, Surface Pro X / 11): use the Python the install manager gives you by default. It's the x64 version, which runs under emulation and installs everything Bristlenose needs. The native Arm version of Python can't install Bristlenose yet, because one of its transcription libraries has no Arm build for Windows.

### Step 2: Install pipx

pipx is a tool for installing Python applications. In the same terminal, run:

```
python -m pip install --user pipx
python -m pipx ensurepath
```

The first command may print yellow warnings that a folder "is not on PATH". That's expected — the second command fixes it. (It may also suggest running `source ~/.bashrc`; ignore that, it doesn't apply on Windows.)

**Close the terminal and open a new one** (the PATH change only takes effect in new windows).

### Step 3: Install FFmpeg

FFmpeg converts audio and video files. Bristlenose needs it to process your interview recordings.

**Option A — winget** (recommended, built into Windows 11 and most Windows 10):

```
winget install --id Gyan.FFmpeg -e --source winget
```

If winget asks you to agree to source terms the first time you use it, type `Y` and press Enter. The download is about 250 MB.

Close and reopen your terminal after this.

**Option B — manual download** (if winget isn't available):

1. Go to [github.com/BtbN/FFmpeg-Builds/releases](https://github.com/BtbN/FFmpeg-Builds/releases)
2. Download `ffmpeg-master-latest-win64-gpl.zip`
3. Extract the zip file
4. Find `ffmpeg.exe` and `ffprobe.exe` inside the `bin` folder. Bristlenose needs both
5. Copy both to `C:\Windows\System32\`

   Or, to keep things tidy, put the extracted folder somewhere permanent (e.g. `C:\ffmpeg\`) and add its `bin` subfolder to your PATH: Settings > System > About > Advanced system settings > Environment Variables > select `Path` > Edit > New > type `C:\ffmpeg\bin` > OK.

To verify, open a new terminal and type:

```
ffmpeg -version
```

### Step 4: Install bristlenose

```
pipx install bristlenose
```

This downloads about a hundred packages and takes a few minutes.

### Step 5: Verify

```
bristlenose doctor
```

This checks that Python, FFmpeg, and your AI provider are set up correctly. If anything is wrong, it tells you how to fix it.

The "Whisper model" line says *not cached* until your first transcription, which downloads the speech-recognition model (about 1.6 GB) once.

---

## Linux

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install pipx ffmpeg
pipx ensurepath
```

Close and reopen your terminal, then:

```bash
pipx install bristlenose
```

### Snap

Bundles Python and FFmpeg in a single package, so there is nothing else to install. The transcription model downloads the first time you run an analysis.

```bash
sudo snap install bristlenose --edge
```

The `--edge` flag is needed because there is no stable release on the Snap Store yet. The Snap is built for amd64 only — on ARM, use the pipx instructions above.

Recordings in your home directory work straight away. If yours are on a USB stick or an external drive, grant access once:

```bash
sudo snap connect bristlenose:removable-media
```

### Fedora

```bash
sudo dnf copr enable cassiocassio/bristlenose
sudo dnf install bristlenose
```

Copr is Fedora's community build service — the equivalent of a PPA. The first command adds
the repository, the second installs from it, and `sudo dnf upgrade` keeps it current.

The package bundles Python and everything Bristlenose needs, and pulls FFmpeg from Fedora's
own repositories. It is built for **x86_64 only** — on ARM, use pipx below.

#### Fedora without Copr

```bash
sudo dnf install pipx ffmpeg-free
pipx ensurepath
```

Close and reopen your terminal, then:

```bash
pipx install bristlenose
```

`ffmpeg-free` is Fedora's patent-free FFmpeg build, and it handles everything Bristlenose
needs — including the H.264 + AAC `.mp4` files that Teams, Zoom and Meet produce. One
exception: it cannot decode **HEVC**, the format phones and newer screen recorders use. Those
files still transcribe normally — they just get no thumbnail in the report. You do not need
RPM Fusion.

### Arch / Manjaro

```bash
sudo pacman -S python-pipx ffmpeg
pipx ensurepath
```

Close and reopen your terminal, then:

```bash
pipx install bristlenose
```

### Linux Mint

Linux Mint is Debian-based — follow the [Ubuntu / Debian](#ubuntu--debian) instructions above.

### Other distributions

Install Python 3.10+, pipx, and FFmpeg using your distribution's package manager, then:

```bash
pipx install bristlenose
```

> If you use [uv](https://docs.astral.sh/uv/): `uv tool install bristlenose`

---

## Set up your AI provider

Bristlenose uses AI to analyse your transcripts. Use whichever provider you already have an API key for — see [Getting an API key](README.md#getting-an-api-key) in the README for full details including Azure OpenAI and Gemini.

### Cloud providers (Claude, ChatGPT, or Gemini)

1. Create an account and API key at [console.anthropic.com](https://console.anthropic.com/settings/keys) (Claude), [platform.openai.com](https://platform.openai.com/api-keys) (ChatGPT), or [aistudio.google.com/apikey](https://aistudio.google.com/apikey) (Gemini)
2. Store the key securely:

   ```bash
   bristlenose configure claude      # or: bristlenose configure chatgpt
   bristlenose configure gemini
   ```

   This validates your key and saves it to your system's secure credential store:
   - **macOS** — saved to your **login keychain** (viewable in the Keychain Access app, search for "Bristlenose")
   - **Linux** — saved via **Secret Service** (GNOME Keyring / KDE Wallet)
   - **Windows** — saved to a config file in your user folder, `C:\Users\<you>\.config\bristlenose\.env`. Windows Credential Manager isn't supported yet

> **Important:** A ChatGPT Plus/Pro or Claude Pro/Max subscription does **not** include API access. The API is billed separately — you need to add a payment method in the API console.

### Local AI (Ollama) — free, no signup

Just run `bristlenose your-interviews/` — bristlenose will offer to set up Ollama automatically (installation, startup, and model download).

Or install [Ollama](https://ollama.ai) yourself and run with `--llm local`.

---

## Verify your setup

Run the built-in health check:

```bash
bristlenose doctor
```

This checks FFmpeg, your transcription backend, AI provider, network connectivity, and disk space. Run it whenever something seems wrong.

## Your first analysis

Point bristlenose at a folder containing your interview recordings:

```bash
bristlenose path-to-your-interviews/
```

The report will appear inside that folder at `bristlenose-output/`. Open the `.html` file in your browser.

---

## Troubleshooting

### "command not found" after installation

Close your terminal and open a new one. PATH changes only take effect in new windows.

If it's still not found, run:

```bash
pipx ensurepath
```

Then close and reopen the terminal again.

### FFmpeg not found

Run `bristlenose doctor` — it will tell you what's missing and how to fix it for your platform.

### Permission denied (macOS)

If macOS says the app is from an "unidentified developer", go to System Settings > Privacy & Security and click "Allow Anyway".

### Something else?

1. Run `bristlenose doctor` for a full diagnostic
2. Open an issue at [github.com/cassiocassio/bristlenose/issues](https://github.com/cassiocassio/bristlenose/issues)
