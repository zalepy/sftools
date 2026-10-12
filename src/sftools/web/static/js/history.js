// Undo/redo: a list of plan snapshots. The server is stateless, so going back means recalculating an
// earlier plan. Snapshots are stored as JSON strings, so later changes to the state can't alter them.

const LIMIT = 50;

let entries = [];
let index = -1;

/** Adds the plan as a new step, unless it equals the current one. Drops the steps that could be redone. */
export function record(plan) {
    const json = JSON.stringify(plan);
    if (entries[index] === json) return;
    entries = entries.slice(0, index + 1);
    entries.push(json);
    if (entries.length > LIMIT) entries.shift();
    index = entries.length - 1;
}

export function canUndo() {
    return index > 0;
}

export function canRedo() {
    return index < entries.length - 1;
}

/** The previous plan, or null. */
export function undo() {
    return canUndo() ? JSON.parse(entries[--index]) : null;
}

/** The next plan, or null. */
export function redo() {
    return canRedo() ? JSON.parse(entries[++index]) : null;
}
