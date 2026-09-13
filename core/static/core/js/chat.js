// Experiência da Kai — somente comportamento de interface.
let envioEmAndamento = false;
let modalAtivo = null;

function rolarChatParaFim(suave = false) {
    const caixa = document.getElementById('caixa-chat');
    if (!caixa) return;
    caixa.scrollTo({ top: caixa.scrollHeight, behavior: suave ? 'smooth' : 'auto' });
}

function rolarParaBaixo() {
    rolarChatParaFim(false);
}

function ajustarAlturaCampo() {
    const input = document.getElementById('mensagem-input');
    if (!input) return;
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 130) + 'px';
}

function criarAvatarKai() {
    const avatar = document.createElement('span');
    avatar.className = 'kai-message-avatar';
    const imagem = document.createElement('img');
    imagem.src = kaiAvatarUrl;
    imagem.alt = 'Kai';
    avatar.appendChild(imagem);
    return avatar;
}

function criarEstruturaMensagem(tipo) {
    const linha = document.createElement('div');
    linha.className = 'kai-message-row ' + (tipo === 'usuario' ? 'is-user' : 'is-assistant');

    if (tipo !== 'usuario') linha.appendChild(criarAvatarKai());

    const mensagem = document.createElement('div');
    mensagem.className = 'kai-message';

    const autor = document.createElement('div');
    autor.className = 'kai-message-author';
    autor.textContent = tipo === 'usuario' ? 'Você' : 'Kai';

    const corpo = document.createElement('div');
    corpo.className = 'kai-message-body';

    mensagem.append(autor, corpo);
    linha.appendChild(mensagem);
    return { linha, corpo };
}

function adicionarMensagemUsuario(texto) {
    const content = document.getElementById('mensagens-content');
    const estrutura = criarEstruturaMensagem('usuario');
    estrutura.corpo.textContent = texto;
    content.appendChild(estrutura.linha);
}

function adicionarIndicadorPensando() {
    const content = document.getElementById('mensagens-content');
    const estrutura = criarEstruturaMensagem('assistente');
    estrutura.linha.classList.add('kai-typing');
    estrutura.corpo.setAttribute('role', 'status');
    estrutura.corpo.setAttribute('aria-label', 'Kai está pensando');

    const label = document.createElement('span');
    label.className = 'kai-thinking-label';
    label.textContent = 'Pensando';

    estrutura.corpo.appendChild(label);
    for (let i = 0; i < 3; i += 1) {
        const ponto = document.createElement('i');
        ponto.className = 'kai-typing-dot';
        ponto.setAttribute('aria-hidden', 'true');
        estrutura.corpo.appendChild(ponto);
    }

    content.appendChild(estrutura.linha);
    return estrutura.linha;
}

function escreverRespostaHTML(elemento, html, velocidade = 9) {
    elemento.innerHTML = html;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        rolarChatParaFim();
        return;
    }

    const walker = document.createTreeWalker(elemento, NodeFilter.SHOW_TEXT);
    const textos = [];
    let node;
    while ((node = walker.nextNode())) {
        if (node.nodeValue.trim()) textos.push({ node, texto: node.nodeValue });
    }

    textos.forEach(item => { item.node.nodeValue = ''; });
    let indiceNo = 0;
    let indiceCaractere = 0;

    function escrever() {
        if (indiceNo >= textos.length) {
            rolarChatParaFim();
            return;
        }

        const item = textos[indiceNo];
        const passo = Math.min(indiceCaractere + 2, item.texto.length);
        item.node.nodeValue = item.texto.slice(0, passo);
        indiceCaractere = passo;

        if (indiceCaractere >= item.texto.length) {
            indiceNo += 1;
            indiceCaractere = 0;
        }

        rolarChatParaFim();
        window.setTimeout(escrever, velocidade);
    }

    escrever();
}

function adicionarRespostaKai(html) {
    const content = document.getElementById('mensagens-content');
    const estrutura = criarEstruturaMensagem('assistente');
    content.appendChild(estrutura.linha);
    escreverRespostaHTML(estrutura.corpo, html || 'Não consegui preparar uma resposta agora.');
}

function adicionarErro(mensagem) {
    const content = document.getElementById('mensagens-content');
    const estrutura = criarEstruturaMensagem('assistente');
    estrutura.corpo.classList.add('kai-error-message');
    estrutura.corpo.textContent = mensagem;
    content.appendChild(estrutura.linha);
}

async function enviarMensagem() {
    const input = document.getElementById('mensagem-input');
    const botao = document.getElementById('kaiSendButton');
    const boasVindas = document.getElementById('msg-boas-vindas');
    const texto = input ? input.value.trim() : '';

    if (!texto || envioEmAndamento) return;

    envioEmAndamento = true;
    botao.disabled = true;
    botao.setAttribute('aria-label', 'Enviando mensagem');

    if (boasVindas) boasVindas.remove();
    adicionarMensagemUsuario(texto);

    input.value = '';
    ajustarAlturaCampo();
    rolarChatParaFim(true);

    const pensando = adicionarIndicadorPensando();
    rolarChatParaFim(true);

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

        const data = await response.json();
        pensando.remove();

        if (!response.ok || data.status !== 'sucesso') {
            adicionarErro(data.mensagem || 'A Kai não conseguiu responder. Tente novamente.');
            return;
        }

        if (!sessaoAtualId && data.sessao_id) {
            sessaoAtualId = data.sessao_id;
            window.history.replaceState({}, '', '?sessao=' + encodeURIComponent(sessaoAtualId));
        }

        adicionarRespostaKai(data.resposta);
    } catch (error) {
        console.error('Erro ao conversar com a Kai:', error);
        pensando.remove();
        adicionarErro('Não foi possível conectar com a Kai agora. Tente novamente em instantes.');
    } finally {
        envioEmAndamento = false;
        botao.disabled = false;
        botao.setAttribute('aria-label', 'Enviar mensagem');
        input.focus();
        rolarChatParaFim(true);
    }
}

