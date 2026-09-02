document.addEventListener('DOMContentLoaded', () => {
    const userButton = document.querySelector('.mk-user-btn');
    const userMenu = document.getElementById('mkUserMenu');
    const menuButton = document.querySelector('.mk-menu-btn');
    const sideMenu = document.getElementById('mkMainMenu');
    const backdrop = document.querySelector('.mk-menu-backdrop');

    const closeUserMenu = () => {
        if (!userButton || !userMenu) return;
        userButton.setAttribute('aria-expanded', 'false');
        userMenu.classList.remove('is-open');
    };

    const closeMainMenu = (restoreFocus = true) => {
        if (!menuButton || !sideMenu || !backdrop) return;
        menuButton.setAttribute('aria-expanded', 'false');
        menuButton.setAttribute('aria-label', 'Abrir menu principal');
        sideMenu.setAttribute('aria-hidden', 'true');
        sideMenu.classList.remove('is-open');
        backdrop.classList.remove('is-open');
        document.body.classList.remove('mk-menu-open');
        if (restoreFocus) menuButton.focus();
    };

    const openMainMenu = () => {
        if (!menuButton || !sideMenu || !backdrop) return;
        closeUserMenu();
        menuButton.setAttribute('aria-expanded', 'true');
        menuButton.setAttribute('aria-label', 'Fechar menu principal');
        sideMenu.setAttribute('aria-hidden', 'false');
        sideMenu.classList.add('is-open');
        backdrop.classList.add('is-open');
        document.body.classList.add('mk-menu-open');
        sideMenu.querySelector('.mk-side-menu-close')?.focus();
    };

    userButton?.addEventListener('click', (event) => {
        event.stopPropagation();
        const shouldOpen = userButton.getAttribute('aria-expanded') !== 'true';
        userButton.setAttribute('aria-expanded', String(shouldOpen));
        userMenu?.classList.toggle('is-open', shouldOpen);
    });

    menuButton?.addEventListener('click', () => {
        if (menuButton.getAttribute('aria-expanded') === 'true') closeMainMenu(); else openMainMenu();
    });

    document.querySelectorAll('[data-mk-menu-close]').forEach((element) => element.addEventListener('click', () => closeMainMenu()));
    document.addEventListener('click', (event) => { if (!event.target.closest('.mk-user-dropdown')) closeUserMenu(); });
    document.addEventListener('keydown', (event) => {
        if (event.key !== 'Escape') return;
        closeUserMenu();
        if (menuButton?.getAttribute('aria-expanded') === 'true') closeMainMenu();
    });

    const kaiPopup = document.getElementById('kai-popup-container');
    if (kaiPopup) window.setTimeout(() => { kaiPopup.hidden = false; }, 1400);
    document.querySelector('[data-kai-close]')?.addEventListener('click', () => { kaiPopup.hidden = true; });
});
