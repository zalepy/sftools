// The side panel's frame: its tabs, collapsing it, and the legend toggle in the header.
import { $ } from './common.js';

const PANEL_KEY = 'sf_planner_panel_collapsed';
const LEGEND_KEY = 'sf_legend_shown';

/** Shows a tab of the side panel: 'planner', 'node', 'colors' or 'recipes'. */
export function showTab(tabId) {
    document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('active', tab.dataset.tab === tabId));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.toggle('active', content.id === `${tabId}-tab`));
}

/**
 * The legend (ticket 035): shown or hidden with the header button, remembered in the browser.
 * `opened` runs when it opens (the guide closes); returns { hide }.
 */
export function initLegendToggle({ opened = () => {} } = {}) {
    const button = $('legend-toggle');
    const legend = $('legend');

    function setShown(shown) {
        legend.hidden = !shown;
        button.setAttribute('aria-expanded', String(shown));
        button.title = shown ? 'Hide the legend' : 'Show the legend';
        button.classList.toggle('active', shown);
    }

    let shown = false;
    try {
        shown = localStorage.getItem(LEGEND_KEY) === '1';
    } catch (e) {
        // Storage unavailable: start hidden
    }
    setShown(shown);

    function remember() {
        try {
            localStorage.setItem(LEGEND_KEY, shown ? '1' : '0');
        } catch (e) {
            // Not remembered; the legend still toggles
        }
    }

    button.addEventListener('click', () => {
        shown = legend.hidden;
        if (shown) opened();
        setShown(shown);
        remember();
    });
    return {
        hide() {
            if (!shown) return;
            shown = false;
            setShown(false);
            remember();
        }
    };
}

/** Wires the header button; `onResize` runs after the graph area changes width. */
export function initPanelToggle(onResize) {
    const button = $('panel-toggle');
    const container = document.querySelector('.main-container');

    function setCollapsed(collapsed) {
        container.classList.toggle('panel-collapsed', collapsed);
        button.setAttribute('aria-expanded', String(!collapsed));
        button.title = collapsed ? 'Show side panel' : 'Hide side panel';
        button.innerHTML = collapsed ? '&#x276F;' : '&#x276E;';
        onResize();
    }

    let collapsed = false;
    try {
        collapsed = localStorage.getItem(PANEL_KEY) === '1';
    } catch (e) {
        // Storage unavailable: start expanded
    }
    setCollapsed(collapsed);

    button.addEventListener('click', () => {
        collapsed = !container.classList.contains('panel-collapsed');
        setCollapsed(collapsed);
        try {
            localStorage.setItem(PANEL_KEY, collapsed ? '1' : '0');
        } catch (e) {
            // Not remembered; the panel still toggles
        }
    });
}
