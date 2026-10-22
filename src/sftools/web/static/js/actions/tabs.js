// Plan tabs (ticket 039) and the chain tab (ticket 040): switching, adding, closing, and opening files and books.
import { state, isBook, readPlanFile, wrongMode, saveColors, savePreferred } from '../state.js';
import * as notes from '../notes.js';
import * as history from '../history.js';
import * as tabs from '../tabs.js';
import { openChain, refreshChain, closeChain, isChainOpen } from '../chain.js';
import * as logisticsView from '../logistics.js';
import { hidePlanNotice } from '../panel/messages.js';
import { renderRecipeList } from '../panel/recipes.js';
import { renderColorList } from '../panel/colors.js';
import { currentPlan, emptyPlan, showPlan, hideSelection, updateHistoryButtons } from './plan.js';
import { leaveNotes } from './notes.js';

/**
 * Shows another tab, with its own undo history. Logistics settings (what's unlocked) are the game's, so
 * they stay as they are, except for a plan just imported, which brings its own.
 */
export async function switchTab(id, { ownSettings = false, reload = false } = {}) {
    if (id !== tabs.getBook().active && !reload && !leaveNotes()) return;
    if (isChainOpen()) {
        closeChain();
        tabs.setChainShown(false);
    }
    if (id === tabs.getBook().active && !reload) return;
    if (logisticsView.isOpen()) logisticsView.closeView();
    const settings = state.logistics.settings;
    tabs.setActive(id);
    history.useTab(id);
    state.selectedNodeId = null;
    hideSelection();
    hidePlanNotice();
    const plan = tabs.activeTab().plan || emptyPlan();
    await showPlan(ownSettings ? plan : { ...plan, logistics: { ...plan.logistics, settings } }, 'Opening the tab failed');
    updateHistoryButtons();
}

/** Shows the chain tab (ticket 040) over the graph; the side panel keeps the active plan. */
export function showChain() {
    if (isChainOpen()) return;
    if (logisticsView.isOpen()) logisticsView.closeView();
    tabs.setChainShown(true);
    openChain(id => switchTab(id));
}

export function addTab() {
    switchTab(tabs.addTab(emptyPlan()).id);
}

export function duplicateTab() {
    const copy = JSON.parse(JSON.stringify(currentPlan()));
    switchTab(tabs.addTab(copy, `${tabs.activeTab().name} (copy)`).id);
}

export async function closeTab(id) {
    const tab = tabs.getBook().tabs.find(t => t.id === id);
    if (!tab) return;
    const planned = tab.plan && tab.plan.items && tab.plan.items.length;
    const links = tabs.getBook().chain.links.filter(l => l.from.tab === id || l.to.tab === id).length;
    const linked = links ? ` Its ${links} link${links === 1 ? '' : 's'} in the chain tab go too.` : '';
    if ((planned || links) && !confirm(`Close "${tab.name}"? Its plan is removed from this browser; Export Plan or Save Book first to keep it.${linked}`)) return;
    if (tabs.getBook().tabs.length === 1) tabs.addTab(emptyPlan());  // there's always a tab
    const chainShown = isChainOpen();
    const next = tabs.removeTab(id);
    history.forget(id);
    if (next) {
        await switchTab(next.id, { reload: true });
        if (chainShown) showChain();
    }
    refreshChain();
}

/** Replaces all the tabs with a saved book's (Save Book, ticket 039). */
async function openBook(data) {
    const list = data.tabs.filter(tab => tab && typeof tab === 'object').map((tab, i) => ({
        id: typeof tab.id === 'string' && tab.id ? tab.id : tabs.newTabId(),
        name: typeof tab.name === 'string' && tab.name.trim() ? tab.name.trim() : `Plan ${i + 1}`,
        plan: tab.plan || null
    }));
    if (!list.length) {
        alert('This book has no plans.');
        return;
    }
    const here = tabs.getBook().tabs.length;
    if (!confirm(`Load this book? Its ${list.length} tab(s) replace the ${here} here; Save Book first to keep them.`)) return;
    notes.discardNodeNote();
    notes.showPlanNote();
    history.reset();
    // A book brings its preferred recipes and colors (ticket 043), for this browser's tabs
    const isMap = value => Boolean(value) && typeof value === 'object' && !Array.isArray(value);
    if (isMap(data.preferred)) {
        savePreferred(data.preferred);
        renderRecipeList();
    }
    if (isMap(data.colors)) {
        saveColors({ ...state.colors, ...data.colors });
        renderColorList();
    }
    tabs.replaceBook(list, data.active, data.chain);
    await switchTab(tabs.getBook().active, { ownSettings: true, reload: true });
}

/** Opens a plan file in a new tab, or a book file in place of all the tabs. */
export async function importFile(input) {
    const file = input.files[0];
    if (!file) return;
    input.value = ''; // allow importing the same file again
    let data;
    try {
        data = await readPlanFile(file);
    } catch (err) {
        alert("Failed to parse JSON file.");
        console.error(err);
        return;
    }
    const wrong = data && wrongMode(data);
    if (wrong) {
        alert(wrong);
        return;
    }
    if (isBook(data)) {
        await openBook(data);
        return;
    }
    const name = typeof data.name === 'string' && data.name.trim() ? data.name.trim() : file.name.replace(/\.json$/i, '');
    await switchTab(tabs.addTab(data, name).id, { ownSettings: true });
}
