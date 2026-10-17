// Client-side plan state and its persistence (localStorage, JSON export/import).

// Plans and files are marked as logistics mode plans (ticket 033), the only mode since simple mode was
// removed; simple mode plans (also those without a mode) are refused.
export const PLAN_MODE = 'logistics';
const PLAN_KEY = 'sf_logistics_state';
const COLORS_KEY = 'sf_planner_colors';
export const DEFAULT_LOGISTICS_SETTINGS = { belt_tier: 6, pipe_tier: 2, smart: true };

// Mutable shared state; modules read and replace its fields.
export const state = {
    clocks: {},         // node_id -> [{clock}, {count, clock}...]: see clock groups in ticket 023
    merges: {},         // absorbed node_id -> target node_id
    recipes: {},        // node_id -> recipe name
    byproducts: {},     // node_id -> 'use' | 'sink' | 'solve': what its by-products do (tickets 031, 032)
    built: {},          // node_id -> {count, recipe}: buildings already built in the game (ticket 037)
    // Logistics mode: what's unlocked, the logistics nodes the user edited ('<node id>|in' / '|out'),
    // where the nodes inside them are drawn (browser only, ticket 036), and the edges given a number of
    // belts ('<producer>><consumer>|<item>' -> count, ticket 041)
    logistics: { settings: { ...DEFAULT_LOGISTICS_SETTINGS }, layouts: {}, positions: {}, edges: {} },
    colors: {},         // item -> color
    selectedNodeId: null
};

/** Plan in its saved/exported shape; demands and inbound production come from the form. */
export function snapshot({ items, rates, inbound }) {
    return {
        mode: PLAN_MODE,
        items,
        rates,
        inbound,
        clocks: state.clocks,
        merges: state.merges,
        recipes: state.recipes,
        byproducts: state.byproducts,
        built: state.built,
        logistics: state.logistics
    };
}

export function applySaved(saved) {
    state.clocks = saved.clocks || {};
    state.merges = saved.merges || {};
    state.recipes = saved.recipes || {};
    state.byproducts = saved.byproducts || {};
    state.built = saved.built || {};
    const logistics = saved.logistics || {};
    state.logistics = {
        settings: { ...DEFAULT_LOGISTICS_SETTINGS, ...logistics.settings },
        layouts: logistics.layouts || {},
        positions: logistics.positions || {},
        edges: logistics.edges || {}
    };
}

/** Why a plan can't be opened, or null: a simple mode plan (plans without a mode are simple ones). */
export function wrongMode(plan) {
    if (plan.mode === PLAN_MODE) return null;
    return "This is a simple mode plan. Simple mode was removed, and its plans don't convert.";
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

/** A file name from a tab's name: letters, digits, '-' and '_' kept. */
function fileName(name) {
    const safe = (name || '').trim().replace(/[^\w-]+/g, '_').replace(/^_+|_+$/g, '');
    return `sf_planner_${safe || 'save'}.json`;
}

/** Downloads one plan, named after its tab. */
export function downloadPlan(plan, name) {
    download({ ...plan, name }, fileName(name));
}

/** Downloads every tab as one file (Save Book, ticket 039). */
export function downloadBook(book) {
    download({ mode: PLAN_MODE, tabs: book.tabs, active: book.active, chain: book.chain }, fileName('book'));
}

/** Whether a file is a book (all tabs) rather than one plan. */
export function isBook(data) {
    return Boolean(data) && Array.isArray(data.tabs);
}

function download(content, filename) {
    const data = { ...content, exportedAt: new Date().toISOString() };
    // octet-stream makes the browser treat it as a download
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.setAttribute('download', filename);
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
export function dropIgnoredEntries(ignored, { merges, recipes, clocks }) {
    const byKind = { recipe: recipes, merge: merges, clock: clocks };
    ignored.forEach(entry => {
        const target = byKind[entry.kind];
        if (!target) return;
        if (entry.replacement) target[entry.node_id] = entry.replacement;
        else delete target[entry.node_id];
    });
}
