# 011 — POST /api/colors overwrites a tracked repo file

**Type:** bug / security · **Priority:** P2 · **Status:** Done

> **Update (2026-10-11):** `POST /api/colors` removed. The default palette ships in `src/sftools/data/node_colors.json`; user changes go to localStorage (`sf_planner_colors`).

## Problem
Any caller can overwrite `data/node_colors.json`, which is tracked in git and global to all users. On Render the file system is temporary, so changes are lost on redeploy anyway.

## Fix
- [ ] Ship the default palette as read-only package data
- [ ] Keep user color changes in client localStorage (as part of the plan export/import)
- [ ] Remove the POST endpoint, or limit it to dev mode
