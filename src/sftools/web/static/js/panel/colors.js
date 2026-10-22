// The Colors tab: the colored items, editing their colors, and defining colors for more items (ticket 044).
import { state } from '../state.js';
import { $ } from './common.js';

/**
 * The colored items, with the unsaved edits in `colors` (Save Colors keeps them). × on a built-in item
 * puts its built-in color back; on an item the user defined, it drops the row.
 */
export function renderColorList(colors = state.colors) {
    const container = $('color-list');
    container.replaceChildren(...Object.keys(colors).sort().map(item => {
        const row = document.createElement('div');
        row.className = 'color-item';
        row.dataset.item = item;

        const label = document.createElement('span');
        label.className = 'color-label';
        label.textContent = item;

        const wrapper = document.createElement('div');
        wrapper.className = 'color-input-wrapper';
        const input = document.createElement('input');
        input.type = 'color';
        input.className = 'color-input';
        input.value = colors[item];
        input.dataset.item = item;

        const builtIn = state.defaultColors[item];
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'color-remove';
        remove.textContent = '×';
        remove.title = builtIn ? `Reset to the built-in color (${builtIn})` : 'Remove';
        remove.addEventListener('click', () => {
            if (builtIn) {
                input.value = builtIn;
            } else {
                row.remove();
            }
        });
        wrapper.append(input, remove);

        row.append(label, wrapper);
        return row;
    }));
}

export function readColorInputs() {
    const colors = {};
    document.querySelectorAll('#color-list .color-input').forEach(input => {
        colors[input.dataset.item] = input.value;
    });
    return colors;
}

/** Wires Define: adds the item with the picked color to the list (or recolors it if it's there). */
export function initColorDefine() {
    const itemInput = $('color-add-item');
    const error = $('color-add-error');
    const items = new Set([...document.querySelectorAll('#items_list option')].map(o => o.value));

    function define() {
        const item = itemInput.value.trim();
        error.hidden = items.has(item);
        if (!items.has(item)) {
            error.textContent = item ? `Unknown item: ${item}` : 'Pick an item first.';
            return;
        }
        renderColorList({ ...readColorInputs(), [item]: $('color-add-value').value });
        itemInput.value = '';
        colorRow(item)?.scrollIntoView({ block: 'nearest' });
    }

    $('color-add-btn').addEventListener('click', define);
    itemInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') {
            e.preventDefault();
            define();
        }
    });
}

function colorRow(item) {
    return [...document.querySelectorAll('#color-list .color-item')].find(row => row.dataset.item === item);
}
