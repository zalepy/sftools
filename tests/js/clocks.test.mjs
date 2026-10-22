// Fit the last building's clock (ticket 047), and the clock boxes. Run: node --test tests/js/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fitLastClock, clockGroups, clockBoxes } from '../../src/sftools/web/static/js/clocks.js';

const fit = (need, scale = Math.ceil(need)) => fitLastClock({ ideal_building_scale: need, building_scale: scale });
const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-6, `${actual} != ${expected}`);

const RULES = [
    [4.3, 4, 1.3],       // one fewer, last at 130% (1 shard)
    [1.2, 1, 1.2],
    [3.6, 4, 0.6],       // one fewer needs 160%: the last underclocked instead
    [5.3, 6, 0.3],       // one fewer would be 5: underclocked
    [7.2, 8, 0.2],       // one fewer would be 7: underclocked
    [4.8, 4, 1.8],       // 5 avoided: 4 with 2 shards
    [6.9, 6, 1.9],       // 7 avoided: 6 with 2 shards
    [6.3, 6, 1.3],       // one fewer than 7, last at 130%
    [0.4, 1, 0.4],
    [2 / 3, 1, 0.666667],  // rounded up to 4 decimals of a percent
];

for (const [need, count, clock] of RULES) {
    test(`fit ${+need.toFixed(3)} buildings: ${count}, the last at ${clock * 100}%`, () => {
        const result = fit(need);
        assert.equal(result.count, count);
        close(result.clock, clock);
        assert.ok(result.clock >= need - (count - 1) - 1e-12, 'never short');
        assert.deepEqual(result.groups, [{ clock: 1 }, { count: 1, clock: result.clock }]);
    });
}

test('nothing to fit', () => {
    assert.equal(fit(3, 3).why, 'No surplus to fit.');
    assert.equal(fit(0, 1).why, 'Nothing is demanded from this node.');
    assert.equal(fit(5.005).count, 5);  // 6 with the last under 1%: 5, just over 100%
});

test('clock groups from the boxes', () => {
    assert.equal(clockGroups(NaN, NaN), null);
    assert.equal(clockGroups(100, NaN), null);
    assert.equal(clockGroups(100, 100), null);
    assert.deepEqual(clockGroups(NaN, 50), [{ clock: 1 }, { count: 1, clock: 0.5 }]);
    assert.deepEqual(clockGroups(80, NaN), [{ clock: 0.8 }]);
    assert.deepEqual(clockGroups(80, 80), [{ clock: 0.8 }]);
});

test('the boxes show what the groups set, empty for the default', () => {
    assert.deepEqual(clockBoxes(undefined), { all: '', last: '' });
    assert.deepEqual(clockBoxes([{ clock: 1 }, { count: 1, clock: 0.666667 }]), { all: '', last: 66.6667 });
    assert.deepEqual(clockBoxes([{ clock: 0.8 }]), { all: 80, last: '' });
    // What the boxes show reads back as the same groups
    const groups = [{ clock: 1.25 }, { count: 1, clock: 0.5 }];
    const boxes = clockBoxes(groups);
    assert.deepEqual(clockGroups(boxes.all, boxes.last), groups);
});
