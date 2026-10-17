// Server calls. The server is stateless: every change sends the full plan and gets the whole graph back.

async function errorFrom(response) {
    const err = await response.json().catch(() => ({}));
    const detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
    return new Error(detail || `HTTP ${response.status}`);
}

/** Returns {nodes, ignored, byproducts}; throws with the server's message on an error status. */
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
        logisticsResets: data.logistics_resets || []
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

export async function fetchDefaultColors() {
    const response = await fetch('/api/colors');
    return response.ok ? response.json() : {};
}
