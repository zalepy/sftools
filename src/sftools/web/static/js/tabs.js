// Plan tabs (ticket 039): a book of plans, one shown at a time, and the tab strip above the graph.
// The book is kept in the browser under its own key; the active tab's plan is also kept under the plan's
// key, as before tabs, so older versions of the page still find it.
// The book has a name, and remembers whether it changed since it was last saved or loaded (ticket 060).
import { savePlan, loadSavedPlan } from './state.js';
import { bookTitle } from './book-info.js';

const BOOK_KEY = 'sf_logistics_book';

const $ = id => document.getElementById(id);

let book = null;  // { name, tabs: [{ id, name, plan }], active, chain: { links, positions }, changed }
let chainShown = false;  // the chain tab (ticket 040) is shown instead of the active plan
let handlers = null;  // { onSwitch(id), onClose(id), onAdd(), onDuplicate(), onChain() }

export function newTabId() {
    return 't' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

/** A plan's name for a new tab: "Plan 2", "Plan 3", ... the first number no tab uses. */
function freeName(base = 'Plan') {
    const names = new Set(book.tabs.map(t => t.name));
    let n = 1;
    while (names.has(`${base} ${n}`)) n++;
    return `${base} ${n}`;
}

/** `base` if no tab has that name, else "base 2", "base 3", ... */
export function uniqueName(base) {
    return book.tabs.some(t => t.name === base) ? freeName(base) : base;
}

/** The saved book; a plan saved before tabs becomes the first tab. */
export function loadBook() {
    try {
        const saved = JSON.parse(localStorage.getItem(BOOK_KEY));
        if (saved && Array.isArray(saved.tabs) && saved.tabs.length) book = saved;
    } catch (e) {
        console.warn("Could not read saved tabs", e);
    }
    if (!book) {
        const id = newTabId();
        book = { tabs: [{ id, name: 'Plan 1', plan: loadSavedPlan() }], active: id };
    }
    if (!book.tabs.some(t => t.id === book.active)) book.active = book.tabs[0].id;
    book.chain = cleanChain(book.chain);
    return book;
}

/** The chain tab's links between plans and where their boxes are (ticket 040), checked. */
export function cleanChain(chain) {
    const end = e => e && typeof e.tab === 'string' && typeof e.item === 'string';
    return {
        links: (chain && Array.isArray(chain.links) ? chain.links : []).filter(l => l && end(l.from) && end(l.to)),
        positions: chain && chain.positions && typeof chain.positions === 'object' ? chain.positions : {}
    };
}

/** Keeps the book after a change to it. */
export function saveBook() {
    store();
}

/** Keeps the book in the browser; a change (`changed`) marks it as not saved to a file. */
function store(changed = true) {
    if (changed && !book.changed) {
        book.changed = true;
        render();
    }
    try {
        localStorage.setItem(BOOK_KEY, JSON.stringify(book));
    } catch (e) {
        console.warn("Could not save tabs", e);
    }
}

export function activeTab() {
    return book.tabs.find(t => t.id === book.active);
}

export function getBook() {
    return book;
}

/**
 * Keeps the active tab's plan (after every change). `changed` false: the plan was only shown again (a tab
 * opened, the page loaded), so the book still matches its file.
 */
export function saveActive(plan, changed = true) {
    activeTab().plan = plan;
    savePlan(plan);
    store(changed);
}

export function setActive(id) {
    book.active = id;
    store(false);
    render();
}

/** The book was just saved to a file (Save Book). */
export function markSaved() {
    book.changed = false;
    store(false);
    render();
}

/** Adds a tab after the active one (or at the end) and returns it; it isn't shown until switched to. */
export function addTab(plan, name = freeName()) {
    const tab = { id: newTabId(), name, plan };
    const at = book.tabs.findIndex(t => t.id === book.active);
    book.tabs.splice(at + 1, 0, tab);
    store();
    render();
    return tab;
}

/** Replaces the whole book (a loaded book, or New Book); it matches its file, or has none yet. */
export function replaceBook(tabs, active, chain, name) {
    book = { name, tabs, active: tabs.some(t => t.id === active) ? active : tabs[0].id, chain: cleanChain(chain), changed: false };
    store(false);
    render();
}

/** Removes a tab; returns the tab to show instead, if it was the active one. */
export function removeTab(id) {
    const at = book.tabs.findIndex(t => t.id === id);
    book.tabs.splice(at, 1);
    // Its links go with it
    book.chain.links = book.chain.links.filter(l => l.from.tab !== id && l.to.tab !== id);
    delete book.chain.positions[id];
    if (book.active !== id) {
        store();
        render();
        return null;
    }
    return book.tabs[Math.min(at, book.tabs.length - 1)] || null;
}

/** Moves a tab before (or after) another one (drag and drop in the strip). */
function moveTab(id, targetId, after) {
    if (id === targetId) return;
    const from = book.tabs.findIndex(t => t.id === id);
    if (from < 0 || !book.tabs.some(t => t.id === targetId)) return;
    const [tab] = book.tabs.splice(from, 1);
    const at = book.tabs.findIndex(t => t.id === targetId);
    book.tabs.splice(at + (after ? 1 : 0), 0, tab);
    store();
    render();
}

function rename(id, name) {
    const tab = book.tabs.find(t => t.id === id);
    const trimmed = name.trim();
    if (tab && trimmed && trimmed !== tab.name) {
        tab.name = trimmed;
        store();
    }
    render();
}

function renameBook(name) {
    const trimmed = name.trim();
    if (trimmed && trimmed !== bookTitle(book.name)) {
        book.name = trimmed;
        store();
    }
    render();
}

// --- The tab strip ---

export function initTabs(callbacks) {
    handlers = callbacks;
    const strip = $('plan-tabs');
    strip.addEventListener('click', e => {
        const tab = e.target.closest('.plan-tab');
        if (e.target.closest('.plan-tab-close')) handlers.onClose(tab.dataset.id);
        else if (tab && !e.target.closest('input')) handlers.onSwitch(tab.dataset.id);
    });
    strip.addEventListener('dblclick', e => {
        const name = e.target.closest('.plan-tab-name');
        if (name) startRename(name.closest('.plan-tab').dataset.id);
        else if (e.target.closest('#book-name')) editInPlace($('book-name'), bookTitle(book.name), renameBook);
    });
    initDrag($('plan-tab-list'));
    $('add-tab-btn').addEventListener('click', () => handlers.onAdd());
    $('chain-tab-btn').addEventListener('click', () => handlers.onChain());
    $('duplicate-tab-btn').addEventListener('click', () => handlers.onDuplicate());
    render();
}

// --- Reordering by drag and drop ---

const EDGE = 40;         // px from the strip's ends where a drag scrolls it
const SCROLL_STEP = 12;  // px per dragover event

/** Drag a tab to move it; a bar marks where it lands. Near the ends, the strip scrolls. */
function initDrag(list) {
    let dragged = null;
    let drop = null;  // { id, after }

    const clearMarks = () => list.querySelectorAll('.drop-before, .drop-after, .dragging')
        .forEach(el => el.classList.remove('drop-before', 'drop-after', 'dragging'));

    list.addEventListener('dragstart', e => {
        const tab = e.target.closest && e.target.closest('.plan-tab');
        if (!tab || e.target.closest('input')) return;
        dragged = tab.dataset.id;
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', tab.dataset.id);
        tab.classList.add('dragging');
    });
    list.addEventListener('dragover', e => {
        if (!dragged) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        const box = list.getBoundingClientRect();
        if (e.clientX < box.left + EDGE) list.scrollLeft -= SCROLL_STEP;
        else if (e.clientX > box.right - EDGE) list.scrollLeft += SCROLL_STEP;
        const tab = e.target.closest && e.target.closest('.plan-tab');
        if (!tab) return;
        const rect = tab.getBoundingClientRect();
        const after = e.clientX > rect.left + rect.width / 2;
        drop = { id: tab.dataset.id, after };
        list.querySelectorAll('.drop-before, .drop-after').forEach(el => el.classList.remove('drop-before', 'drop-after'));
        if (tab.dataset.id !== dragged) tab.classList.add(after ? 'drop-after' : 'drop-before');
    });
    list.addEventListener('drop', e => {
        if (!dragged) return;
        e.preventDefault();
        const id = dragged;
        dragged = null;
        clearMarks();
        if (drop) moveTab(id, drop.id, drop.after);
        drop = null;
    });
    list.addEventListener('dragend', () => {
        dragged = null;
        drop = null;
        clearMarks();
    });
}

/** Renames a tab in place. */
export function startRename(id) {
    const tab = book.tabs.find(t => t.id === id);
    const element = document.querySelector(`.plan-tab[data-id="${id}"] .plan-tab-name`);
    if (!tab || !element) return;
    const input = editInPlace(element, tab.name, name => rename(id, name));
    input.closest('.plan-tab').draggable = false;  // the field's text can be selected with the mouse
}

/** Puts a field in place of `element`: Enter or leaving the field keeps the name (`keep`), Esc cancels. */
function editInPlace(element, value, keep) {
    const input = Object.assign(document.createElement('input'), { value, className: 'plan-tab-input' });
    input.size = Math.max(6, value.length);
    let done = false;
    const finish = kept => {
        if (done) return;
        done = true;
        if (kept) keep(input.value); else render();
    };
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter') finish(true);
        else if (e.key === 'Escape') finish(false);
    });
    input.addEventListener('blur', () => finish(true));
    element.replaceWith(input);
    input.focus();
    input.select();
    return input;
}

