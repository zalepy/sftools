// What a node's data says as text and colors. Run: node --test tests/js/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
    textColorOn, builtStatus, statusColor, clocksText, buildingsText, inboundUnused
} from '../../src/sftools/web/static/js/node-info.js';

test('text contrasts with the node color', () => {
    assert.equal(textColorOn('#ffffff'), '#0f172a');
    assert.equal(textColorOn('#000000'), '#f8fafc');
    assert.equal(textColorOn('#facc15'), '#0f172a');  // yellow: dark text
    assert.equal(textColorOn('not a color'), '#f8fafc');
});

test('clocks as text: empty when all run at 100%', () => {
    assert.equal(clocksText({ clocks: [{ count: 4, clock: 1 }] }), '');
    assert.equal(clocksText({ clocks: [{ count: 3, clock: 1 }, { count: 1, clock: 0.5 }] }), '3 × 100% + 1 × 50%');
    assert.equal(clocksText({ clocks: [{ count: 0, clock: 1 }, { count: 1, clock: 1.333333 }] }, '×'), '1×133.33%');
});

test('buildings: whole with clocks, fractional without', () => {
    assert.equal(buildingsText({ clocks: [{ count: 4, clock: 1 }], buildings: 4 }), '4');
    assert.equal(buildingsText({ building_scale: '3.3333' }), '3.33');
});

test('status dot: shortage, surplus, a whole building spare', () => {
    const node = (scale, ideal) => ({ building_scale: scale, ideal_building_scale: ideal });
    assert.equal(statusColor(node(3, 3)), null);
    assert.equal(statusColor(node(3, 2.5)), '#22c55e');
    assert.equal(statusColor(node(3, 2)), '#3b82f6');
    assert.equal(statusColor(node(2, 2.5)), '#ef4444');
    assert.equal(statusColor({ inbound: { rate: 30, used: 20 } }), '#22c55e');
    assert.equal(inboundUnused({ inbound: { rate: '30', used: '30' } }), 0);
});

test('built marks count for the recipe they were made for', () => {
    const node = { id: 'Rotor', recipe_name: 'Rotor', building_scale: 2.4 };
    assert.deepEqual(builtStatus(node, {}), { needed: 3, built: 0, done: false, stale: null });
    assert.deepEqual(builtStatus(node, { Rotor: { count: 3, recipe: 'Rotor' } }), { needed: 3, built: 3, done: true, stale: null });
    const stale = { count: 2, recipe: 'Alternate: Steel Rotor' };
    assert.deepEqual(builtStatus(node, { Rotor: stale }), { needed: 3, built: 0, done: false, stale });
    assert.equal(builtStatus({ inbound: { rate: 1 } }, {}), null);
});
