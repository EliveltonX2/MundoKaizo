/* Navegação simples da biblioteca: grade de livros e conteúdo completo do livro. */
(() => {
    'use strict';
    const panels = new Map([...document.querySelectorAll('[data-panel]')].map(panel => [panel.id, panel]));
    const library = panels.get('biblioteca-livros');
    const search = document.getElementById('librarySearch');
    const count = document.getElementById('libraryCount');
    const breadcrumb = document.getElementById('libraryBreadcrumb');
    const empty = document.getElementById('librarySearchEmpty');
    if (!library) return;
    document.body.classList.add('li-enhanced');

    const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();

    function filterBooks() {
        const books = [...library.querySelectorAll('[data-book-card]')];
        const words = normalize(search?.value).split(/\s+/).filter(Boolean);
        let visible = 0;
        books.forEach(book => {
            const matches = words.every(word => normalize(book.dataset.search).includes(word));
            book.hidden = !matches;
            if (matches) visible += 1;
        });
        if (count) count.textContent = `${visible} ${visible === 1 ? 'livro disponível' : 'livros disponíveis'}`;
        if (empty) empty.hidden = visible > 0 || books.length === 0;
    }

    function panelFromHash() {
        const hash = location.hash.slice(1);
        if (panels.has(hash)) return panels.get(hash);
        if (hash.startsWith('capitulo-')) return document.getElementById(hash)?.closest('[data-panel]') || library;
        return library;
    }

    function buildBreadcrumb(active) {
        if (!breadcrumb) return;
        breadcrumb.replaceChildren();
        if (active === library) { breadcrumb.hidden = true; return; }
        const home = document.createElement('a');
        home.href = '#biblioteca-livros';
        home.innerHTML = '<i class="fa-solid fa-book-open" aria-hidden="true"></i> Exploradores da Computação';
        const divider = document.createElement('span');
        divider.textContent = '›';
        divider.setAttribute('aria-hidden', 'true');
        const current = document.createElement('span');
        current.textContent = active.dataset.label;
        current.setAttribute('aria-current', 'page');
        breadcrumb.append(home, divider, current);
        breadcrumb.hidden = false;
    }

    function openPanel(focus = false) {
        const active = panelFromHash();
        panels.forEach(panel => { panel.hidden = panel !== active; });
        document.getElementById('libraryHero').hidden = active !== library;
        buildBreadcrumb(active);
        document.title = active === library ? 'Exploradores da Computação | Biblioteca MundoKaizo' : `${active.dataset.label} | Biblioteca MundoKaizo`;
        if (focus) {
            active.querySelector('h2')?.focus({ preventScroll: true });
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    }

    document.querySelectorAll('[data-progress-for]').forEach(summary => {
        const lessons = [...(document.getElementById(summary.dataset.progressFor)?.querySelectorAll('[data-lesson]') || [])];
        if (!lessons.length) return;
        const completed = lessons.filter(lesson => lesson.dataset.status === 'completed').length;
        summary.querySelector('span').textContent = `${completed} de ${lessons.length} concluídas`;
        const progress = summary.querySelector('progress');
        progress.max = lessons.length;
        progress.value = completed;
        summary.hidden = false;
    });

    search?.addEventListener('input', filterBooks);
    document.getElementById('clearLibrarySearch')?.addEventListener('click', () => { search.value = ''; filterBooks(); search.focus(); });
    document.querySelector('.li-skip')?.addEventListener('click', event => { event.preventDefault(); panelFromHash().querySelector('h2')?.focus(); });
    window.addEventListener('hashchange', () => openPanel(true));
    window.addEventListener('pageshow', event => { if (event.persisted) window.location.reload(); else openPanel(false); });
    filterBooks();
    openPanel(false);
})();
