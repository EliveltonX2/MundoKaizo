(() => {
    const messages = document.querySelectorAll('.turmas-message');

    messages.forEach((message) => {
        const closeButton = message.querySelector('.turmas-message-close');
        if (!closeButton) return;

        closeButton.addEventListener('click', () => {
            message.classList.add('is-leaving');
            window.setTimeout(() => message.remove(), 200);
        });
    });

    const form = document.querySelector('.turmas-form');
    const submitButton = form?.querySelector('.turmas-submit');
    if (!form || !submitButton) return;

    form.addEventListener('submit', () => {
        submitButton.classList.add('is-submitting');
        submitButton.setAttribute('aria-busy', 'true');
        const label = submitButton.querySelector('span');
        if (label) label.textContent = 'Criando turma...';
    });
})();