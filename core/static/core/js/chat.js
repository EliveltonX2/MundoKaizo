// core/static/core/js/chat.js

function handleEnter(event) {
    if (event.key === "Enter") enviarMensagem();
}

function rolarParaBaixo() {
    const caixa = document.getElementById('caixa-chat');
    if (caixa) {
        caixa.scrollTop = caixa.scrollHeight;
    }
}

async function enviarMensagem() {
    const input = document.getElementById('mensagem-input');
    const caixaChat = document.getElementById('caixa-chat');
    const boasVindas = document.getElementById('msg-boas-vindas');
    const texto = input.value;
    
    if (!texto) return;

    // Remove mensagem de boas-vindas se existir
    if (boasVindas) boasVindas.remove();

    // Adiciona o balão do usuário na tela
    caixaChat.innerHTML += `
        <div class="balao balao-usuario">
            ${texto}
        </div>`;
        
    input.value = ''; 
    rolarParaBaixo(); 

    try {
        // Usa a urlKaiChat e o csrfToken definidos no HTML
        const response = await fetch(urlKaiChat, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ 
                mensagem: texto,
                sessao_id: sessaoAtualId 
            })
        });

        const data = await response.json();

        if (data.status === 'sucesso') {
            // Atualiza o ID da sessão na URL
            if (!sessaoAtualId && data.sessao_id) {
                sessaoAtualId = data.sessao_id;
                window.history.replaceState({}, '', `?sessao=${sessaoAtualId}`);
            }

            caixaChat.innerHTML += `
                <div class="balao balao-ia">
                    <div style="display: flex; align-items: center; margin-bottom: 6px;">
                        <img src="${kaiAvatarUrl}" alt="Kai" style="width: 24px; height: 24px; margin-right: 8px; object-fit: contain;">
                        <b style="color: #2288c4;">Kai:</b>
                    </div>
                    ${data.resposta}
                </div>`;
        } else {
            caixaChat.innerHTML += `<div class="balao balao-ia text-danger"><b>Erro:</b> ${data.mensagem}</div>`;
        }
    } catch (error) {
        console.error('Erro:', error);
        caixaChat.innerHTML += `<div class="balao balao-ia text-danger">Falha ao conectar com o servidor.</div>`;
    }
    
    rolarParaBaixo(); 
}

// Rola para o final da tela quando a página carregar
window.onload = rolarParaBaixo;