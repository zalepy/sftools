// Messages over the graph: the toast, and the plan notice (saved entries the server ignored).
import { $ } from './common.js';

let toastTimer = null;

/** A short, non-blocking message. */
export function showToast(text, ms = 4000) {
    const toast = $('toast');
    toast.textContent = text;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, ms);
}

let noticeTimer = null;

export function showPlanNotice(ignored) {
    const notice = $('plan-notice');
    const count = ignored.length;
    notice.querySelector('.plan-notice-text').textContent =
        `${count} saved adjustment${count === 1 ? '' : 's'} no longer match${count === 1 ? 'es' : ''} this plan and ${count === 1 ? 'was' : 'were'} removed.`;
    notice.querySelector('ul').replaceChildren(...ignored.map(entry => {
        const li = document.createElement('li');
        li.textContent = `${entry.kind} on ${entry.node_id.split('__').pop()}: ${entry.reason}`;
        li.title = entry.node_id;
        return li;
    }));
    notice.hidden = false;
    clearTimeout(noticeTimer);
    noticeTimer = setTimeout(hidePlanNotice, 15000);
}

export function hidePlanNotice() {
    $('plan-notice').hidden = true;
}

$('plan-notice').querySelector('.close').addEventListener('click', hidePlanNotice);
