// The book's name (ticket 060). Run: node --test tests/js/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
    bookTitle, fileName, bookFileName, loadedBookName, replaceQuestion, loadWhat
} from '../../src/sftools/web/static/js/book-info.js';

test('a book without a name is shown as Book', () => {
    assert.equal(bookTitle(undefined), 'Book');
    assert.equal(bookTitle('  '), 'Book');
    assert.equal(bookTitle(' RAD '), 'RAD');
});

test('Save Book names the file after the book', () => {
    assert.equal(bookFileName('RAD'), 'sf_planner_RAD.json');
    assert.equal(bookFileName('Main base / v2'), 'sf_planner_Main_base_v2.json');
    assert.equal(bookFileName(undefined), 'sf_planner_book.json');  // as before 060
    assert.equal(fileName('Plan 2'), 'sf_planner_Plan_2.json');
    assert.equal(fileName('***'), 'sf_planner_save.json');
});

test("a loaded book's name: the file's, else from the file name", () => {
    assert.equal(loadedBookName({ name: 'RAD' }, 'whatever.json'), 'RAD');
    assert.equal(loadedBookName({}, 'sf_planner_book.json'), 'book');
    assert.equal(loadedBookName({ name: ' ' }, 'sf_planner_Main_base.JSON'), 'Main_base');
    assert.equal(loadedBookName({}, 'my plans.json'), 'my plans');
    assert.equal(loadedBookName({}, 'sf_planner_.json'), 'Book');
});

test('replacing a book asks only when it has unsaved changes', () => {
    const tabs = Array(17).fill({});
    assert.equal(replaceQuestion({ name: 'Main', tabs, changed: false }, loadWhat('RAD', 4)), null);
    assert.equal(replaceQuestion({ name: 'Main', tabs, changed: true }, loadWhat('RAD', 4)),
        '"Main" has unsaved changes. Load "RAD" (4 tabs) in place of its 17 tabs?');
    assert.equal(replaceQuestion({ tabs: [{}], changed: true }, 'Start "RAD"'),
        '"Book" has unsaved changes. Start "RAD" in place of its 1 tab?');
});
