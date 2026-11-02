# 061 — Chain tab: mark inbound production no link supplies

**Type:** feature · **Priority:** P2 · **Status:** Done · **Related:** [040](040-chain-tab.md)

> **Done (2026-11-02).** `endStatus` in `static/js/chain-info.js` (pure, `tests/js/chain-info.test.mjs`) gives a need without links the status `unlinked` ("not linked"); the Chain tab draws it with a dashed orange border. Browser test: `test_the_chain_tab_links_plans`.

## Goal
On the Chain tab, a need (inbound production) without a link was drawn plain grey, the same as a supply without one. Moving a link to another tab (e.g. Fused Modular Frames from FFRM to RAD instead of NUPA) left NUPA's need unsupplied, and only the missing green border showed it. Requested 2026-11-02.

## Rule
- A need with no link: dashed orange border, and "not linked" under its rate. Orange, not red: red is a link's shortfall; dashed, so it reads as missing rather than as a rate.
- A supply with no link stays plain: a plan's demand target is often its own product, not meant for another tab.
- Linked ends as before: red short, blue spare or more, green matches.
