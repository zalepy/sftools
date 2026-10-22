// Notes (ticket 046): saving them, keeping unsaved edits from being lost, and logging recipe changes.
import { state } from '../state.js';
import { getNodeData, markSelected } from '../graph.js';
import * as notes from '../notes.js';
import { showToast } from '../panel/messages.js';
import { save } from './plan.js';

/**
 * Whether unsaved note edits may go: true when there are none, or the user discards them. `plan`: the
 * plan's note counts too (it stays on the Planner tab while another node is selected).
 */
export function leaveNotes({ plan = true } = {}) {
    const dirty = notes.nodeNoteDirty() || (plan && notes.planNoteDirty());
    if (!dirty) return true;
    if (!confirm('Discard unsaved note?')) return false;
    notes.discardNodeNote();
    if (plan) notes.showPlanNote();
    return true;
}

/** Back to the selected node in the graph, after the user kept its unsaved note. */
export function keepSelection() {
    if (state.selectedNodeId) markSelected(state.selectedNodeId);
}

export function saveNodeNote() {
    const [nodeId, text] = notes.readNodeNote();
    if (!nodeId || !getNodeData(nodeId)) return;
    const kept = { ...state.notes };
    if (text.trim()) kept[nodeId] = text; else delete kept[nodeId];
    state.notes = kept;
    notes.nodeNoteSaved();
    save();
    notes.refreshNoteBox();
    showToast('Note saved.');
}

export function savePlanNote() {
    const text = notes.readPlanNote();
    state.planNote = text.trim() ? text : '';
    notes.planNoteSaved();
    save();
    showToast('Plan note saved.');
}

/** The recipes of the nodes with a note, before a change that can switch them. */
export function notedRecipes() {
    return Object.fromEntries(Object.keys(state.notes)
        .map(id => [id, getNodeData(id)?.recipe_name]).filter(([, recipe]) => recipe));
}

/** Adds "dd.mm.yy: recipe changed from X to Y" to the notes of the nodes whose recipe changed since `before`. */
export function noteRecipeChanges(before) {
    Object.entries(before).forEach(([id, recipe]) => {
        const now = getNodeData(id)?.recipe_name;
        if (!now || now === recipe || !state.notes[id]) return;
        const line = `${notes.today()}: recipe changed from ${recipe} to ${now}`;
        state.notes = { ...state.notes, [id]: `${state.notes[id]}\n${line}` };
        notes.nodeNoteAppended(id, line);
    });
}
