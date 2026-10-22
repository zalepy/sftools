// Move Branch to Inbound (ticket 045), on the Node tab: whether the branch can move, and where to.
import { getNodeData, allNodeData } from '../graph.js';
import { state } from '../state.js';
import { $ } from './common.js';
import { getDemands } from './planner.js';

export const NEW_TAB = 'new';

/** What the node's consumers take: the rate that becomes inbound production. */
export function branchRate(data) {
    return Object.values(data.parent_demands || {}).reduce((sum, rate) => sum + rate, 0);
}

/** Why the node's branch can't be moved, or null: the item must be made by this node alone, and not be a demand target. */
function moveBlocked(data) {
    const item = data.output_item;
    if (getDemands().items.includes(item)) return `${item} is a demand target of this plan.`;
    const makers = allNodeData().filter(n => n.output_item === item && !n.inbound && !n.sink).length;
    if (makers > 1) return `Merge all ${makers} ${item} nodes first.`;
    return null;
}

/** By-products made in the node's branch that the rest of the plan uses as supply. */
function byproductsUsedElsewhere(data) {
    const branch = new Set();
    const stack = [data.id];
    while (stack.length) {
        const id = stack.pop();
        const node = getNodeData(id);
        if (branch.has(id) || !node || node.inbound) continue;
        branch.add(id);
        stack.push(...node.children);
    }
    const items = new Set();
    branch.forEach(id => (getNodeData(id).byproducts || []).forEach(b => {
        if (Object.keys(b.used || {}).some(consumer => !branch.has(consumer))) items.add(b.item);
    }));
    return [...items].sort();
}

/** The Move Branch section for the node; hidden for null (inbound production, the Sink). */
export function renderMoveBranch(data) {
    $('move-branch').style.display = data ? '' : 'none';
    $('move-branch-form').hidden = true;
    if (!data) return;
    const why = moveBlocked(data);
    $('move-branch-btn').disabled = Boolean(why);
    $('move-branch-why').innerText = why || '';
}

/** Opens the destination picker: Undefined, the other tabs, or a new tab. */
export function openMoveBranch(tabs, activeId) {
    const data = getNodeData(state.selectedNodeId);
    if (!data) return;
    const select = $('move-branch-dest');
    select.replaceChildren(
        new Option('Undefined (add the demand target later)', ''),
        ...tabs.filter(t => t.id !== activeId).map(t => new Option(t.name, t.id)),
        new Option('New tab…', NEW_TAB)
    );
    const rate = branchRate(data);
    const used = byproductsUsedElsewhere(data);
    const describe = () => {
        const lines = [`${rate.toFixed(2)}/min ${data.output_item} becomes inbound production here; this node and its inputs go.`];
        if (used.length) lines.push(`By-products of this branch used as supply elsewhere in this plan: ${used.join(', ')}. Those nodes grow.`);
        if (select.value) lines.push(`The destination gets a demand target of ${rate.toFixed(2)}/min, linked on the Chain tab. Undo here doesn't remove it.`);
        $('move-branch-info').innerText = lines.join('\n');
    };
    select.onchange = describe;
    describe();
    $('move-branch-form').hidden = false;
}

export function closeMoveBranch() {
    $('move-branch-form').hidden = true;
}

export function moveBranchDestination() {
    return $('move-branch-dest').value;
}