/** Marks the chain tab as shown (the active plan stays in the side panel, its tab marked as such). */
export function setChainShown(shown) {
    chainShown = shown;
    render();
}

/** The book's name, marked while it has changes not saved to a file. */
function renderBookName() {
    let element = $('book-name');
    if (!element) {  // replaced by its field while renamed
        element = Object.assign(document.createElement('span'), { id: 'book-name', className: 'book-name' });
        const field = $('plan-tabs').querySelector(':scope > .plan-tab-input');
        if (field) field.replaceWith(element); else $('plan-tabs').prepend(element);
    }
    element.textContent = bookTitle(book.name) + (book.changed ? ' •' : '');
    element.classList.toggle('changed', Boolean(book.changed));
    element.title = 'This book: double-click to rename. '
        + (book.changed ? 'It has changes since it was last saved or loaded: Save Book keeps them.' : 'Saved.');
}

function render() {
    const list = $('plan-tab-list');
    if (!list || !book) return;
    renderBookName();
    const chainButton = $('chain-tab-btn');
    chainButton.classList.toggle('active', chainShown);
    chainButton.setAttribute('aria-selected', String(chainShown));
    list.replaceChildren(...book.tabs.map(tab => {
        const active = tab.id === book.active;
        const element = document.createElement('div');
        element.className = 'plan-tab' + (active ? (chainShown ? ' behind' : ' active') : '');
        element.dataset.id = tab.id;
        element.draggable = true;
        element.setAttribute('role', 'tab');
        element.setAttribute('aria-selected', String(active && !chainShown));
        element.title = 'Double-click to rename; drag to move';
        const name = Object.assign(document.createElement('span'), { className: 'plan-tab-name', textContent: tab.name });
        const close = Object.assign(document.createElement('button'), {
            type: 'button', className: 'plan-tab-close', textContent: '✕', title: `Close ${tab.name}`
        });
        close.setAttribute('aria-label', `Close ${tab.name}`);
        element.append(name, close);
        return element;
    }));
    const shown = list.querySelector('.plan-tab.active');
    if (shown) shown.scrollIntoView({ block: 'nearest', inline: 'nearest' });
}
