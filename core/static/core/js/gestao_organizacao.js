(() => {
    // 1. Gerenciamento de Abas
    const tabButtons = document.querySelectorAll('.go-tab-btn');
    const tabPanes = document.querySelectorAll('.go-tab-pane');

    function setActiveTab(tabId) {
        tabButtons.forEach(btn => {
            const isActive = btn.dataset.tab === tabId;
            btn.classList.toggle('is-active', isActive);
            btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });

        tabPanes.forEach(pane => {
            const isActive = pane.id === `tab-${tabId}`;
            pane.classList.toggle('is-active', isActive);
        });

        // Atualiza a URL sem recarregar a página
        const url = new URL(window.location);
        url.searchParams.set('aba', tabId);
        window.history.replaceState({}, '', url);

        // Atualiza campo de origem nos formulários
        document.querySelectorAll('input[name="aba_origem"]').forEach(input => {
            input.value = tabId;
        });
    }

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            setActiveTab(btn.dataset.tab);
        });
    });

    // Lê a aba inicial da URL ou padrão
    const initialAba = new URLSearchParams(window.location.search).get('aba') || 'turmas';
    if (document.getElementById(`tab-${initialAba}`)) {
        setActiveTab(initialAba);
    }

    // 2. Busca Rápida de Turmas em Tempo Real
    const searchInput = document.getElementById('searchTurmas');
    const turmaCards = document.querySelectorAll('.go-turma-card');

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            turmaCards.forEach(card => {
                const text = card.dataset.searchInfo ? card.dataset.searchInfo.toLowerCase() : card.textContent.toLowerCase();
                const matches = text.includes(query);
                card.style.display = matches ? 'flex' : 'none';
            });
        });
    }

    // 3. Acordeão de Alunos da Turma
    document.querySelectorAll('.go-accordion-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            const list = btn.nextElementSibling;
            if (!list) return;
            const isOpen = list.style.display === 'flex';
            list.style.display = isOpen ? 'none' : 'flex';
            btn.classList.toggle('is-open', !isOpen);
        });
    });

    // 4. Utilitário de Abertura/Fechamento de Modais
    function openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('is-open');
            document.body.style.overflow = 'hidden';
        }
    }

    function closeModal(modal) {
        if (typeof modal === 'string') modal = document.getElementById(modal);
        if (modal) {
            modal.classList.remove('is-open');
            document.body.style.overflow = '';
        }
    }

    document.querySelectorAll('.go-modal-close, [data-close-modal]').forEach(btn => {
        btn.addEventListener('click', () => {
            const modal = btn.closest('.go-modal-backdrop');
            closeModal(modal);
        });
    });

    // Fechar ao clicar fora
    document.querySelectorAll('.go-modal-backdrop').forEach(backdrop => {
        backdrop.addEventListener('click', (e) => {
            if (e.target === backdrop) closeModal(backdrop);
        });
    });

    // 5. Modal: Criar Turma
    const btnOpenCriar = document.getElementById('btnOpenCriarTurma');
    if (btnOpenCriar) {
        btnOpenCriar.addEventListener('click', () => openModal('modalCriarTurma'));
    }

    // 6. Modal: Editar Turma
    document.querySelectorAll('.btn-editar-turma').forEach(btn => {
        btn.addEventListener('click', () => {
            const id = btn.dataset.turmaId;
            const nome = btn.dataset.turmaNome;
            const escolaId = btn.dataset.escolaId;
            const anoId = btn.dataset.anoId;

            const modal = document.getElementById('modalEditarTurma');
            if (!modal) return;

            modal.querySelector('#editTurmaId').value = id;
            modal.querySelector('#editNome').value = nome;
            if (modal.querySelector('#editEscola')) modal.querySelector('#editEscola').value = escolaId || '';
            if (modal.querySelector('#editAno')) modal.querySelector('#editAno').value = anoId || '';

            openModal('modalEditarTurma');
        });
    });

    // 7. Modal: Atribuir Professor
    document.querySelectorAll('.btn-atribuir-prof').forEach(btn => {
        btn.addEventListener('click', () => {
            const id = btn.dataset.turmaId;
            const nome = btn.dataset.turmaNome;

            const modal = document.getElementById('modalAtribuirProf');
            if (!modal) return;

            modal.querySelector('#atribTurmaId').value = id;
            modal.querySelector('#atribTurmaNome').textContent = nome;

            openModal('modalAtribuirProf');
        });
    });

    // 8. Modal: Exclusão Segura com Digitação Obrigatória do Nome da Turma
    const inputConfirmDelete = document.getElementById('inputConfirmarDeleteTurma');
    const btnConfirmDelete = document.getElementById('btnConfirmarDelete');
    let targetDeleteName = '';

    document.querySelectorAll('.btn-excluir-turma').forEach(btn => {
        btn.addEventListener('click', () => {
            const id = btn.dataset.turmaId;
            const nome = btn.dataset.turmaNome;
            targetDeleteName = nome ? nome.trim() : '';

            const modal = document.getElementById('modalExcluirTurma');
            if (!modal) return;

            modal.querySelector('#delTurmaId').value = id;
            modal.querySelector('#delTurmaNome').textContent = nome;
            modal.querySelector('#delTurmaTargetSpan').textContent = nome;

            if (inputConfirmDelete) {
                inputConfirmDelete.value = '';
                inputConfirmDelete.focus();
            }

            if (btnConfirmDelete) {
                btnConfirmDelete.disabled = true;
                btnConfirmDelete.style.opacity = '0.5';
                btnConfirmDelete.style.cursor = 'not-allowed';
            }

            openModal('modalExcluirTurma');
        });
    });

    if (inputConfirmDelete && btnConfirmDelete) {
        inputConfirmDelete.addEventListener('input', () => {
            const typed = inputConfirmDelete.value.trim();
            const matches = typed.toLowerCase() === targetDeleteName.toLowerCase();

            if (matches) {
                btnConfirmDelete.disabled = false;
                btnConfirmDelete.style.opacity = '1';
                btnConfirmDelete.style.cursor = 'pointer';
            } else {
                btnConfirmDelete.disabled = true;
                btnConfirmDelete.style.opacity = '0.5';
                btnConfirmDelete.style.cursor = 'not-allowed';
            }
        });
    }

    // 9. Modal: Reset de Senha do Aluno
    document.querySelectorAll('.btn-reset-aluno').forEach(btn => {
        btn.addEventListener('click', () => {
            const id = btn.dataset.alunoId;
            const nome = btn.dataset.alunoNome;

            const modal = document.getElementById('modalResetarSenha');
            if (!modal) return;

            modal.querySelector('#resetAlunoId').value = id;
            modal.querySelector('#resetAlunoNome').textContent = nome;

            openModal('modalResetarSenha');
        });
    });
})();
