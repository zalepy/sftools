// The chain tab's highlights (tickets 040, 061). Run: node --test tests/js/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { endStatus } from '../../src/sftools/web/static/js/chain-info.js';

const need = { kind: 'need', rate: 0.5 };
const supply = { kind: 'supply', rate: 2 };

test('a need no link feeds is marked as not linked; a supply without links is not marked', () => {
    assert.deepEqual(endStatus(need, 0, 0), { kind: 'unlinked', text: 'not linked' });
    assert.equal(endStatus(supply, 0, 0), null);
});

test('linked ends: ok, short or surplus', () => {
    assert.equal(endStatus(need, 0.5, 1).kind, 'ok');
    assert.deepEqual(endStatus(need, 0.2, 1), { kind: 'short', text: '0.30/m short' });
    assert.deepEqual(endStatus(need, 1, 1), { kind: 'surplus', text: '0.50/m more' });
    assert.deepEqual(endStatus(supply, 3, 2), { kind: 'short', text: '1.00/m short' });
    assert.deepEqual(endStatus(supply, 1.5, 1), { kind: 'surplus', text: '0.50/m spare' });
});
