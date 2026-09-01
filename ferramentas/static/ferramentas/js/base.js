document.addEventListener('DOMContentLoaded', () => {
    const dropdownButton = document.querySelector('.user-dropdown-btn');
    const dropdownMenu = document.getElementById('userMenu');

    const closeDropdown = () => {
        if (!dropdownButton || !dropdownMenu) return;
        dropdownButton.setAttribute('aria-expanded', 'false');
        dropdownMenu.classList.remove('show');
    };

    if (dropdownButton && dropdownMenu) {
        dropdownButton.addEventListener('click', (event) => {
            event.stopPropagation();
            const willOpen = dropdownButton.getAttribute('aria-expanded') !== 'true';
            dropdownButton.setAttribute('aria-expanded', String(willOpen));
            dropdownMenu.classList.toggle('show', willOpen);
        });

        document.addEventListener('click', (event) => {
            if (!event.target.closest('.user-dropdown')) closeDropdown();
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                closeDropdown();
                dropdownButton.focus();
            }
        });
    }

    const menuButton = document.querySelector('.nav-menu-btn');
    const sideMenu = document.getElementById('mainMenu');
    const menuBackdrop = document.querySelector('.menu-backdrop');
    const menuCloseButtons = document.querySelectorAll('[data-menu-close]');

    const closeMenu = (restoreFocus = true) => {
        if (!menuButton || !sideMenu || !menuBackdrop) return;
        menuButton.setAttribute('aria-expanded', 'false');
        menuButton.setAttribute('aria-label', 'Abrir menu principal');
        sideMenu.setAttribute('aria-hidden', 'true');
        sideMenu.classList.remove('is-open');
        menuBackdrop.classList.remove('is-open');
        document.body.classList.remove('menu-open');
        if (restoreFocus) menuButton.focus();
    };

    const openMenu = () => {
        if (!menuButton || !sideMenu || !menuBackdrop) return;
        closeDropdown();
        menuButton.setAttribute('aria-expanded', 'true');
        menuButton.setAttribute('aria-label', 'Fechar menu principal');
        sideMenu.setAttribute('aria-hidden', 'false');
        sideMenu.classList.add('is-open');
        menuBackdrop.classList.add('is-open');
        document.body.classList.add('menu-open');
        sideMenu.querySelector('.side-menu-close')?.focus();
    };

    if (menuButton && sideMenu && menuBackdrop) {
        menuButton.addEventListener('click', () => {
            const isOpen = menuButton.getAttribute('aria-expanded') === 'true';
            if (isOpen) closeMenu(); else openMenu();
        });

        menuCloseButtons.forEach((button) => button.addEventListener('click', () => closeMenu()));

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && menuButton.getAttribute('aria-expanded') === 'true') {
                closeMenu();
            }
        });
    }

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
