document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('[data-password-form]');
    if (!form) return;

    form.querySelectorAll('[data-password-toggle]').forEach((button) => {
        const input = button.closest('.password-input-wrap')?.querySelector('.password-input');
        if (!input) return;

        button.addEventListener('click', () => {
            const willShow = input.type === 'password';
            input.type = willShow ? 'text' : 'password';
            button.setAttribute('aria-label', willShow ? 'Ocultar senha' : 'Mostrar senha');
            button.setAttribute('title', willShow ? 'Ocultar senha' : 'Mostrar senha');
            button.querySelector('i')?.classList.toggle('fa-eye', !willShow);
            button.querySelector('i')?.classList.toggle('fa-eye-slash', willShow);
            input.focus();
        });
    });

    const primary = form.querySelector('[data-password-primary]');
    const strength = form.querySelector('[data-password-strength]');
    const strengthLabel = form.querySelector('[data-strength-label]');

    const updateStrength = () => {
        if (!primary || !strength || !strengthLabel) return;
        const value = primary.value;
        let level = 0;

        if (value.length > 0) level = 1;
        if (value.length >= 8) level += 1;
        if (/[a-z]/i.test(value) && /\d/.test(value)) level += 1;
        if (value.length >= 12 && /[^a-z0-9]/i.test(value)) level += 1;
        level = Math.min(level, 4);

        const labels = ['Comece a digitar', 'Muito curta', 'Pode melhorar', 'Boa', 'Forte'];
        strength.dataset.level = String(level);
        strengthLabel.textContent = labels[level];
    };

    primary?.addEventListener('input', updateStrength);
    updateStrength();

    const confirmation = form.querySelector('[data-password-confirm]');
    const confirmationMessage = form.querySelector('[data-confirm-message]');

    const updateConfirmation = () => {
        if (!primary || !confirmation || !confirmationMessage) return;
        const hasValue = confirmation.value.length > 0;
        const matches = hasValue && primary.value === confirmation.value;

        confirmationMessage.classList.toggle('is-match', matches);
        confirmationMessage.classList.toggle('is-mismatch', hasValue && !matches);
        confirmationMessage.textContent = !hasValue
            ? 'Digite novamente para confirmar.'
            : matches
                ? 'As senhas coincidem.'
                : 'As senhas ainda não coincidem.';
    };

    primary?.addEventListener('input', updateConfirmation);
    confirmation?.addEventListener('input', updateConfirmation);
});
