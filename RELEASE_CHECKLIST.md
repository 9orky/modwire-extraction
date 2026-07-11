# 1.0.0 Release Checklist

Required before publishing `modwire-extraction` 1.0.0:

- Decide and add the project license. Add a `LICENSE` file and matching
  `license` metadata in `pyproject.toml`. Done: MIT.
- Configure PyPI Trusted Publishing for GitHub Actions:
  - Repository owner: `modwire`
  - Repository name: `modwire-extraction`
  - Workflow name: `release.yml`
  - Environment name: `pypi`
- Publish releases from an existing strict SemVer tag named `vX.Y.Z`. The build backend
  derives the package version from that tag and the reusable workflow verifies the
  generated artifact filenames match the tag.
- Resolve or explicitly document dependency graph semantics. Current graph
  edges use normalized import strings, so imports such as
  `domain/model/user` are not tracked as the source ID
  `src/domain/model/user`. Done: documented in `README.md` and
  `CHANGELOG.md`.
- Add a serialized `CodeMap` schema/version compatibility contract before
  treating JSON payloads as stable across releases. Done for 1.0.0:
  documented as same-version interchange only.
- Fix strict Pyright errors before making type checking a required CI gate.
  Done for 1.0.0: Pyright remains a development check and is not a required CI
  release gate.
- Make the PHP PHAR bundle build deterministic across environments before
  enforcing a binary `script.php` diff check in CI. Done for 1.0.0: CI does
  not enforce a binary `script.php` diff check.
- Decide whether helper build files such as `build.mjs`, `package.json`,
  `composer.json`, and lockfiles are intentional wheel runtime assets or
  sdist-only build inputs. Done: documented as intentional package data for
  bundled extractor runtimes and maintenance.

Recommended local release verification:

```bash
pytest
python -m build
twine check dist/*
```
