document.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('home-ready');

    const canAnimate = window.matchMedia('(prefers-reduced-motion: no-preference)').matches;
    if (!canAnimate || !window.matchMedia('(pointer: fine)').matches) return;

    document.querySelectorAll('[data-tilt]').forEach((card) => {
        card.addEventListener('pointermove', (event) => {
            const bounds = card.getBoundingClientRect();
            const x = (event.clientX - bounds.left) / bounds.width - 0.5;
            const y = (event.clientY - bounds.top) / bounds.height - 0.5;
            card.style.transform = `perspective(900px) rotateX(${y * -3}deg) rotateY(${x * 4}deg) translateY(-4px)`;
        });
        card.addEventListener('pointerleave', () => { card.style.transform = ''; });
    });
});
