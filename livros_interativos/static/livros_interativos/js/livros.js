/* Navegação de apresentação sobre a hierarquia já renderizada pelo Django.
 * Sem fetch, armazenamento local, cadastros ou alteração de progresso.
 * Sem JS, os painéis continuam legíveis e os links de âncora funcionam.
 */
(() => {
    'use strict';
    const panels = new Map([...document.querySelectorAll('[data-panel]')].map(panel => [panel.id, panel]));
    if (!panels.size) return;
    const search = document.getElementById('librarySearch');
    const count = document.getElementById('libraryCount');
    const breadcrumb = document.getElementById('libraryBreadcrumb');
    const empty = document.getElementById('librarySearchEmpty');
    const names = [['coleção', 'coleções'], ['livro', 'livros'], ['capítulo', 'capítulos'], ['aula', 'aulas']];
    const normalize = value => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
    let active;
    document.body.classList.add('li-enhanced');

    function filter() {
        const items = [...active.querySelectorAll('[data-item]')];
        const words = normalize(search.value).split(/\s+/).filter(Boolean);
        let shown = 0;
        items.forEach(item => {
            const text = normalize(item.dataset.search);
            item.hidden = !words.every(word => text.includes(word));
            if (!item.hidden) shown++;
        });
        const [singular, plural] = names[Number(active.dataset.level)];
        count.textContent = `${shown} ${shown === 1 ? singular : plural}${words.length ? ' nesta busca' : shown === 1 ? ' disponível' : ' disponíveis'}`;
        empty.hidden = !items.length || shown > 0;
        document.getElementById('libraryToolbar').hidden = !items.length;
    }

    function openPanel(focus = false) {
        active = panels.get(location.hash.slice(1)) || panels.get('colecoes');
        panels.forEach(panel => { panel.hidden = panel !== active; });
        document.getElementById('libraryHero').hidden = active.id !== 'colecoes';
        const heading = active.querySelector('.li-compact') || active.querySelector('.li-section-heading');
        heading.append(document.getElementById('libraryToolbar'));
        search.value = '';
        search.placeholder = `Buscar ${names[Number(active.dataset.level)][0]}...`;
        document.querySelectorAll('[data-step]').forEach(step => {
            const current = step.dataset.step === active.dataset.level;
            step.classList.toggle('is-current', current);
            step.classList.toggle('is-past', Number(step.dataset.step) < Number(active.dataset.level));
            if (current) step.setAttribute('aria-current', 'step');
            else step.removeAttribute('aria-current');
        });
        const path = [];
        for (let panel = active; panel; panel = panels.get(panel.dataset.parent)) path.unshift(panel);
        breadcrumb.replaceChildren();
        path.forEach((panel, index) => {
            if (index) {
                const divider = document.createElement('span');
                divider.textContent = '›';
                divider.setAttribute('aria-hidden', 'true');
                breadcrumb.append(divider);
            }
            const node = document.createElement(panel === active ? 'span' : 'a');
            node.textContent = panel.dataset.label;
            if (panel === active) node.setAttribute('aria-current', 'page');
            else node.href = `#${panel.id}`;
            breadcrumb.append(node);
        });
        breadcrumb.hidden = path.length === 1;
        filter();
        document.title = `${active.dataset.label} | Biblioteca MundoKaizo`;
        if (focus) {
            active.querySelector('h2')?.focus({ preventScroll: true });
            window.scrollTo(0, 0);
        }
    }

    // Resumo derivado exclusivamente dos estados que a view já forneceu.
    document.querySelectorAll('[data-progress-for]').forEach(summary => {
        const lessons = [...(panels.get(summary.dataset.progressFor)?.querySelectorAll('[data-status]') || [])];
        if (!lessons.length) return;
        const completed = lessons.filter(lesson => lesson.dataset.status === 'completed').length;
        summary.querySelector('span').textContent = `${completed} de ${lessons.length} aulas concluídas`;
        const progress = summary.querySelector('progress');
        progress.max = lessons.length;
        progress.value = completed;
        progress.setAttribute('aria-valuetext', `${completed} de ${lessons.length} aulas concluídas`);
        summary.hidden = false;
    });
    search.addEventListener('input', filter);
    document.querySelector('.li-skip').addEventListener('click', event => {
        event.preventDefault();
        active.querySelector('h2')?.focus();
    });
    document.getElementById('clearLibrarySearch').addEventListener('click', () => { search.value = ''; filter(); search.focus(); });
    window.addEventListener('hashchange', () => openPanel(true));
    // Ao voltar do leitor pelo navegador, pedir os estados atuais ao Django
    // em vez de reapresentar os cards antigos do cache de navegação.
    window.addEventListener('pageshow', event => {
        if (event.persisted) window.location.reload();
        else openPanel(false);
    });
    openPanel();
})();