function handleEnter(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        enviarMensagem();
    }
}

function abrirSidebar() {
    const sidebar = document.getElementById('menuHistorico');
    const backdrop = document.getElementById('kaiSidebarBackdrop');
    const trigger = document.getElementById('kaiHistoryTrigger');
    if (!sidebar || !backdrop) return;
    sidebar.classList.add('is-open');
    backdrop.hidden = false;
    trigger?.setAttribute('aria-expanded', 'true');
}

function fecharSidebar() {
    const sidebar = document.getElementById('menuHistorico');
    const backdrop = document.getElementById('kaiSidebarBackdrop');
    const trigger = document.getElementById('kaiHistoryTrigger');
    sidebar?.classList.remove('is-open');
    if (backdrop) backdrop.hidden = true;
    trigger?.setAttribute('aria-expanded', 'false');
}

function abrirModal(id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    fecharMenusDeSessao();
    modal.hidden = false;
    modalAtivo = modal;
    document.body.classList.add('kai-modal-open');
    window.setTimeout(() => {
        const foco = modal.querySelector('input:not([type="hidden"]), button');
        foco?.focus();
    }, 20);
}

function fecharModal() {
    if (!modalAtivo) return;
    modalAtivo.hidden = true;
    modalAtivo = null;
    document.body.classList.remove('kai-modal-open');
}

function abrirModalRenomear(id, nomeAtual) {
    document.getElementById('inputRenomearId').value = id;
    document.getElementById('inputRenomearNome').value = nomeAtual;
    abrirModal('modalRenomear');
}

function abrirModalDeletar(id) {
    document.getElementById('inputDeletarId').value = id;
    abrirModal('modalDeletar');
}

async function salvarNovoNome() {
    const id = document.getElementById('inputRenomearId').value;
    const campo = document.getElementById('inputRenomearNome');
    const novoNome = campo.value.trim();
    if (!novoNome) {
        campo.focus();
        return;
    }

    try {
        const response = await fetch('/kai/renomear/' + encodeURIComponent(id) + '/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ titulo: novoNome })
        });
        const data = await response.json();
        if (response.ok && data.status === 'sucesso') window.location.reload();
    } catch (error) {
        console.error('Erro ao renomear conversa:', error);
    }
}

async function confirmarDelecao() {
    const id = document.getElementById('inputDeletarId').value;

    try {
        const response = await fetch('/kai/deletar/' + encodeURIComponent(id) + '/', {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken }
        });
        const data = await response.json();

        if (response.ok && data.status === 'sucesso') {
            if (String(id) === String(sessaoAtualId)) {
                window.location.href = window.location.pathname + '?nova=true';
            } else {
                window.location.reload();
            }
        }
    } catch (error) {
        console.error('Erro ao excluir conversa:', error);
    }
}

function fecharMenusDeSessao(excecao) {
    document.querySelectorAll('.kai-session-options[open]').forEach(menu => {
        if (menu !== excecao) menu.removeAttribute('open');
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const caixaChat = document.getElementById('caixa-chat');
    const btnScroll = document.getElementById('btnScrollBottom');
    const input = document.getElementById('mensagem-input');
    const composer = document.getElementById('kaiComposer');

    rolarChatParaFim();
    window.setTimeout(rolarChatParaFim, 120);

    composer?.addEventListener('submit', event => {
        event.preventDefault();
        enviarMensagem();
    });

    input?.addEventListener('keydown', handleEnter);
    input?.addEventListener('input', ajustarAlturaCampo);
    ajustarAlturaCampo();

    document.querySelectorAll('[data-kai-prompt]').forEach(botao => {
        botao.addEventListener('click', () => {
            input.value = botao.dataset.kaiPrompt || '';
            ajustarAlturaCampo();
            input.focus();
            input.setSelectionRange(input.value.length, input.value.length);
        });
    });

    caixaChat?.addEventListener('scroll', () => {
        const distancia = caixaChat.scrollHeight - caixaChat.scrollTop - caixaChat.clientHeight;
        btnScroll?.classList.toggle('is-visible', distancia > 150);
    });

    btnScroll?.addEventListener('click', () => rolarChatParaFim(true));
    document.getElementById('kaiHistoryTrigger')?.addEventListener('click', abrirSidebar);
    document.getElementById('kaiSidebarClose')?.addEventListener('click', fecharSidebar);
    document.getElementById('kaiSidebarBackdrop')?.addEventListener('click', fecharSidebar);

    document.querySelectorAll('[data-kai-modal-close]').forEach(botao => {
        botao.addEventListener('click', fecharModal);
    });

    document.querySelectorAll('.kai-modal').forEach(modal => {
        modal.addEventListener('click', event => {
            if (event.target === modal) fecharModal();
        });
    });

    document.querySelectorAll('.kai-session-options').forEach(menu => {
        menu.addEventListener('toggle', () => {
            if (menu.open) fecharMenusDeSessao(menu);
        });
    });

    document.addEventListener('click', event => {
        if (!event.target.closest('.kai-session-options')) fecharMenusDeSessao();
    });

    document.getElementById('inputRenomearNome')?.addEventListener('keydown', event => {
        if (event.key === 'Enter') salvarNovoNome();
    });

    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            if (modalAtivo) fecharModal();
            else fecharSidebar();
        }
    });
});
