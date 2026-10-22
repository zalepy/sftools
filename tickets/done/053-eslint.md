# 053 — ESLint for bugs, in CI

**Type:** chore · **Priority:** P3 · **Status:** Done

## Goal
The JS checked for bugs (undefined names, unreachable code, unused variables and the like) the way ruff checks the Python, without a style debate.

## Decisions (agreed with the user, 2026-10-22)
- **Bug rules only**, as with ruff (ticket 050): no formatting or style rules. CI reports; nothing is blocked.
- **No Node toolchain in the repo:** the rules and globals are listed in `eslint.config.mjs` (not imported from `@eslint/js` or `globals`), so `npx eslint@<version>` runs it with no `package.json` or `node_modules`.
- No `// @ts-check` for now.

## Notes
- Implemented 2026-10-22: `eslint.config.mjs` (the recommended rules that find bugs, plus `no-self-compare` and `no-use-before-define` for variables), ESLint 10.12.0. One finding on the existing code: `CSS` (as in `CSS.escape`) missing from the browser globals.
- CI steps after the Python lint now run even when an earlier one fails (`if: ${{ !cancelled() }}`), so one run shows every result. Node 24 via `actions/setup-node@v7`.
