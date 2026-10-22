// The Recipes tab (ticket 043): every item made by more than one recipe, with a dropdown of its recipes.
import { getNodeData } from '../graph.js';
import { state } from '../state.js';
import { $ } from './common.js';

let recipeChoices = [];  // from the server: [{item, default, recipes}]
let onRecipeChange = null;  // (item, recipe or null for the default)

/** Nodes of `item` in the plan shown that run a recipe of their own, other than the preferred one. */
export function ownRecipeNodes(item) {
    return Object.entries(state.recipes)
        .filter(([id, recipe]) => getNodeData(id)?.output_item === item && recipe !== state.preferred[item])
        .map(([id]) => id);
}

export function initRecipeList(choices, onChange) {
    recipeChoices = choices;
    onRecipeChange = onChange;
    $('recipe-filter').addEventListener('input', filterRecipeList);
    $('recipe-changed-only').addEventListener('change', filterRecipeList);
    renderRecipeList();
}

/** The recipe an item's nodes run by default, or null when it has no other. */
export function defaultRecipe(item) {
    return recipeChoices.find(choice => choice.item === item)?.default ?? null;
}

/** Redraws the Recipes tab from the preferred recipes. */
export function renderRecipeList() {
    $('recipe-list').replaceChildren(...recipeChoices.map(choice => {
        const preferred = choice.recipes.some(r => r.name === state.preferred[choice.item]) ? state.preferred[choice.item] : choice.default;
        const row = document.createElement('div');
        row.className = `recipe-choice${preferred === choice.default ? '' : ' changed'}`;
        row.dataset.item = choice.item;
        const label = Object.assign(document.createElement('span'), { textContent: choice.item });
        const select = document.createElement('select');
        select.setAttribute('aria-label', `Preferred recipe for ${choice.item}`);
        select.replaceChildren(...choice.recipes.map(r => new Option(
            `${r.name}${r.name === choice.default ? ' (default)' : r.byproduct ? ' (by-product)' : ''}`, r.name, false, r.name === preferred)));
        select.addEventListener('change', () => onRecipeChange(choice.item, select.value === choice.default ? null : select.value));
        row.append(label, select);
        return row;
    }));
    filterRecipeList();
}

function filterRecipeList() {
    const text = $('recipe-filter').value.trim().toLowerCase();
    const changedOnly = $('recipe-changed-only').checked;
    document.querySelectorAll('#recipe-list .recipe-choice').forEach(row => {
        row.hidden = (text && !row.dataset.item.toLowerCase().includes(text)) || (changedOnly && !row.classList.contains('changed'));
    });
}
