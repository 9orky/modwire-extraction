# Contributing

## Development setup

Use Python 3.11 or newer.

```bash
python -m pip install -e ".[dev]"
```

Install the optional runtimes when working on the language extractors:

- Node.js 22 or newer for TypeScript, TSX, JavaScript, and JSX extraction.
- PHP 8.3 or newer with Composer for PHP extraction.

## Checks

Run the Python test suite before opening a pull request:

```bash
pytest
```

When changing the TypeScript extractor:

```bash
cd src/modwire_extraction/extractors/languages/typescript
npm ci
npm run check
npm run build
git diff --exit-code -- script.js
```

When changing the PHP extractor:

```bash
cd src/modwire_extraction/extractors/languages/php
composer install --no-interaction --prefer-dist
composer check
composer build
```

The generated `script.js` and `script.php` bundles are committed package data.
Regenerate and commit them with their source changes. The PHP PHAR bundle is
not yet enforced by a binary diff check because its current build output can
vary by environment.

## Pull request rules

- Keep changes focused on one behavior or release task.
- Add or update tests for user-visible behavior.
- Do not commit local build output from `build/`, `dist/`, virtual environments,
  dependency directories, or cache directories.
- Keep public API changes explicit in the pull request description.
- Update `README.md` when install steps, runtime requirements, or public import
  paths change.

## Release process

1. Ensure the changelog or release notes describe user-visible changes.
2. Create the release tag as `vX.Y.Z` or `X.Y.Z`.
3. Remove old local build artifacts:

   ```bash
   rm -rf build dist src/*.egg-info
   ```

4. Build and verify the package:

   ```bash
   python -m build
   twine check dist/*
   ```

5. Create and publish a GitHub Release for the version tag.

Publishing to PyPI is handled by `.github/workflows/workflow.yml` from the
`pypi` GitHub Environment using PyPI Trusted Publishing. Release builds set the
package version from the GitHub Release tag. Configure the PyPI trusted publisher
with:

- Repository owner: `9orky`
- Repository name: `modwire-extraction`
- Workflow name: `workflow.yml`
- Environment name: `pypi`
