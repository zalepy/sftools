// What the chain tab (ticket 040) says about each end, from the rates. Pure: no DOM, so Node tests it.

const EPSILON = 1e-4;

export const rate = value => `${value.toFixed(2)}/m`;

/**
 * An end's highlight, from what flows through its links (`flow`) over `links` links:
 * short: a supply gives more than it makes, or a need gets less than it needs; surplus: the other way;
 * ok: matches; unlinked: a need no link feeds, so nothing in the book supplies it (ticket 061).
 * A supply without links is a plan's own product: no highlight (null).
 */
export function endStatus(node, flow, links) {
    if (!links) return node.kind === 'need' ? { kind: 'unlinked', text: 'not linked' } : null;
    if (Math.abs(flow - node.rate) <= EPSILON) return { kind: 'ok', text: '' };
    const shortfall = node.kind === 'supply' ? flow > node.rate : flow < node.rate;
    const difference = rate(Math.abs(flow - node.rate));
    if (node.kind === 'supply') return shortfall ? { kind: 'short', text: `${difference} short` } : { kind: 'surplus', text: `${difference} spare` };
    return shortfall ? { kind: 'short', text: `${difference} short` } : { kind: 'surplus', text: `${difference} more` };
}
