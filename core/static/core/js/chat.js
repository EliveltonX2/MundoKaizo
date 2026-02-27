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
    const caixaContent = document.getElementById('mensagens-content'); 
    const boasVindas = document.getElementById('msg-boas-vindas');
    const texto = input.value;
    
    if (!texto) return;

    if (boasVindas) boasVindas.remove();

    // 1. Adiciona o texto do usuário na tela
    caixaContent.innerHTML += `
        <div class="balao balao-usuario">
            ${texto}
        </div>`;
        
    input.value = ''; 
    rolarParaBaixo(); 

    // 2. Adiciona o balão animado da KAI "Pensando..." com um ID único
    const idPensando = `pensando-${Date.now()}`;
    caixaContent.innerHTML += `
        <div id="${idPensando}" class="balao balao-ia typing-indicator">
            <img src="${kaiAvatarUrl}" alt="Kai" style="width: 24px; height: 24px; object-fit: contain; margin-right: 8px;">
            <b style="color: #2288c4; margin-right: 8px;">Kai:</b>
            <span style="font-style: italic; margin-right: 5px;">Pensando</span>
            <div class="dot"></div>
            <div class="dot"></div>
            <div class="dot"></div>
        </div>`;
        
    rolarParaBaixo();

    try {
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

        // 3. Remove a animação de "Pensando" agora que o backend respondeu
        const balaoPensando = document.getElementById(idPensando);
        if (balaoPensando) balaoPensando.remove();

        const data = await response.json();

        if (data.status === 'sucesso') {
            if (!sessaoAtualId && data.sessao_id) {
                sessaoAtualId = data.sessao_id;
                window.history.replaceState({}, '', `?sessao=${sessaoAtualId}`);
            }

            caixaContent.innerHTML += `
                <div class="balao balao-ia">
                    <div style="display: flex; align-items: center; margin-bottom: 6px;">
                        <img src="${kaiAvatarUrl}" alt="Kai" style="width: 24px; height: 24px; margin-right: 8px; object-fit: contain;">
                        <b style="color: #2288c4;">Kai:</b>
                    </div>
                    ${data.resposta}
                </div>`;
        } else {
            caixaContent.innerHTML += `<div class="balao balao-ia text-danger"><b>Erro:</b> ${data.mensagem}</div>`;
        }
    } catch (error) {
        console.error('Erro:', error);
        // Remove a animação de "Pensando" caso dê erro de conexão
        const balaoPensando = document.getElementById(idPensando);
        if (balaoPensando) balaoPensando.remove();
        
        caixaContent.innerHTML += `<div class="balao balao-ia text-danger">Falha ao conectar com o servidor.</div>`;
    }
    
    rolarParaBaixo(); 
}

// ==========================================
// VIGIA DO SCROLL (Mostra o Botão de Descer)
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    const caixaChat = document.getElementById('caixa-chat');
    const btnScroll = document.getElementById('btnScrollBottom');

    if (caixaChat && btnScroll) {
        // Toda vez que a tela rolar...
        caixaChat.addEventListener('scroll', () => {
            // Calcula qual a distância entre onde estamos e o fundo da tela
            const distToBottom = caixaChat.scrollHeight - caixaChat.scrollTop - caixaChat.clientHeight;
            
            // Se o usuário subiu mais de 150 pixels pra cima, mostramos o botão
            if (distToBottom > 150) {
                btnScroll.style.display = 'flex';
            } else {
                btnScroll.style.display = 'none';
            }
        });
    }
});

window.onload = rolarParaBaixo;


// ==========================================
// MÓDULO DE GESTÃO DO HISTÓRICO
// ==========================================

let modalRenomearObj, modalDeletarObj;

document.addEventListener('DOMContentLoaded', () => {
    const elRenomear = document.getElementById('modalRenomear');
    const elDeletar = document.getElementById('modalDeletar');
    
    if (typeof bootstrap !== 'undefined') {
        if (elRenomear) modalRenomearObj = new bootstrap.Modal(elRenomear);
        if (elDeletar) modalDeletarObj = new bootstrap.Modal(elDeletar);
    }
});

function abrirModalRenomear(id, nomeAtual) {
    document.getElementById('inputRenomearId').value = id;
    document.getElementById('inputRenomearNome').value = nomeAtual;
    if (modalRenomearObj) modalRenomearObj.show();
}

function abrirModalDeletar(id) {
    document.getElementById('inputDeletarId').value = id;
    if (modalDeletarObj) modalDeletarObj.show();
}

function salvarNovoNome() {
    const id = document.getElementById('inputRenomearId').value;
    const novoNome = document.getElementById('inputRenomearNome').value;
    if (!novoNome.trim()) return;

    fetch(`/kai/renomear/${id}/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify({ titulo: novoNome })
    })
    .then(res => res.json())
    .then(data => { if (data.status === 'sucesso') location.reload(); });
}

function confirmarDelecao() {
    const id = document.getElementById('inputDeletarId').value;
    fetch(`/kai/deletar/${id}/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken }
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'sucesso') {
            if (id == sessaoAtualId) { window.location.href = window.location.pathname + '?nova=true'; } 
            else { location.reload(); }
        }
    });
}