// Undo/redo: a list of plan snapshots. The server is stateless, so going back means recalculating an
// earlier plan. Snapshots are stored as JSON strings, so later changes to the state can't alter them.
// Each plan tab has its own history (ticket 039).

const LIMIT = 50;

let entries = [];
let index = -1;
let tab = null;
const others = new Map();  // tab id -> { entries, index }

/** Switches to a tab's history (a new one for a tab not seen yet). */
export function useTab(id) {
    if (id === tab) return;
    if (tab !== null) others.set(tab, { entries, index });
    ({ entries, index } = others.get(id) || { entries: [], index: -1 });
    others.delete(id);
    tab = id;
}

/** Drops a closed tab's history. */
export function forget(id) {
    others.delete(id);
    if (id === tab) {
        entries = [];
        index = -1;
        tab = null;
    }
}

/** Drops every tab's history (a loaded book). */
export function reset() {
    others.clear();
    entries = [];
    index = -1;
    tab = null;
}

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
