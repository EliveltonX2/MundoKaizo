document.addEventListener('DOMContentLoaded', () => {
    const iframe = document.querySelector('.tool-iframe');
    const loadingScreen = document.getElementById('loadingScreen');
    if (!iframe || !loadingScreen) return;

    const showTool = () => {
        iframe.classList.add('is-ready');
        loadingScreen.classList.add('is-hidden');
    };

    iframe.addEventListener('load', showTool, { once: true });

    // Evita manter a tela de espera caso uma ferramenta externa demore para responder.
    window.setTimeout(showTool, 12000);
});

