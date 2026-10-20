// Notes (ticket 046): one per node and one per plan, kept in the plan (state.notes, state.planNote).
// The text boxes keep what was typed until Save; the note box over the graph shows the note of the node
// the mouse rests on, or else of the selected node.
import { getNodeData, onNodeHover, onBackgroundTap } from './graph.js';
import { state } from './state.js';

const HOVER_MS = 600;
const $ = id => document.getElementById(id);

// What each text box was filled with: it has unsaved edits when its text differs
let nodeNoteId = null;
let nodeNoteBase = '';
let planNoteBase = '';

// --- The node's note (Node tab) ---

/** Fills the node's note box, keeping unsaved edits when it's the node already shown. */
export function showNodeNote(data) {
    const group = $('node-note-group');
    group.style.display = data.sink ? 'none' : '';
    if (data.sink) return;
    if (data.id === nodeNoteId && nodeNoteDirty()) return;
    nodeNoteId = data.id;
    nodeNoteBase = state.notes[data.id] || '';
    $('node-note').value = nodeNoteBase;
}

export function nodeNoteDirty() {
    return nodeNoteId !== null && $('node-note').value !== nodeNoteBase;
}

/** The node's note as typed: [node id, text]. */
export function readNodeNote() {
    return [nodeNoteId, $('node-note').value];
}

/** After a save: what's in the box is the node's note now. */
export function nodeNoteSaved() {
    nodeNoteBase = $('node-note').value;
}

/** A line just added to a node's note (a recipe change): also added to its box, keeping edits there. */
export function nodeNoteAppended(nodeId, line) {
    if (nodeId !== nodeNoteId) return;
    const box = $('node-note');
    box.value = box.value ? `${box.value}\n${line}` : line;
    nodeNoteBase = state.notes[nodeId] || '';
}

/** Drops the unsaved edits of the node's note: the box is filled again when the node is shown. */
export function discardNodeNote() {
    nodeNoteId = null;
}

// --- The plan's note (Planner tab) ---

/** Fills the plan's note box from the plan. */
export function showPlanNote() {
    planNoteBase = state.planNote || '';
    $('plan-note').value = planNoteBase;
}

export function planNoteDirty() {
    return $('plan-note').value !== planNoteBase;
}

export function readPlanNote() {
    return $('plan-note').value;
}

export function planNoteSaved() {
    planNoteBase = $('plan-note').value;
}

// --- The note box over the graph ---

let hovered = null;
let pinned = null;  // the selected node: its note stays shown until it's deselected
let timer = null;

/** Keeps the selected node's note shown (null: none selected). */
export function pinNote(nodeId) {
    pinned = nodeId;
    refreshNoteBox();
}

/** Shows the note of the node the mouse rests on, or else of the selected node; hidden when it has none. */
export function refreshNoteBox() {
    const id = hovered && getNodeData(hovered) ? hovered : pinned;
    const text = id ? state.notes[id] : '';
    const box = $('note-box');
    box.hidden = !text;
    if (!text) return;
    const data = getNodeData(id);
    $('note-box-title').innerText = data ? data.output_item : 'Note';
    $('note-box-text').innerText = text;
}

export function initNoteBox() {
    onNodeHover(id => {
        clearTimeout(timer);
        timer = setTimeout(() => {
            hovered = id;
            refreshNoteBox();
        }, HOVER_MS);
    }, () => {
        clearTimeout(timer);
        hovered = null;
        refreshNoteBox();
    });
    // A click on the empty graph deselects
    onBackgroundTap(() => pinNote(null));
}

/** Today as dd.mm.yy, for lines added to notes. */
export function today() {
    const now = new Date();
    const two = n => String(n).padStart(2, '0');
    return `${two(now.getDate())}.${two(now.getMonth() + 1)}.${two(now.getFullYear() % 100)}`;
}
