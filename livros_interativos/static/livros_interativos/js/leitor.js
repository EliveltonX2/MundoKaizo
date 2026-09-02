/* Controles apenas da moldura visual; protocolo de progresso em api_livros.js. */
(() => {
    'use strict';
    const button = document.getElementById('readerFullscreen');
    if (!button || !document.fullscreenEnabled) return;
    button.hidden = false;
    button.addEventListener('click', async () => {
        try {
            if (document.fullscreenElement) await document.exitFullscreen();
            else await document.documentElement.requestFullscreen();
        } catch (_) {
            const notice = document.getElementById('readerNotice');
            notice.textContent = 'Não foi possível abrir em tela cheia neste navegador.';
            notice.hidden = false;
        }
    });
    document.addEventListener('fullscreenchange', () => {
        const expanded = Boolean(document.fullscreenElement);
        button.setAttribute('aria-pressed', String(expanded));
        button.querySelector('span').textContent = expanded ? 'Sair da tela cheia' : 'Tela cheia';
        button.querySelector('i').className = expanded ? 'fa-solid fa-compress' : 'fa-solid fa-expand';
    });
})();
