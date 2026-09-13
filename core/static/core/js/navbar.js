document.addEventListener('DOMContentLoaded', () => {
    const userButton = document.querySelector('.mk-user-btn');
    const userMenu = document.getElementById('mkUserMenu');
    const menuButton = document.querySelector('.mk-menu-btn');
    const sideMenu = document.getElementById('mkMainMenu');
    const backdrop = document.querySelector('.mk-menu-backdrop');
    // MASCOTE SURPRESA: a lista vem do HTML e pode crescer sem mudar esta lógica.
    const mascotHost = document.querySelector('[data-mk-brand-mascot]');
    const mascotImage = mascotHost?.querySelector('.mk-brand-mascot');
    if (mascotHost && mascotImage) {
        const mascotSources = (mascotHost.dataset.mascots || '')
            .split('|')
            .map(source => source.trim())
            .filter(Boolean);

        if (mascotSources.length) {
            let randomValue;
            if (window.crypto?.getRandomValues) {
                const values = new Uint32Array(1);
                window.crypto.getRandomValues(values);
                randomValue = values[0] / 4294967296;
            } else {
                randomValue = Math.random();
            }

            const rareMascots = (mascotHost.dataset.rareMascots || '')
                .split('|')
                .map(name => name.trim())
                .filter(Boolean);
            const weightedMascots = mascotSources.map((source, index) => ({
                index,
                weight: rareMascots.some(name => source.endsWith(name)) ? 1 : 10
            }));
            const totalWeight = weightedMascots.reduce((total, mascot) => total + mascot.weight, 0);
            let draw = randomValue * totalWeight;
            const selectedMascot = weightedMascots.find(mascot => {
                draw -= mascot.weight;
                return draw < 0;
            }) || weightedMascots[weightedMascots.length - 1];
            const mascotIndex = selectedMascot.index;
            const revealMascot = () => mascotHost.classList.add('is-ready');
            mascotImage.addEventListener('load', revealMascot, { once: true });
            mascotImage.src = mascotSources[mascotIndex];
            mascotHost.dataset.mascotIndex = String(mascotIndex + 1);
            if (mascotImage.complete && mascotImage.naturalWidth) revealMascot();
        }
    }

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
