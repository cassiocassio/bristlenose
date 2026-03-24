/** Contributing section — how to contribute, links, licence. */

export function ContributingSection() {
  return (
    <>
      <p>
        Bristlenose is free and open source under AGPL-3.0 with a Contributor
        Licence Agreement (CLA).
      </p>

      <h3>Before committing</h3>
      <p>
        Run <code>ruff check .</code>, <code>pytest tests/</code>, and{" "}
        <code>npm run build</code> (tsc catches type errors Vitest misses).
        Version lives in <code>bristlenose/__init__.py</code> &mdash; bump
        with <code>scripts/bump-version.py</code>.
      </p>

      <h3>Translate</h3>
      <p>
        Help translate Bristlenose into your language on{" "}
        <a
          href="https://hosted.weblate.org/projects/bristlenose/"
          target="_blank"
          rel="noopener noreferrer"
        >
          Weblate
        </a>
        . No Git or JSON knowledge required.
      </p>

      <h3>Links</h3>
      <ul>
        <li>
          <a
            href="https://github.com/cassiocassio/bristlenose/blob/main/CONTRIBUTING.md"
            target="_blank"
            rel="noopener noreferrer"
          >
            Contributing guide
          </a>
        </li>
        <li>
          <a
            href="https://github.com/cassiocassio/bristlenose/issues/new"
            target="_blank"
            rel="noopener noreferrer"
          >
            Report a bug
          </a>
        </li>
        <li>
          <a
            href="https://github.com/cassiocassio/bristlenose"
            target="_blank"
            rel="noopener noreferrer"
          >
            Source code
          </a>
        </li>
      </ul>
    </>
  );
}
