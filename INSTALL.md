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

These instructions assume you've never used the command line before. That's fine — just follow each step.

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

Once available in the Snap Store, this will be the easiest option — it bundles everything:

```bash
sudo snap install bristlenose --classic
```

This is pending Snap Store registration. In the meantime, use the pipx instructions above.

### Other distributions

Install Python 3.10+, pipx, and FFmpeg using your distribution's package manager, then:

```bash
pipx install bristlenose
```

> If you use [uv](https://docs.astral.sh/uv/): `uv tool install bristlenose`

---

## Set up your AI provider

Bristlenose uses AI to analyse your transcripts. You need one of these three options. (Transcription — converting audio to text — works without any provider.)

### Option 1: Local AI (Ollama) — free, private, no signup

Run everything on your own machine using open-source models. No account needed, no data leaves your laptop.

The easiest way: just run `bristlenose run ./your-interviews/` and bristlenose will offer to set up Ollama for you automatically — it handles installation, startup, and model download.

Or install Ollama yourself from [ollama.ai](https://ollama.ai) and run:

```bash
bristlenose run ./your-interviews/ --llm local
```

**Trade-offs:** Local models are slower and less accurate than cloud APIs. Good for trying the tool; use Claude or ChatGPT for production studies.

### Option 2: Claude — best quality (~$1.50 per study)

1. Go to [console.anthropic.com](https://console.anthropic.com) and create an account
2. Add a payment method (billing is pay-as-you-go)
3. Go to [API Keys](https://console.anthropic.com/settings/keys) and create a new key
4. Store it securely:

   ```bash
   bristlenose configure claude
   ```

   This validates your key and stores it in your system's keychain (macOS Keychain or Linux Secret Service). You only need to do this once.

   On Windows (or if you prefer environment variables):

   ```bash
   export BRISTLENOSE_ANTHROPIC_API_KEY=sk-ant-...
   ```

### Option 3: ChatGPT (~$1.00 per study)

1. Go to [platform.openai.com](https://platform.openai.com) and create an account
2. Add a payment method (billing is pay-as-you-go)
3. Go to [API Keys](https://platform.openai.com/api-keys) and create a new key
4. Store it securely:

   ```bash
   bristlenose configure chatgpt
   ```

   On Windows (or if you prefer environment variables):

   ```bash
   export BRISTLENOSE_OPENAI_API_KEY=sk-...
   ```

To use ChatGPT instead of the default (Claude), add `--llm chatgpt`:

```bash
bristlenose run ./your-interviews/ --llm chatgpt
```

> **Important:** A ChatGPT Plus or Pro subscription does **not** include API access. The API is billed separately. Likewise for Claude Pro/Max subscriptions.

### Which should I pick?

| | Cost | Quality | Speed | Setup |
|---|---|---|---|---|
| **Local (Ollama)** | Free | Good | ~10 min/study | No signup |
| **Claude** | ~$1.50/study | Excellent | ~2 min/study | Account + payment |
| **ChatGPT** | ~$1.00/study | Excellent | ~2 min/study | Account + payment |

**Just trying it?** Start with Local. **Running a real study?** Use Claude or ChatGPT.

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
