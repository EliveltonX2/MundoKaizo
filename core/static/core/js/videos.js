document.addEventListener('DOMContentLoaded', () => {
    const covers = document.querySelectorAll('[data-video-cover]');

    covers.forEach((cover) => {
        const hideBrokenCover = () => {
            if (!cover.naturalWidth) cover.hidden = true;
        };

        cover.addEventListener('error', hideBrokenCover, { once: true });
        if (cover.complete) hideBrokenCover();
    });

    const cards = document.querySelectorAll('[data-video-card]');
    if (!('IntersectionObserver' in window)) return;

    cards.forEach((card) => card.classList.add('is-awaiting-reveal'));

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
        });
    }, { threshold: 0.12 });

    cards.forEach((card) => observer.observe(card));
});
