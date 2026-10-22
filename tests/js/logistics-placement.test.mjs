// Where the zoomed-in logistics view puts its nodes. Run: node --test tests/js/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { placement } from '../../src/sftools/web/static/js/logistics-placement.js';

// An output side: two buildings, a merger, a splitter, two exits
const side = {
    nodes: [
        { id: 'b1', kind: 'building', building: 'b1' },
        { id: 'b2', kind: 'building', building: 'b2' },
        { id: 'm1', kind: 'merger' },
        { id: 's1', kind: 'splitter' },
        { id: 'x1', kind: 'exit' },
        { id: 'x2', kind: 'exit' },
    ],
    belts: [
        { from: 'b1', to: 'm1' }, { from: 'b2', to: 'm1' },
        { from: 'm1', to: 's1' },
        { from: 's1', to: 'x1' }, { from: 's1', to: 'x2' },
    ],
};

test('sources left, parts by belt order, sinks right', () => {
    const at = placement(side, 'out');
    assert.equal(at.b1.x, 0);
    assert.equal(at.b2.x, 0);
    assert.ok(at.m1.x > 0 && at.s1.x > at.m1.x, 'the splitter is a column after the merger');
    assert.equal(at.x1.x, at.x2.x);
    assert.ok(at.x1.x > at.s1.x);
});

test('a column keeps its nodes a row apart', () => {
    const at = placement(side, 'out');
    assert.ok(Math.abs(at.x1.y - at.x2.y) >= 72);
    assert.ok(Math.abs(at.b1.y - at.b2.y) >= 72);
});

test("the user's positions win", () => {
    const at = placement(side, 'out', { m1: { x: 5, y: 500 } });
    assert.deepEqual(at.m1, { x: 5, y: 500 });
    assert.equal(at.b1.x, 0);
});

test('on an input side the buildings are the sinks, in order', () => {
    const input = {
        nodes: [
            { id: 'e1', kind: 'entry' },
            { id: 'b2', kind: 'building', building: 'b2', item: 'Screw' },
            { id: 'b1', kind: 'building', building: 'b1', item: 'Screw' },
        ],
        belts: [{ from: 'e1', to: 'b1' }, { from: 'e1', to: 'b2' }],
    };
    const at = placement(input, 'in');
    assert.equal(at.e1.x, 0);
    assert.ok(at.b1.x > 0);
    assert.ok(at.b1.y < at.b2.y);
});
