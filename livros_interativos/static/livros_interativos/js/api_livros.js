// api_livros.js
// Responsável por interceptar mensagens do Iframe (Construct 3 / HTML5) e comunicar com o backend Django

window.addEventListener("message", function(event) {
    // Ignora mensagens que não sejam um objeto JSON válido ou que venham de fontes suspeitas
    if (!event.data || typeof event.data !== 'string') return;
    
    try {
        const msgData = JSON.parse(event.data);
        
        if (msgData.type === 'SAVE_PROGRESS') {
            salvarProgresso(msgData);
        } else if (msgData.type === 'LOAD_PROGRESS') {
            carregarProgresso();
        }
    } catch (e) {
        // Não é um JSON válido, ignorar
    }
});

function salvarProgresso(data) {
    const payload = {
        aula_id: window.KAIZO_AULA_ID,
        pontuacao: data.score || 0,
        time: data.time || 0,
        rubrica: data.rubrica || '',
        habilidades: data.habilidades || []
    };

    fetch('/livros-novo/api/progresso/salvar/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.CSRF_TOKEN
        },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(result => {
        if (result.status === 'sucesso') {
            console.log("Progresso da aula salvo com sucesso.");
        } else {
            console.error("Erro ao salvar progresso:", result.mensagem);
        }
    })
    .catch(error => {
        console.error("Erro na comunicação com a API:", error);
    });
}

function carregarProgresso() {
    fetch(`/livros-novo/api/progresso/carregar/${window.KAIZO_AULA_ID}/`)
    .then(response => response.json())
    .then(result => {
        if (result.status === 'sucesso') {
            // Envia de volta para o Iframe
            const iframe = document.getElementById('aula-iframe');
            if (iframe && iframe.contentWindow) {
                iframe.contentWindow.postMessage(JSON.stringify({
                    type: 'PROGRESS_LOADED',
                    data: result.progress
                }), '*');
            }
        }
    })
    .catch(error => console.error("Erro ao carregar progresso:", error));
}
