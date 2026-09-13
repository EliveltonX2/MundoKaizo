(() => {
    'use strict';

    const form = document.getElementById('cardLinkForm');
    const turma = document.getElementById('id_turma');
    const codigos = document.getElementById('id_codigos');
    const count = document.getElementById('cardCodeCount');
    const submit = document.getElementById('cardLinkSubmit');
    const steps = Array.from(document.querySelectorAll('.card-link-steps li'));

    function getCodes() {
        if (!codigos) return [];
        return codigos.value
            .split(/\r?\n/)
            .map(code => code.trim())
            .filter(Boolean);
    }

    function updateInterface() {
        const codes = getCodes();
        if (count) count.textContent = String(codes.length);

        steps.forEach(step => step.classList.remove('is-active'));
        if (!turma?.value) {
            steps[0]?.classList.add('is-active');
        } else if (!codes.length) {
            steps[1]?.classList.add('is-active');
        } else {
            steps[2]?.classList.add('is-active');
        }
    }

    document.querySelectorAll('[data-dismiss-alert]').forEach(button => {
        button.addEventListener('click', () => {
            const alert = button.closest('.card-link-alert');
            if (!alert) return;
            alert.classList.add('is-closing');
            window.setTimeout(() => alert.remove(), 200);
        });
    });

    turma?.addEventListener('change', updateInterface);
    codigos?.addEventListener('input', updateInterface);
    updateInterface();

    form?.addEventListener('submit', () => {
        if (!form.checkValidity() || !submit) return;
        submit.disabled = true;
        const title = submit.querySelector('strong');
        const description = submit.querySelector('small');
        if (title) title.textContent = 'Salvando vínculos...';
        if (description) description.textContent = 'Aguarde a confirmação';
    });
})();
