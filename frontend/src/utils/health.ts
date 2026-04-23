export const DEFAULT_GITHUB_ISSUES_URL =
  "https://github.com/cassiocassio/bristlenose/issues/new";
export const DEFAULT_FEEDBACK_URL = "https://bristlenose.app/feedback.php";
export const DEFAULT_TELEMETRY_URL = "https://bristlenose.app/telemetry.php";

export interface HealthResponse {
  status: string;
  version: string;
  links: {
    github_issues_url: string;
  };
  feedback: {
    enabled: boolean;
    url: string;
  };
  telemetry: {
    enabled: boolean;
    url: string;
  };
}

export const DEFAULT_HEALTH_RESPONSE: HealthResponse = {
  status: "ok",
  version: "",
  links: {
    github_issues_url: DEFAULT_GITHUB_ISSUES_URL,
  },
  feedback: {
    enabled: true,
    url: DEFAULT_FEEDBACK_URL,
  },
  telemetry: {
    enabled: true,
    url: DEFAULT_TELEMETRY_URL,
  },
};
