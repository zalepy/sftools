// The Planner tab: demand and inbound production rows, and the logistics settings.
import { state } from '../state.js';
import { $ } from './common.js';

const demandRows = $('demand-rows');
const inboundRows = $('inbound-rows');

function createRow(item = '', rate = '') {
    const row = document.createElement('div');
    row.className = 'demand-row';

    const itemInput = document.createElement('input');
    itemInput.type = 'text';
    itemInput.name = 'items';
    itemInput.setAttribute('list', 'items_list');
    itemInput.placeholder = 'Item';
    itemInput.value = item;

    const rateInput = document.createElement('input');
    rateInput.type = 'number';
    rateInput.step = 'any';
    rateInput.name = 'rates';
    rateInput.placeholder = 'Rate';
    rateInput.value = rate;

    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'secondary remove-row';
    remove.style.width = 'auto';
    remove.textContent = '✕';

    row.append(itemInput, rateInput, remove);
    return row;
}

export function addRow() {
    demandRows.appendChild(createRow());
}

export function addInboundRow() {
    inboundRows.appendChild(createRow());
}

// Removing the last row only clears it
[demandRows, inboundRows].forEach(rows => rows.addEventListener('click', e => {
    const button = e.target.closest('.remove-row');
    if (!button) return;
    const row = button.closest('.demand-row');
    if (rows.children.length > 1) {
        row.remove();
    } else {
        row.querySelectorAll('input').forEach(i => i.value = '');
    }
}));

/** Filled-in rows as [{item, rate}]. */
function readRows(rows) {
    const entries = [];
    rows.querySelectorAll('.demand-row').forEach(row => {
        const inputs = row.querySelectorAll('input');
        if (inputs[0].value && inputs[1].value) {
            entries.push({ item: inputs[0].value.trim(), rate: parseFloat(inputs[1].value) });
        }
    });
    return entries;
}

function fillRows(rows, entries) {
    rows.replaceChildren(...entries.map(({ item, rate }) => createRow(item, rate)));
    if (entries.length === 0) rows.appendChild(createRow());
}

/** Demand targets as items and rates, and inbound production as [{item, rate}]. */
export function getDemands() {
    const demands = readRows(demandRows);
    return { items: demands.map(d => d.item), rates: demands.map(d => d.rate), inbound: readRows(inboundRows) };
}

export function setDemands(items = [], rates = [], inbound = []) {
    fillRows(demandRows, items.map((item, i) => ({ item, rate: rates[i] })));
    fillRows(inboundRows, inbound);
}

// --- Logistics settings (ticket 033) ---

export function readLogisticsSettings() {
    return {
        belt_tier: parseInt($('belt-tier').value, 10),
        pipe_tier: parseInt($('pipe-tier').value, 10),
        smart: $('smart-splitters').checked
    };
}

export function showLogisticsSettings() {
    const settings = state.logistics.settings;
    $('belt-tier').value = String(settings.belt_tier);
    $('pipe-tier').value = String(settings.pipe_tier);
    $('smart-splitters').checked = settings.smart;
}
