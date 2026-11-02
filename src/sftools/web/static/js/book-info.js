// The book's name and the questions asked before it's replaced (ticket 060). Pure: no DOM, so Node tests it.

export const DEFAULT_BOOK_NAME = 'Book';

/** The name shown for a book: books saved before 060 have none. */
export function bookTitle(name) {
    return typeof name === 'string' && name.trim() ? name.trim() : DEFAULT_BOOK_NAME;
}

/** A download's file name from a tab's or a book's name: letters, digits, '-' and '_' kept. */
export function fileName(name) {
    const safe = (name || '').trim().replace(/[^\w-]+/g, '_').replace(/^_+|_+$/g, '');
    return `sf_planner_${safe || 'save'}.json`;
}

/** Save Book's file name: after the book, or `sf_planner_book.json` as before 060. */
export function bookFileName(name) {
    return fileName(typeof name === 'string' && name.trim() ? name : 'book');
}

/** A loaded book's name: the file's `name`, else the file's name without `sf_planner_` and `.json`. */
export function loadedBookName(data, file) {
    if (data && typeof data.name === 'string' && data.name.trim()) return data.name.trim();
    const base = (file || '').replace(/\.json$/i, '').replace(/^sf_planner_/, '').trim();
    return base || DEFAULT_BOOK_NAME;
}

const tabCount = n => `${n} tab${n === 1 ? '' : 's'}`;

/**
 * What to ask before `book` is replaced by `instead` (e.g. `Load "RAD" (4 tabs)`), or null: a book saved
 * since its last change is in its file, so nothing is lost and nothing is asked.
 */
export function replaceQuestion(book, instead) {
    if (!book || !book.changed) return null;
    return `"${bookTitle(book.name)}" has unsaved changes. ${instead} in place of its ${tabCount(book.tabs.length)}?`;
}

/** The load half of the question: `Load "RAD" (4 tabs)`. */
export function loadWhat(name, count) {
    return `Load "${name}" (${tabCount(count)})`;
}
