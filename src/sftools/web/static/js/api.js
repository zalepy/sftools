// Server calls. The server is stateless: every change sends the full plan and gets the whole graph back.

async function errorFrom(response) {
    const err = await response.json().catch(() => ({}));
    const detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
    return new Error(detail || `HTTP ${response.status}`);
}

/** Returns {nodes, ignored, byproducts, logisticsResets, supply, made}; throws with the server's message on an error status. */
export async function calculate(plan) {
    const response = await fetch('/api/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(plan)
    });
    if (!response.ok) throw await errorFrom(response);
    const data = await response.json();
    return {
        nodes: data.nodes, ignored: data.ignored || [], byproducts: data.byproducts || {},
        logisticsResets: data.logistics_resets || [], supply: data.supply || null, made: data.made || []
    };
}

export async function fetchRecipes(itemName) {
    const response = await fetch(`/api/available_recipes?item_name=${encodeURIComponent(itemName)}`);
    if (!response.ok) throw await errorFrom(response);
    return response.json();
}

/** Items made by more than one recipe: [{item, default, recipes: [{name, type, byproduct, ...}]}]. */
export async function fetchRecipeChoices() {
    const response = await fetch('/api/recipe_choices');
    if (!response.ok) throw await errorFrom(response);
    return response.json();
}

/** The recipes that take an item, [{name, building, product}]: what can be made from a by-product (ticket 059). */
export async function fetchRecipesUsing(itemName) {
    const response = await fetch(`/api/recipes_using?item_name=${encodeURIComponent(itemName)}`);
    if (!response.ok) throw await errorFrom(response);
    return response.json();
}

/** {fuels, raw}: what a supply-driven plan burns, and the raw items (ticket 057). */
export async function fetchPowerItems() {
    const response = await fetch('/api/power_items');
    if (!response.ok) throw await errorFrom(response);
    return response.json();
}

export async function fetchDefaultColors() {
    const response = await fetch('/api/colors');
    return response.ok ? response.json() : {};
}
