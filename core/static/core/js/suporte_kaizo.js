(() => {
    'use strict';

    let activeModal = null;
    let lastFocusedElement = null;

    function getModal(id) {
        return document.getElementById(id);
    }

    function openModal(modal, focusSelector) {
        if (!modal) return;
        lastFocusedElement = document.activeElement;
        modal.hidden = false;
        activeModal = modal;
        document.body.classList.add('support-modal-open');

        window.setTimeout(() => {
            const focusTarget = modal.querySelector(focusSelector || 'button, input, select, textarea');
            focusTarget?.focus();
        }, 30);
    }

    function closeModal(modal, restoreFocus = true) {
        if (!modal) return;
        modal.hidden = true;
        if (activeModal === modal) activeModal = null;
        document.body.classList.remove('support-modal-open');

        if (restoreFocus && lastFocusedElement instanceof HTMLElement) {
            lastFocusedElement.focus();
        }
    }

    function abrirModalNovo() {
        openModal(getModal('modalNovo'), '#supportSubject');
    }

    function fecharModalNovo() {
        closeModal(getModal('modalNovo'));
    }

    function abrirModalChat(url) {
        const iframe = document.getElementById('iframeChat');
        if (!iframe || !url) return;
        iframe.src = url;
        openModal(getModal('modalChat'), '[data-close-chat]');
    }

    function fecharModalChat() {
        const iframe = document.getElementById('iframeChat');
        closeModal(getModal('modalChat'), false);
        if (iframe) iframe.src = '';
        window.location.reload();
    }

    window.abrirModalNovo = abrirModalNovo;
    window.fecharModalNovo = fecharModalNovo;
    window.abrirModalChat = abrirModalChat;
    window.fecharModalChat = fecharModalChat;

    function resizeTextarea(textarea, maxHeight) {
        if (!textarea) return;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, maxHeight) + 'px';
    }

    function initializeListPage() {
        const newTicketModal = getModal('modalNovo');
        const chatModal = getModal('modalChat');
        const message = document.getElementById('supportMessage');
        const counter = document.getElementById('supportCharacterCount');
        const newTicketForm = document.getElementById('newTicketForm');
        const submitTicketButton = document.getElementById('submitTicketButton');

        document.querySelectorAll('[data-open-new-ticket]').forEach(button => {
            button.addEventListener('click', abrirModalNovo);
        });

        document.querySelectorAll('[data-chat-url]').forEach(button => {
            button.addEventListener('click', () => abrirModalChat(button.dataset.chatUrl));
        });

        document.querySelectorAll('[data-close-modal]').forEach(button => {
            button.addEventListener('click', fecharModalNovo);
        });

        document.querySelectorAll('[data-close-chat]').forEach(button => {
            button.addEventListener('click', fecharModalChat);
        });

        newTicketModal?.addEventListener('click', event => {
            if (event.target === newTicketModal) fecharModalNovo();
        });

        chatModal?.addEventListener('click', event => {
            if (event.target === chatModal) fecharModalChat();
        });

        if (message && counter) {
            const updateCount = () => {
                counter.textContent = String(message.value.length);
            };
            message.addEventListener('input', updateCount);
            updateCount();
        }

        newTicketForm?.addEventListener('submit', () => {
            if (!newTicketForm.checkValidity()) return;
            if (submitTicketButton) {
                submitTicketButton.disabled = true;
                submitTicketButton.querySelector('span').textContent = 'Abrindo...';
            }
        });
    }

    function initializeDetailPage() {
        const chatContainer = document.getElementById('chatContainer');
        const textarea = document.getElementById('ticketMessage');
        const form = document.getElementById('supportReplyForm');
        const submitButton = document.getElementById('supportReplyButton');

        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
            window.setTimeout(() => {
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }, 100);
        }

        if (textarea) {
            resizeTextarea(textarea, 110);
            textarea.addEventListener('input', () => resizeTextarea(textarea, 110));
            textarea.addEventListener('keydown', event => {
                if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                    event.preventDefault();
                    form?.requestSubmit();
                }
            });
        }

        form?.addEventListener('submit', () => {
            if (!form.checkValidity()) return;
            if (submitButton) {
                submitButton.disabled = true;
                submitButton.setAttribute('aria-label', 'Enviando mensagem');
            }
        });
    }

    document.addEventListener('keydown', event => {
        if (event.key !== 'Escape' || !activeModal) return;
        if (activeModal.id === 'modalChat') fecharModalChat();
        else fecharModalNovo();
    });

    document.addEventListener('DOMContentLoaded', () => {
        const page = document.body.dataset.supportPage;
        if (page === 'list') initializeListPage();
        if (page === 'detail') initializeDetailPage();
    });
})();
