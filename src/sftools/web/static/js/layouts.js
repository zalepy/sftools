// Reference layouts (ticket 056): fixed builds to copy, in a drawer over the graph like the guide. Each is a
// data file (static/layouts/<id>.json, listed in index.json) drawn by layout-svg.js, with its table and note.
import { layoutSvg } from './layout-svg.js';

const $ = id => document.getElementById(id);

let loaded = null;     // the request for the layouts, made on first open
let onOpen = () => {};

async function fetchJson(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

function amounts(list) {
    return list.map(([item, rate]) => `${rate.toLocaleString('en')} ${item}`).join(', ') || '-';
}

function table(rows) {
    const element = document.createElement('table');
    element.className = 'layout-table';
    const head = element.createTHead().insertRow();
    ['Step', 'Buildings', 'In (/min)', 'Out (/min)'].forEach(text => head.appendChild(Object.assign(document.createElement('th'), { textContent: text })));
    const body = element.createTBody();
    rows.forEach(row => {
        const tr = body.insertRow();
        [row.step, row.buildings, amounts(row.in), amounts(row.out)].forEach(text => { tr.insertCell().textContent = text; });
    });
    return element;
}

function show(layout) {
    const section = document.createElement('section');
    section.className = 'layout';
    section.dataset.id = layout.id;
    const heading = Object.assign(document.createElement('h2'), { textContent: layout.title });
    const summary = Object.assign(document.createElement('p'), { textContent: layout.summary });
    const drawing = document.createElement('div');
    drawing.className = 'layout-drawing';
    drawing.innerHTML = layoutSvg(layout);  // built from our own data file, text escaped
    const note = Object.assign(document.createElement('p'), { className: 'layout-note-text', textContent: layout.note });
    section.append(heading, summary, drawing, table(layout.table || []), note);
    return section;
}

function load() {
    loaded ||= fetchJson('/static/layouts/index.json')
        .then(list => Promise.all(list.map(entry => fetchJson(`/static/layouts/${encodeURIComponent(entry.id)}.json`))))
        .then(layouts => { $('layouts-content').replaceChildren(...layouts.map(show)); })
        .catch(e => {
            loaded = null;  // try again next time
            $('layouts-content').innerText = `The layouts couldn't be loaded (${e.message}).`;
        });
    return loaded;
}

function setShown(shown) {
    $('layouts').hidden = !shown;
    const button = $('layouts-toggle');
    button.setAttribute('aria-expanded', String(shown));
    button.title = shown ? 'Hide the layouts' : 'Show reference layouts';
    button.classList.toggle('active', shown);
}

export function isOpen() {
    return !$('layouts').hidden;
}

export function closeLayouts() {
    setShown(false);
}

export async function openLayouts() {
    if (!isOpen()) onOpen();
    setShown(true);
    await load();
}

/** `opened`: runs when the layouts open (the legend and the guide close). */
export function initLayouts({ opened }) {
    onOpen = opened;
    $('layouts-toggle').addEventListener('click', () => isOpen() ? closeLayouts() : openLayouts());
    $('layouts-close').addEventListener('click', closeLayouts);
}
