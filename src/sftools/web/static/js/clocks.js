// Clock math for the Node tab: no DOM, so it's unit-tested (tests/js/).

const EPSILON = 0.0001;
const AVOIDED_COUNTS = [5, 7];  // hard to balance: one fewer building with up to 2 shards is better

/**
 * The clocks that make exactly the demand, with All at 100% and only the last building clocked (ticket 047):
 * {count, clock, groups}, or {why} when there's nothing to fit. One building fewer with the last at up
 * to 150% (1 shard) is preferred, then the buildings needed with the last underclocked; 5 and 7
 * buildings are avoided, by one fewer with the last at up to 200% (2 shards).
 */
export function fitLastClock(data) {
    const need = parseFloat(data.ideal_building_scale);  // buildings at 100%
    if (!(need > 0)) return { why: 'Nothing is demanded from this node.' };
    if (parseFloat(data.building_scale) - need <= EPSILON) return { why: 'No surplus to fit.' };
    const all = Math.ceil(need - 0.00001);
    const lastClock = count => need - (count - 1);
    const fits = (count, max) => count >= 1 && lastClock(count) <= max + 1e-9;
    const avoided = count => AVOIDED_COUNTS.includes(count);
    let count;
    if (!avoided(all - 1) && fits(all - 1, 1.5)) count = all - 1;
    else if (!avoided(all)) count = all;
    else if (fits(all - 1, 2)) count = all - 1;
    else count = all;
    // Under 1% (the lowest clock) the surplus is tiny: one fewer building, just over 100%
    if (lastClock(count) < 0.01) {
        if (!fits(all - 1, 2.5)) return { why: 'The surplus is too small to fit.' };
        count = all - 1;
    }
    // Rounded up to 4 decimals of a percent, so the node is never short
    const clock = Math.ceil(lastClock(count) * 1e6 - 1e-6) / 1e6;
    if (Math.abs(clock - 1) < 1e-9) return { why: 'No surplus to fit.' };
    return { count, clock, groups: [{ clock: 1 }, { count: 1, clock }] };
}

/** Clock groups from the All and Last boxes (percent; NaN when empty), or null for the default (all at 100%). */
export function clockGroups(allPercent, lastPercent) {
    const allClock = isNaN(allPercent) ? 1 : allPercent / 100;
    const groups = [{ clock: allClock }];
    if (!isNaN(lastPercent) && lastPercent / 100 !== allClock) groups.push({ count: 1, clock: lastPercent / 100 });
    return groups.length === 1 && allClock === 1 ? null : groups;
}

/** What the boxes show for a node's clock groups, in percent ('' for the default). */
export function clockBoxes(groups = []) {
    const rest = groups.find(g => g.count === undefined);
    const last = groups.find(g => g.count !== undefined);
    return {
        all: rest && rest.clock !== 1 ? +(rest.clock * 100).toFixed(4) : '',
        last: last ? +(last.clock * 100).toFixed(4) : ''
    };
}
