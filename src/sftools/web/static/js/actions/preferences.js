// Settings for every tab: preferred recipes (ticket 043) and item colors.
import * as api from '../api.js';
import { state, loadSavedColors, saveColors, savePreferred } from '../state.js';
import { getNodeData, hasNodes, refreshNodeColors, reselectNode } from '../graph.js';
import { defaultRecipe, ownRecipeNodes, renderRecipeList } from '../panel/recipes.js';
import { renderColorList, readColorInputs } from '../panel/colors.js';
import { showToast } from '../panel/messages.js';
import { save, render, requestPlan } from './plan.js';
import { notedRecipes, noteRecipeChanges } from './notes.js';

// --- Preferred recipes ---

/** Prefers a recipe for an item (null, or its default: back to the default), in every tab. */
export function setPreferred(item, recipe) {
    const preferred = { ...state.preferred };
    if (recipe && recipe !== defaultRecipe(item)) preferred[item] = recipe; else delete preferred[item];
    return changePreferred(preferred, item, preferred[item]);
}

/** Replaces the preferred recipes; recalculates the plan shown. `item`/`recipe`: the one just preferred. */
export async function changePreferred(preferred, item = null, recipe = null) {
    const previous = state.preferred;
    // A node's own choice of the same recipe goes: it follows the preferred one from now on
    const recipes = Object.fromEntries(Object.entries(state.recipes)
        .filter(([id, name]) => !(recipe && name === recipe && getNodeData(id)?.output_item === item)));
    savePreferred(preferred);
    renderRecipeList();
    if (!hasNodes()) return;
    const before = notedRecipes();
    try {
        render(await requestPlan({ recipes }));
        state.recipes = recipes;
        noteRecipeChanges(before);
        save();
        if (state.selectedNodeId) reselectNode(state.selectedNodeId);
        const own = item ? ownRecipeNodes(item).length : 0;
        if (own) showToast(`${own} ${item} node${own === 1 ? '' : 's'} here keep${own === 1 ? 's' : ''} a recipe of ${own === 1 ? 'its' : 'their'} own.`);
    } catch (e) {
        savePreferred(previous);
        renderRecipeList();
        console.error("Preferred recipe change failed", e);
        alert(`Preferred recipe change failed: ${e.message}`);
    }
}

/** Prefer (or Use Default Recipe) on the Node tab, for the selected node's item. */
export function preferSelected(prefer) {
    const data = getNodeData(state.selectedNodeId);
    if (data) setPreferred(data.output_item, prefer ? data.recipe_name : null);
}

// --- Colors ---

export async function loadColors() {
    let defaults = {};
    try {
        defaults = await api.fetchDefaultColors();
    } catch (e) {
        console.error("Failed to load colors", e);
    }
    state.defaultColors = defaults;
    state.colors = { ...defaults, ...loadSavedColors() };
    renderColorList();
}

export function saveColorChanges() {
    try {
        saveColors(readColorInputs());
        if (hasNodes()) refreshNodeColors();
        alert('Colors saved in this browser.');
    } catch (e) {
        console.error("Failed to save colors", e);
    }
}
