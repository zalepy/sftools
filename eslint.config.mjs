// ESLint for bugs, not style (ticket 053), like ruff's F and B rules for Python: no formatting rules.
// CI runs it and reports; nothing is blocked. Locally: npx eslint@10.12.0
// The rules are listed here (not imported from @eslint/js) so it runs with npx alone: no package.json.

const BROWSER = [
    'window', 'document', 'localStorage', 'console', 'setTimeout', 'clearTimeout', 'requestAnimationFrame',
    'alert', 'confirm', 'fetch', 'btoa', 'Option', 'Blob', 'URL', 'FileReader', 'WheelEvent', 'Event',
    'getComputedStyle', 'navigator', 'location', 'CSS',
    'cytoscape', 'cytoscapeDagre',  // CDN scripts in index.html
];

const BUGS = {
    'constructor-super': 'error',
    'for-direction': 'error',
    'getter-return': 'error',
    'no-async-promise-executor': 'error',
    'no-class-assign': 'error',
    'no-compare-neg-zero': 'error',
    'no-cond-assign': 'error',
    'no-const-assign': 'error',
    'no-constant-binary-expression': 'error',
    'no-constant-condition': ['error', { checkLoops: false }],
    'no-dupe-args': 'error',
    'no-dupe-class-members': 'error',
    'no-dupe-else-if': 'error',
    'no-dupe-keys': 'error',
    'no-duplicate-case': 'error',
    'no-empty-pattern': 'error',
    'no-ex-assign': 'error',
    'no-fallthrough': 'error',
    'no-func-assign': 'error',
    'no-import-assign': 'error',
    'no-invalid-regexp': 'error',
    'no-loss-of-precision': 'error',
    'no-new-native-nonconstructor': 'error',
    'no-obj-calls': 'error',
    'no-redeclare': 'error',
    'no-self-assign': 'error',
    'no-self-compare': 'error',
    'no-setter-return': 'error',
    'no-sparse-arrays': 'error',
    'no-this-before-super': 'error',
    'no-undef': 'error',
    'no-unreachable': 'error',
    'no-unsafe-finally': 'error',
    'no-unsafe-negation': 'error',
    'no-unsafe-optional-chaining': 'error',
    'no-unused-vars': ['error', { caughtErrors: 'none', args: 'none' }],
    'no-use-before-define': ['error', { functions: false, classes: false, variables: true }],
    'use-isnan': 'error',
    'valid-typeof': 'error',
};

const globals = names => Object.fromEntries(names.map(name => [name, 'readonly']));

export default [
    { ignores: ['.venv/', '.pytest_cache/'] },
    {
        files: ['src/sftools/web/static/js/**/*.js'],
        languageOptions: { ecmaVersion: 2022, sourceType: 'module', globals: globals(BROWSER) },
        rules: BUGS,
    },
    {
        files: ['tests/js/**/*.mjs'],
        languageOptions: { ecmaVersion: 2022, sourceType: 'module', globals: globals(['console']) },
        rules: BUGS,
    },
];
