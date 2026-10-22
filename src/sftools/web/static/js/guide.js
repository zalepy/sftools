// The user guide panel: USER_GUIDE.md rendered by the server (/guide), in a drawer over the graph.
// The header's Guide button opens and closes it; "?" links (.help-link[data-guide]) open it at a section.

const $ = id => document.getElementById(id);

let loaded = null;     // the request for the guide, made on first open
let onOpen = () => {};

function load() {
    loaded ||= fetch('/guide')
        .then(response => {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.text();
        })
        .then(html => { $('guide-content').innerHTML = html; })
        .catch(e => {
            loaded = null;  // try again next time
            $('guide-content').innerText = `The guide couldn't be loaded (${e.message}).`;
        });
    return loaded;
}

function setShown(shown) {
    $('guide').hidden = !shown;
    const button = $('guide-toggle');
    button.setAttribute('aria-expanded', String(shown));
    button.title = shown ? 'Hide the guide' : 'Show the guide';
    button.classList.toggle('active', shown);
}

export function isOpen() {
    return !$('guide').hidden;
}

export function closeGuide() {
    setShown(false);
}

/** Opens the guide, at a section (its heading's id) if given. */
export async function openGuide(section = null) {
    if (!isOpen()) onOpen();
    setShown(true);
    await load();
    const content = $('guide-content');
    const heading = section && content.querySelector(`[id="${CSS.escape(section)}"]`);
    if (heading) content.scrollTop = heading.offsetTop;  // #guide-content is the offset parent
}

/** `opened`: runs when the guide opens (the legend closes). */
export function initGuide({ opened }) {
    onOpen = opened;
    $('guide-toggle').addEventListener('click', () => isOpen() ? closeGuide() : openGuide());
    $('guide-close').addEventListener('click', closeGuide);
    // Links within the guide (the contents, "see ...") scroll it, rather than the page
    $('guide-content').addEventListener('click', e => {
        const link = e.target.closest('a[href^="#"]');
        if (!link) return;
        e.preventDefault();
        openGuide(decodeURIComponent(link.getAttribute('href').slice(1)));
    });
    document.addEventListener('click', e => {
        const help = e.target.closest('.help-link[data-guide]');
        if (!help) return;
        e.preventDefault();
        e.stopPropagation();
        openGuide(help.dataset.guide);
    });
}
