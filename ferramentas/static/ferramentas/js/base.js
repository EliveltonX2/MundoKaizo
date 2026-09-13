document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('toolSearch');
    const cards = [...document.querySelectorAll('[data-tool-card]')];
    const countLabel = document.getElementById('toolCount');
    const emptyState = document.getElementById('searchEmpty');
    const clearButton = document.getElementById('clearSearch');

    if (!searchInput || !cards.length) return;

    const normalize = (value) => value
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .trim();

    const updateCatalog = () => {
        const query = normalize(searchInput.value);
        let visible = 0;

        cards.forEach((card) => {
            const searchable = normalize(`${card.dataset.toolName} ${card.dataset.toolDescription}`);
            const matches = !query || searchable.includes(query);
            card.hidden = !matches;
            if (matches) visible += 1;
        });

        countLabel.textContent = `${visible} ferramenta${visible === 1 ? '' : 's'}`;
        emptyState.hidden = visible !== 0;
    };

    searchInput.addEventListener('input', updateCatalog);

    clearButton?.addEventListener('click', () => {
        searchInput.value = '';
        updateCatalog();
        searchInput.focus();
    });

    document.addEventListener('keydown', (event) => {
        const isTyping = /input|textarea|select/i.test(document.activeElement?.tagName || '');
        if (event.key === '/' && !isTyping) {
            event.preventDefault();
            searchInput.focus();
        }
    });
});
