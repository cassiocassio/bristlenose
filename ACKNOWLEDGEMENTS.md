# Acknowledgements

Bristlenose is built with these open-source projects.

## Python Backend

- [FastAPI](https://fastapi.tiangolo.com/) — web framework
- [Uvicorn](https://www.uvicorn.org/) — ASGI server
- [SQLAlchemy](https://www.sqlalchemy.org/) — database toolkit
- [Pydantic](https://docs.pydantic.dev/) — data validation
- [Typer](https://typer.tiangolo.com/) — CLI framework
- [Rich](https://rich.readthedocs.io/) — terminal formatting
- [Jinja2](https://jinja.palletsprojects.com/) — template engine
- [inflect](https://github.com/jaraco/inflect) — English pluralisation
- [Presidio](https://microsoft.github.io/presidio/) — PII detection
- [spaCy](https://spacy.io/) — NLP engine behind PII detection

## Transcription

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — speech recognition
- [CTranslate2](https://github.com/OpenNMT/CTranslate2) — inference engine for faster-whisper
- [MLX](https://github.com/ml-explore/mlx) & [mlx-whisper](https://github.com/ml-explore/mlx-examples) — Apple Silicon transcription
- [PyTorch](https://pytorch.org/) & [Transformers](https://huggingface.co/docs/transformers/) — transcription model stack
- [FFmpeg](https://ffmpeg.org/) — audio/video decoding and probing

## Ingest & Export

- [pysrt](https://github.com/byroot/pysrt) & [webvtt-py](https://github.com/glut23/webvtt-py) — subtitle parsing
- [python-docx](https://python-docx.readthedocs.io/) — Word document parsing
- [openpyxl](https://openpyxl.readthedocs.io/) — Excel export

## Frontend

- [React](https://react.dev/) — UI framework
- [Vite](https://vite.dev/) — build tool
- [React Router](https://reactrouter.com/) — client-side routing
- [i18next](https://www.i18next.com/) — internationalisation
- [TypeScript](https://www.typescriptlang.org/) — type system
- [Vitest](https://vitest.dev/) — test framework

## AI Providers

- [Anthropic SDK](https://docs.anthropic.com/) — Claude integration
- [OpenAI SDK](https://platform.openai.com/docs/) — ChatGPT integration
- [Google GenAI SDK](https://ai.google.dev/) — Gemini integration
- [Ollama](https://ollama.com/) — local model runner

---

This is a curated highlights list. For the full inventory of every binary
and Python wheel bundled in the macOS desktop app — with versions, licences,
and checksums — see [THIRD-PARTY-BINARIES.md](THIRD-PARTY-BINARIES.md).
