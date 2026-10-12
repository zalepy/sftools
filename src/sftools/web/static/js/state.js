// Client-side plan state and its persistence (localStorage, JSON export/import).

const PLAN_KEY = 'sf_planner_state';
const COLORS_KEY = 'sf_planner_colors';

// Mutable shared state; modules read and replace its fields.
export const state = {
    clocks: {},         // node_id -> [{clock}, {count, clock}...]: see clock groups in ticket 023
    overrides: {},      // retired building counts from older saved plans; sent once, then reported and dropped
    merges: {},         // absorbed node_id -> target node_id
    recipes: {},        // node_id -> recipe name
    splits: {},         // node_id -> number of parts
    colors: {},         // item -> color
    selectedNodeId: null
};

/** Plan in its saved/exported shape; `demands` come from the form. */
export function snapshot({ items, rates }) {
    return {
        items,
        rates,
        clocks: state.clocks,
        ...(Object.keys(state.overrides).length && { overrides: state.overrides }),
        merges: state.merges,
        recipes: state.recipes,
        splits: state.splits
    };
}

export function applySaved(saved) {
    state.overrides = saved.overrides || {};
    state.clocks = saved.clocks || {};
    state.merges = saved.merges || {};
    state.recipes = saved.recipes || {};
    state.splits = saved.splits || {};
}

export function savePlan(plan) {
    try {
        localStorage.setItem(PLAN_KEY, JSON.stringify(plan));
    } catch (e) {
        console.warn("Could not save plan", e);
    }
}

export function loadSavedPlan() {
    try {
        return JSON.parse(localStorage.getItem(PLAN_KEY));
    } catch (e) {
        console.warn("Could not read saved plan", e);
        return null;
    }
}

export function downloadPlan(plan) {
    const data = { ...plan, exportedAt: new Date().toISOString() };
    // octet-stream makes the browser treat it as a download
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.setAttribute('download', 'sf_planner_save.json');
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }, 100);
}

export function readPlanFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = e => {
            try {
                resolve(JSON.parse(e.target.result));
            } catch (err) {
                reject(err);
            }
        };
        reader.onerror = () => reject(reader.error);
        reader.readAsText(file);
    });
}

export function loadSavedColors() {
    try {
        return JSON.parse(localStorage.getItem(COLORS_KEY)) || {};
    } catch (e) {
        console.warn("Could not read saved colors", e);
        return {};
    }
}

export function saveColors(colors) {
    localStorage.setItem(COLORS_KEY, JSON.stringify(colors));
    state.colors = colors;
}

// Entries the server could not apply are removed from the plan that was sent; callers save it after
// a successful request. A merge whose target was dropped can name a new target (`replacement`).
export function dropIgnoredEntries(ignored, { merges, overrides, recipes, splits, clocks }) {
    const byKind = { recipe: recipes, merge: merges, override: overrides, split: splits, clock: clocks };
    ignored.forEach(entry => {
        const target = byKind[entry.kind];
        if (!target) return;
        if (entry.replacement) target[entry.node_id] = entry.replacement;
        else delete target[entry.node_id];
    });
}
