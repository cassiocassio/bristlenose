/** Acknowledgements section — open-source dependency credits. */

import { useTranslation } from "react-i18next";

interface Dep {
  name: string;
  url: string;
  description: string;
}

const PYTHON: Dep[] = [
  { name: "FastAPI", url: "https://fastapi.tiangolo.com/", description: "Web framework" },
  { name: "SQLAlchemy", url: "https://www.sqlalchemy.org/", description: "Database toolkit" },
  { name: "Pydantic", url: "https://docs.pydantic.dev/", description: "Data validation" },
  { name: "Typer", url: "https://typer.tiangolo.com/", description: "CLI framework" },
  { name: "Rich", url: "https://rich.readthedocs.io/", description: "Terminal formatting" },
  { name: "faster-whisper", url: "https://github.com/SYSTRAN/faster-whisper", description: "Speech recognition" },
  { name: "Jinja2", url: "https://jinja.palletsprojects.com/", description: "Template engine" },
  { name: "Presidio", url: "https://microsoft.github.io/presidio/", description: "PII detection" },
];

const FRONTEND: Dep[] = [
  { name: "React", url: "https://react.dev/", description: "UI framework" },
  { name: "Vite", url: "https://vite.dev/", description: "Build tool" },
  { name: "React Router", url: "https://reactrouter.com/", description: "Client-side routing" },
  { name: "i18next", url: "https://www.i18next.com/", description: "Internationalisation" },
  { name: "TypeScript", url: "https://www.typescriptlang.org/", description: "Type system" },
  { name: "Vitest", url: "https://vitest.dev/", description: "Test framework" },
];

const AI: Dep[] = [
  { name: "Anthropic SDK", url: "https://docs.anthropic.com/", description: "Claude integration" },
  { name: "OpenAI SDK", url: "https://platform.openai.com/docs/", description: "ChatGPT integration" },
  { name: "Google GenAI SDK", url: "https://ai.google.dev/", description: "Gemini integration" },
  { name: "Ollama", url: "https://ollama.com/", description: "Local model runner" },
];

function DepList({ deps }: { deps: Dep[] }) {
  return (
    <ul>
      {deps.map((d) => (
        <li key={d.name}>
          <a href={d.url} target="_blank" rel="noopener noreferrer">
            {d.name}
          </a>
          {" — "}
          {d.description}
        </li>
      ))}
    </ul>
  );
}

export function AcknowledgementsSection() {
  const { t } = useTranslation();
  return (
    <>
      <p>{t("help.acknowledgements.intro")}</p>

      <h3>{t("help.acknowledgements.python")}</h3>
      <DepList deps={PYTHON} />

      <h3>{t("help.acknowledgements.frontend")}</h3>
      <DepList deps={FRONTEND} />

      <h3>{t("help.acknowledgements.ai")}</h3>
      <DepList deps={AI} />
    </>
  );
}
