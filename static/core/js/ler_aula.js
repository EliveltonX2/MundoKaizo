function ativarTelaCheia() {
    const wrapper = document.getElementById('bookWrapper');
    if (wrapper.requestFullscreen) {
        wrapper.requestFullscreen();
    } else if (wrapper.webkitRequestFullscreen) {
        wrapper.webkitRequestFullscreen();
    } else if (wrapper.msRequestFullscreen) {
        wrapper.msRequestFullscreen();
    }
}

// Listener para a API do livro
window.addEventListener('message', function(event) {
    const data = event.data;
    if (!data) return;

    const configEl = document.getElementById('aula-config');
    if (!configEl) return;
    const config = JSON.parse(configEl.textContent);

    // Tratamento de salvamento de progresso
    if (data.type === 'BOOK_PROGRESS_SAVE') {
        fetch(config.url_salvar, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': config.csrf_token
            },
            body: JSON.stringify({
                aula_id: config.aula_id,
                answers: data.answers || {},
                attempts: data.attempts || {},
                skills: data.skills || [],
                pontuacao: data.pontuacao || data.score || 0,
                rubrica: data.rubrica || '',
                time: data.time || data.play_time || 0
            })
        })
        .then(res => res.json())
        .then(res => console.log('Progresso salvo:', res))
        .catch(err => console.error('Erro ao salvar:', err));
    }

    // Tratamento de carregamento de progresso
    if (data.type === 'BOOK_PROGRESS_REQUEST') {
        fetch(config.url_carregar)
        .then(res => res.json())
        .then(res => {
            if(res.status === 'sucesso') {
                // Devolve para o iframe
                const iframe = document.getElementById('bookIframe');
                iframe.contentWindow.postMessage({
                    type: 'BOOK_PROGRESS_LOADED',
                    progress: res.progress
                }, '*');
            }
        })
        .catch(err => console.error('Erro ao carregar progresso:', err));
    }
});
