// The Planner tab's limit for power plans (ticket 057): the checkbox, offered while the rows demand only fuels
// with inbound production, and what the limited plan burns and uses.
import { state } from '../state.js';
import { canLimit, summaryText, rowLines } from '../supply-info.js';
import { $ } from './common.js';
import { getDemands } from './planner.js';

/** Shows the checkbox when the rows allow the limit, ticked as the plan says; hides the summary otherwise. */
export function refreshLimitControl() {
    const offered = canLimit(getDemands(), state.power.fuels);
    $('supply-limit-group').style.display = offered ? 'block' : 'none';
    $('supply-limit').checked = state.supplyLimit;
    if (!offered) showSupply(null);
}

/** The server's `supply`: the limit, the power, and a line per fuel and inbound row; nothing unless active. */
export function showSupply(supply) {
    const summary = $('supply-summary');
    if (!supply || !supply.active) {
        summary.replaceChildren();
        summary.style.display = 'none';
        return;
    }
    summary.replaceChildren(...[summaryText(supply), ...rowLines(supply)].map((text, i) => {
        const line = document.createElement('div');
        line.textContent = text;
        if (i === 0) line.className = 'supply-headline';
        return line;
    }));
    summary.style.display = 'block';
}
