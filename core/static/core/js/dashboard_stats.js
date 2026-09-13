(() => {
    const counters = document.querySelectorAll('.dashboard-stats .counter');
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    counters.forEach((counter) => {
        const rawTarget = (counter.dataset.target || '0').replace(',', '.');
        const target = Number.parseFloat(rawTarget);
        if (!Number.isFinite(target)) {
            counter.textContent = rawTarget;
            return;
        }
        if (reduceMotion || target === 0) {
            counter.textContent = Number.isInteger(target) ? String(target) : target.toFixed(1).replace('.', ',');
            return;
        }

        const duration = 650;
        const startedAt = performance.now();
        const decimal = !Number.isInteger(target);
        const update = (now) => {
            const progress = Math.min((now - startedAt) / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            const value = target * eased;
            counter.textContent = decimal ? value.toFixed(1).replace('.', ',') : String(Math.round(value));
            if (progress < 1) requestAnimationFrame(update);
        };
        requestAnimationFrame(update);
    });
})();