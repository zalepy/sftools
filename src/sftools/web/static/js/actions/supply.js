// Supply-driven power plans (ticket 057): turning the limit on or off is a change to the plan (an undo step).
import { state } from '../state.js';
import { refreshLimitControl } from '../panel/supply.js';
import { recalculate } from './plan.js';

export function setSupplyLimit(on) {
    state.supplyLimit = on;
    recalculate();
}

/** The rows changed: offer the limit or not. */
export function rowsChanged() {
    refreshLimitControl();
}
