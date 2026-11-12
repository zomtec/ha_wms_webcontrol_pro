# AGENTS.md

Binding rules for AI agents working on this repository. They take precedence over
default agent behavior. When a rule conflicts with a user request, say so and ask.

## Project

Custom Home Assistant integration (HACS) for the Warema WMS WebControl pro gateway,
domain `wms_webcontrol_pro`. Device logic lives in the library
[`pywmswebcontrolpro`](https://github.com/zomtec/pywmswebcontrolpro). The domain must
never be `wmspro`, that would replace the core integration.

## Architecture rules

1. Entities never depend on each other. A cover does not read a number entity, both use
   the same methods of the library.
2. No virtual configuration entities without a counterpart in the API. Number entities
   that only write a value into the library are fine.
3. Workarounds for device bugs belong into the library. The integration shows the result
   without extra logic.
4. Persistent data is stored by the library. Attributes and `RestoreEntity` are no
   storage for learned or configured values.
5. Polling is done by the coordinator and is dynamic: rarely when idle, once shortly
   after a command. The library locks parallel requests. Intervals and retries are
   backed by measurements.
6. No private members of the library, the library offers public methods for everything
   the integration needs. The manifest pins the exact library version.
7. Small, separately reviewable changes. Extensions come in follow-up changes.
8. Document vendor bugs where a workaround is needed: what the bug is, where it was
   reported and when the workaround can go.

## Working rules

- Read the affected code and its tests before changing anything.
- Make the smallest change that solves the task. No unrequested refactoring.
- Ask before architectural changes, dependency changes, breaking changes (domain,
  `unique_id`, entity keys, stored data), raising the minimum Home Assistant version,
  or changing `.github/workflows/`, `hacs.json` or `ruff.toml`.

## Code rules

- Python 3.14: `except A, B:` without parentheses where no `as` is used, annotations
  without quotes. Full type annotations everywhere.
- Ruff and mypy are the source of formatting and lint rules (`ruff.toml`, `mypy.ini`).
  Never add `# noqa` or `# type: ignore` without a one-line reason.
- Comments are short and explain why, never what. No section dividers, no hints at
  earlier states of the code.
- `try` blocks as small as possible. A guaranteed key is read directly with `data["key"]`.
- Admin services use `async_register_admin_service`.
- Texts only in `strings.json` in English, mirrored in `translations/en.json` and
  `translations/de.json`.
- Language of code, comments, commits, issues and pull requests is English.

## Tests

- `pytest` with `pytest-homeassistant-custom-component`, no real hardware or network.
  The gateway is mocked at the HTTP level (`tests/conftest.py`), the library runs for real.
- Type annotations on all test parameters, `usefixtures` for unused fixtures, no
  branches in tests, `parametrize` instead of duplicates, snapshots with Syrupy.
- Every behavior change comes with a test.

Run before declaring work done:

```bash
ruff check .
ruff format --check .
mypy
python -m pytest
```

## Release

`manifest.json` keeps `"version": "0.0.0"`. The release workflow writes the tag into it
and attaches `wms_webcontrol_pro.zip` to the GitHub release. Publishing the library
to PyPI and the integration to HACS is done by the owner.
