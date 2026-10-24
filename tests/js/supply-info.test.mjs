// Supply-driven power plans (ticket 057). Run: node --test tests/js/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { canLimit, isLimited, chainEnds, summaryText, rowLines } from '../../src/sftools/web/static/js/supply-info.js';

const power = { fuels: ['Fuel', 'Coal', 'Turbofuel'], raw: ['Coal', 'Crude Oil', 'Water'] };
const plan = {
    items: ['Fuel'], rates: [1], supplyLimit: true,
    inbound: [{ item: 'Crude Oil', rate: 300 }, { item: 'Steel Beam', rate: 50 }]
};

test('the limit is offered when only fuels are demanded and there is inbound production', () => {
    assert.ok(canLimit(plan, power.fuels));
    assert.ok(!canLimit({ ...plan, items: ['Fuel', 'Plastic'] }, power.fuels));
    assert.ok(!canLimit({ ...plan, inbound: [] }, power.fuels));
    assert.ok(!canLimit({ ...plan, items: [] }, power.fuels));
    assert.ok(!isLimited({ ...plan, supplyLimit: false }, power.fuels));
    assert.ok(!isLimited({ ...plan, items: ['Plastic'] }, power.fuels));  // the checkbox stays, the rule doesn't hold
});

test('a limited plan gives no fuel to the chain, and needs only its non-raw inbound rows', () => {
    assert.deepEqual(chainEnds(plan, power), { supplies: [], needs: [{ item: 'Steel Beam', rate: 50 }] });
    assert.deepEqual(chainEnds({ ...plan, supplyLimit: false }, power), {
        supplies: [{ item: 'Fuel', rate: 1 }], needs: plan.inbound
    });
});

test('the summary names the limit and the power', () => {
    const supply = { limit: 'Crude Oil', power: { gross: 2500, net: 2199.6 } };
    assert.equal(summaryText(supply), 'Limited by Crude Oil · 2,500 MW gross / 2,200 net');
    assert.match(summaryText({ ...supply, limit: null }), /^The plan uses none of the inbound/);
});

test('a line per fuel and inbound row', () => {
    const supply = {
        demands: [{ item: 'Fuel', rate: 200 }],
        rows: [
            { item: 'Crude Oil', rate: 300, used: 312, limit: true, unused: false },
            { item: 'Coal', rate: 100, used: 50, limit: false, unused: false },
            { item: 'Iron Ore', rate: 10, used: 0, limit: false, unused: true }
        ]
    };
    assert.deepEqual(rowLines(supply), [
        'Fuel: 200.00/min burned',
        'Crude Oil: 312.00 of 300.00/min, the limit (12.00 over: whole buildings)',
        'Coal: 50.00 of 100.00/min',
        'Iron Ore: unused'
    ]);
});

test('what is made from by-products is a supply of the plan, limited or not (ticket 059)', () => {
    const made = [{ item: 'Plastic', rate: 50, from: 'Rocket Fuel__Fuel|Polymer Resin' }];
    assert.deepEqual(chainEnds({ ...plan, made }, power).supplies, [{ item: 'Plastic', rate: 50 }]);
    assert.deepEqual(chainEnds({ ...plan, made, supplyLimit: false }, power).supplies, [
        { item: 'Fuel', rate: 1 }, { item: 'Plastic', rate: 50 }
    ]);
});
