/* Temas exclusivamente visuais. Não lê nem grava banco, progresso ou AWS.
 * Vincule um livro pelo ID cadastrado em bindings.books; isso evita confundir
 * volumes iguais de coleções diferentes. Exemplo: books: { '42': 'livro3' }.
 * Alternativa: collections: { 'ID_DA_COLECAO': { '3': 'livro3' } }.
 * Os títulos abaixo reconhecem apenas o Livro 3 da referência recebida.
 * Livros sem vínculo mantêm o azul neutro, nunca recebem roxo pelo volume.
 * Cada capítulo pode sobrescrever accent/deep/soft/action/actionHover em chapters.
 * As quatro cores específicas ainda precisam ser confirmadas; não são inferidas.
 */
(() => {
    'use strict';
    const themes = {
        library: { accent: '#176e9e', deep: '#135577', soft: '#eaf5fb', action: '#176e9e', actionHover: '#135577' },
        livro3: {
            accent: '#6c4799', deep: '#54347b', soft: '#f3edf8',
            action: '#187b4b', actionHover: '#14623e',
            // Verde de ação ligeiramente mais escuro para contraste do texto branco.
            chapters: {
                // '1': { accent: '#...', deep: '#...', soft: '#...' },
                // '2': { accent: '#...', deep: '#...', soft: '#...' },
                // '3': { accent: '#...', deep: '#...', soft: '#...' },
                // '4': { accent: '#...', deep: '#...', soft: '#...' }
            }
        }
    };
    const bindings = {
        books: {},
        collections: {},
        titles: {
            'livro 3': 'livro3',
            'livro 3 — educacao infantil / fundamental': 'livro3'
        }
    };
    const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().toLowerCase();
    const tokens = {accent: '--li-accent', deep: '--li-deep', soft: '--li-soft', action: '--li-action', actionHover: '--li-action-hover'};
    document.querySelectorAll('[data-theme]').forEach(element => {
        const { bookId, collectionId, volume, bookTitle, chapter } = element.dataset;
        const key = bindings.books[bookId] || bindings.collections[collectionId]?.[volume] || bindings.titles[normalize(bookTitle)];
        const book = themes[key] || themes.library;
        const palette = { ...themes.library, ...book, ...book.chapters?.[chapter] };
        for (const [token, variable] of Object.entries(tokens)) {
            if (/^#[0-9a-f]{6}$/i.test(palette[token])) element.style.setProperty(variable, palette[token]);
        }
    });
})();
