// The reference layouts' drawing (ticket 056). Run: node --test "tests/js/*.test.mjs"
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { escapeXml, buildingTitle, layoutSvg, powerNote } from '../../src/sftools/web/static/js/layout-svg.js';

const LAYOUT = JSON.parse(readFileSync(new URL('../../src/sftools/web/static/layouts/turbofuel-power.json', import.meta.url)));
const count = (text, pattern) => (text.match(pattern) || []).length;

test('text is escaped', () => {
    assert.equal(escapeXml(`<a & "b">`), '&lt;a &amp; &quot;b&quot;&gt;');
});

test('a building says what it runs and which pipes it is on', () => {
    const traces = [{ id: 'green', name: 'green', item: 'Fuel' }, { id: 'red-right', name: 'right red', item: 'Turbofuel' }];
    assert.equal(buildingTitle({ label: '12', recipe: 'Turbofuel', from: 'green', into: 'red-right' }, traces),
        'Refinery 12: Turbofuel, from the green Fuel pipe into the right red Turbofuel pipe');
    assert.equal(buildingTitle({ label: '21', recipe: 'Fuel', into: 'green', clock: 0.83334 }, traces),
        'Refinery 21: Fuel at 83.334%, into the green Fuel pipe');
});

test('the drawing has every building, path and label, belts under pipes', () => {
    const svg = layoutSvg(LAYOUT);
    assert.match(svg, /^<svg [^>]*viewBox="0 0 448 896"/);
    assert.equal(count(svg, /<rect /g), LAYOUT.buildings.length);
    assert.equal(count(svg, /<polyline /g), LAYOUT.traces.reduce((n, t) => n + t.paths.length, 0));
    assert.equal(count(svg, /<circle /g), LAYOUT.labels.filter(l => l.color).length);
    assert.ok(svg.indexOf('data-id="coal"') < svg.indexOf('data-id="green"'));
    assert.ok(svg.includes('>500</text>'));  // the green pipe's last total
});

test('the power note adds up what the build draws', () => {
    const note = powerNote(LAYOUT);
    assert.match(note, /^Power used: 3,097 MW of the 25,000 MW \(21,903 MW net\): 60 Refineries 1,800 MW, 3 Refineries at 83\.334% 71 MW, /);
    assert.ok(note.includes('1 Resource Well Pressurizer at 250% (3 pure and 3 normal extractors: 1,350 Crude Oil) 504 MW'));
    assert.equal(powerNote({ ...LAYOUT, power: [] }), '');
});
