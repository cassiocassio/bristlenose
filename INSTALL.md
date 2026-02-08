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

1. Go to [python.org/downloads](https://www.python.org/downloads/) and click the big yellow "Download Python" button
2. Run the downloaded `.exe` file
3. **Important:** on the first screen, tick the checkbox that says **"Add python.exe to PATH"** — this is easy to miss and everything breaks without it
4. Click "Install Now"

To verify it worked, open a terminal (press Win + X, then click "Terminal" or "Windows PowerShell") and type:

```
python --version
```

You should see something like `Python 3.12.x`.

### Step 2: Install pipx

pipx is a tool for installing Python applications. In the same terminal, run:

```
python -m pip install --user pipx
python -m pipx ensurepath
```

**Close the terminal and open a new one** (the PATH change only takes effect in new windows).

### Step 3: Install FFmpeg

FFmpeg converts audio and video files. Bristlenose needs it to process your interview recordings.

**Option A — winget** (recommended, built into Windows 11 and most Windows 10):

```
winget install FFmpeg
```

Close and reopen your terminal after this.

**Option B — manual download** (if winget isn't available):

1. Go to [github.com/BtbN/FFmpeg-Builds/releases](https://github.com/BtbN/FFmpeg-Builds/releases)
2. Download `ffmpeg-master-latest-win64-gpl.zip`
3. Extract the zip file
4. Find `ffmpeg.exe` inside the `bin` folder
5. Copy `ffmpeg.exe` to `C:\Windows\System32\`

   Or, to keep things tidy, put the extracted folder somewhere permanent (e.g. `C:\ffmpeg\`) and add its `bin` subfolder to your PATH: Settings > System > About > Advanced system settings > Environment Variables > select `Path` > Edit > New > type `C:\ffmpeg\bin` > OK.

To verify, open a new terminal and type:

```
ffmpeg -version
```

### Step 4: Install bristlenose

```
pipx install bristlenose
```

### Step 5: Verify

```
bristlenose doctor
```

This checks that Python, FFmpeg, and your AI provider are set up correctly. If anything is wrong, it tells you how to fix it.

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

### Snap (coming soon)

Once available in the Snap Store, this will bundle Python, FFmpeg, and all dependencies into a single package:

```bash
sudo snap install bristlenose --classic
```

This is pending Snap Store registration. In the meantime, use the pipx instructions above.

### Fedora

```bash
sudo dnf install pipx ffmpeg-free
pipx ensurepath
```

Close and reopen your terminal, then:

```bash
pipx install bristlenose
```

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

Bristlenose uses AI to analyse your transcripts. Use whichever provider you already have an API key for — see [Getting an API key](README.md#getting-an-api-key) in the README for full details including Azure OpenAI.

### Cloud providers (Claude or ChatGPT)

1. Create an account and API key at [console.anthropic.com](https://console.anthropic.com/settings/keys) (Claude) or [platform.openai.com](https://platform.openai.com/api-keys) (ChatGPT)
2. Store the key securely:

   ```bash
   bristlenose configure claude      # or: bristlenose configure chatgpt
   ```

   This validates your key and saves it to your system's secure credential store:
   - **macOS** — saved to your **login keychain** (viewable in the Keychain Access app, search for "Bristlenose")
   - **Linux** — saved via **Secret Service** (GNOME Keyring / KDE Wallet)
   - **Windows** — keychain not yet supported; use `setx` to save the key permanently instead:

     ```
     setx BRISTLENOSE_ANTHROPIC_API_KEY "sk-ant-..."
     ```

     Close and reopen your terminal after running `setx`.

> **Important:** A ChatGPT Plus/Pro or Claude Pro/Max subscription does **not** include API access. The API is billed separately — you need to add a payment method in the API console.

### Local AI (Ollama) — free, no signup

Just run `bristlenose run ./your-interviews/` — bristlenose will offer to set up Ollama automatically (installation, startup, and model download).

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
bristlenose run ./path-to-your-interviews/
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
