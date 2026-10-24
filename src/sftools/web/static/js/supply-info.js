// Supply-driven power plans (ticket 057): when a plan can use its inbound as the limit, what it says as text,
// and what it gives and takes in the Chain tab. No DOM, so it's unit-tested (tests/js/).

const EPSILON = 0.0001;

const mw = value => `${Math.round(value).toLocaleString('en-US')} MW`;

/** Only fuels demanded and some inbound production: the plan can use its inbound as the limit. */
export function canLimit(plan, fuels) {
    const items = plan.items || [];
    return items.length > 0 && items.every(item => fuels.includes(item))
        && (plan.inbound || []).some(row => row.item && row.rate > 0);
}

/** The plan uses its inbound as the limit: the checkbox is on, and the rule still holds. */
export function isLimited(plan, fuels) {
    return Boolean(plan.supplyLimit) && canLimit(plan, fuels);
}

/**
 * What the plan gives and takes in the Chain tab: [{item, rate}] supplies (demand targets, and what's made from
 * by-products as last calculated, ticket 059) and needs (inbound production). A limited plan burns its fuels
 * itself and mines its raw inbound rows, so those aren't there.
 */
export function chainEnds(plan, power) {
    const made = (plan.made || []).map(({ item, rate }) => ({ item, rate }));
    const supplies = (plan.items || []).map((item, i) => ({ item, rate: (plan.rates || [])[i] }));
    const needs = plan.inbound || [];
    if (!isLimited(plan, power.fuels)) return { supplies: [...supplies, ...made], needs };
    return { supplies: made, needs: needs.filter(row => !power.raw.includes(row.item)) };
}

/** The panel's line: "Limited by Crude Oil · 2,500 MW gross / 2,200 net", or why nothing limits the plan. */
export function summaryText(supply) {
    const power = `${mw(supply.power.gross)} gross / ${mw(supply.power.net).replace(' MW', '')} net`;
    return supply.limit ? `Limited by ${supply.limit} · ${power}`
        : `The plan uses none of the inbound, so nothing limits it: it runs at the rates given · ${power}`;
}

/** One line per fuel and inbound row: the fuels as planned, and what the plan uses of each row. */
export function rowLines(supply) {
    const fuels = supply.demands.map(d => `${d.item}: ${d.rate.toFixed(2)}/min burned`);
    const rows = supply.rows.map(row => {
        if (row.unused) return `${row.item}: unused`;
        const over = row.used - row.rate > EPSILON ? ` (${(row.used - row.rate).toFixed(2)} over: whole buildings)` : '';
        return `${row.item}: ${row.used.toFixed(2)} of ${row.rate.toFixed(2)}/min${row.limit ? ', the limit' : ''}${over}`;
    });
    return [...fuels, ...rows];
}
