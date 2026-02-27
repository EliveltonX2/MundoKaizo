// core/static/core/js/leitor.js
console.log("[KAIZO] Script leitor.js iniciado.");

window.onload = function() {
    
    // --- LÓGICA DO LOADER GLOBAL ---
    const loader = document.getElementById("globalLoader");
    const imagens = document.querySelectorAll(".pagina-livro");
    
    function esconderLoader() {
        if(loader) loader.classList.add("oculto");
    }

    const imagensParaVerificar = Array.from(imagens).slice(0, 2);
    let imagensPendentes = 0;

    if (imagensParaVerificar.length === 0) {
        esconderLoader();
    } else {
        imagensParaVerificar.forEach((img) => {
            if (!img.complete) {
                imagensPendentes++;
                img.addEventListener("load", () => {
                    imagensPendentes--;
                    if (imagensPendentes === 0) esconderLoader();
                });
                img.addEventListener("error", () => {
                    imagensPendentes--;
                    if (imagensPendentes === 0) esconderLoader();
                });
            }
        });
        if (imagensPendentes === 0) esconderLoader();
    }

    // --- CONFIGURAÇÃO DO PAGEFLIP (Cálculo Extremamente Flexível) ---
    const pageFlipElement = document.getElementById('flipbook');
    const movableLayer = document.getElementById('movable');
    const stage = document.getElementById('stage');

    // A MÁGICA DE ENQUADRAMENTO: Reduzimos os tamanhos mínimos para quase zero.
    // Assim, o "autoSize: true" tem liberdade total para encolher o livro e caber 
    // em qualquer tela de celular, sem nunca vazar para os lados.
    const pageFlip = new St.PageFlip(pageFlipElement, {
        width: 420,  
        height: 594, 
        size: 'fixed', 
        autoSize: true, 
        minWidth: 50,    // <--- CÁLCULO LIVRE: Permite encolher infinitamente
        maxWidth: 2000,
        minHeight: 50,   // <--- CÁLCULO LIVRE: Permite encolher infinitamente
        maxHeight: 2500,
        maxShadowOpacity: 0.5,
        showCover: true,
        mobileScrollSupport: false, 
        usePortrait: true 
    });

    pageFlipElement.style.display = 'block';
    pageFlip.loadFromHTML(document.querySelectorAll('.page'));

    // --- SISTEMA DE PRÉ-CARREGAMENTO INTELIGENTE ---
    function preloadPages(currentIndex) {
        const startIndex = Math.max(0, currentIndex - 2);
        const endIndex = Math.min(imagens.length - 1, currentIndex + 3);

        for (let i = startIndex; i <= endIndex; i++) {
            let img = imagens[i];
            if (img && img.hasAttribute('data-src')) {
                img.src = img.getAttribute('data-src'); 
                img.removeAttribute('data-src'); 
            }
        }
    }
    preloadPages(0);

    // MANTÉM A PROTEÇÃO CONTRA O BUG DO PULO: Só mostra o livro após o cálculo.
    pageFlip.on('init', () => {
        setTimeout(() => {
            pageFlipElement.style.opacity = '1';
        }, 50);
    });

    // --- LÓGICA DE ESCONDER/MOSTRAR BARRA ---
    const toggleBtn = document.getElementById('toggleToolbarBtn');
    const controlsWrapper = document.getElementById('controlsWrapper');
    const toggleIcon = document.getElementById('toggleToolbarIcon');
    let toolbarVisible = true;

    toggleBtn.onclick = () => {
        toolbarVisible = !toolbarVisible;
        if(toolbarVisible) {
            controlsWrapper.classList.remove('hidden');
            toggleBtn.classList.remove('btn-hidden-state');
            toggleIcon.classList.remove('fa-eye');
            toggleIcon.classList.add('fa-eye-slash');
        } else {
            controlsWrapper.classList.add('hidden');
            toggleBtn.classList.add('btn-hidden-state');
            toggleIcon.classList.remove('fa-eye-slash');
            toggleIcon.classList.add('fa-eye');
        }
    };

    // --- CONTROLES DE ZOOM E PAN ---
    let currentScale = 1;
    let translateX = 0;
    let translateY = 0;
    let isPanMode = false;
    let isDragging = false;
    let startX, startY;

    const panBtn = document.getElementById('panToggle');

    function updateTransform() {
        movableLayer.style.transform = `translate(${translateX}px, ${translateY}px) scale(${currentScale})`;
    }

    function updatePanButtonState() {
        if (currentScale > 1) {
            panBtn.disabled = false;
        } else {
            panBtn.disabled = true;
            isPanMode = false;
            panBtn.classList.remove('active');
            stage.style.cursor = 'default';
            pageFlipElement.style.pointerEvents = 'auto'; 
            translateX = 0;
            translateY = 0;
            updateTransform();
        }
    }

    document.getElementById('zoomIn').onclick = () => { if(currentScale < 3) { currentScale += 0.3; updateTransform(); updatePanButtonState(); }};
    document.getElementById('zoomOut').onclick = () => { if(currentScale > 1) { currentScale -= 0.3; updateTransform(); updatePanButtonState(); }};
    document.getElementById('zoomReset').onclick = () => { currentScale = 1; updateTransform(); updatePanButtonState(); };

    panBtn.onclick = () => {
        isPanMode = !isPanMode;
        if (isPanMode) {
            panBtn.classList.add('active');
            stage.style.cursor = 'grab';
            pageFlipElement.style.pointerEvents = 'none'; 
        } else {
            panBtn.classList.remove('active');
            stage.style.cursor = 'default';
            pageFlipElement.style.pointerEvents = 'auto';
        }
    };

    const handleDragStart = (e) => {
        if (!isPanMode) return;
        isDragging = true;
        stage.style.cursor = 'grabbing';
        let clientX = e.touches ? e.touches[0].clientX : e.clientX;
        let clientY = e.touches ? e.touches[0].clientY : e.clientY;
        startX = clientX - translateX;
        startY = clientY - translateY;
    };

    const handleDragMove = (e) => {
        if (!isDragging || !isPanMode) return;
        e.preventDefault(); 
        let clientX = e.touches ? e.touches[0].clientX : e.clientX;
        let clientY = e.touches ? e.touches[0].clientY : e.clientY;
        translateX = clientX - startX;
        translateY = clientY - startY;
        updateTransform();
    };

    const handleDragEnd = () => {
        if (!isPanMode) return;
        isDragging = false;
        stage.style.cursor = 'grab';
    };

    stage.addEventListener('mousedown', handleDragStart);
    stage.addEventListener('mousemove', handleDragMove);
    stage.addEventListener('mouseup', handleDragEnd);
    stage.addEventListener('mouseleave', handleDragEnd);
    stage.addEventListener('touchstart', handleDragStart, { passive: false });
    stage.addEventListener('touchmove', handleDragMove, { passive: false });
    stage.addEventListener('touchend', handleDragEnd);

    // --- LÓGICA DO VÍDEO CONTEXTUAL ---
    const videoBtn = document.getElementById('videoBtn');
    const videoSeparator = document.getElementById('videoSeparator');

    function checkVideoAvailability() {
        if (!videoBtn) return; 
        const currentIndex = pageFlip.getCurrentPageIndex(); 
        const paginaEsquerda = currentIndex + 1;
        const mapa = window.mapaVideos || {};
        let urlVideo = mapa[paginaEsquerda];

        if (pageFlip.getOrientation() === 'landscape' && currentIndex > 0) {
            const paginaDireita = currentIndex + 2;
            if (!urlVideo && mapa[paginaDireita]) {
                urlVideo = mapa[paginaDireita];
            }
        }

        if (urlVideo) {
            videoBtn.style.display = 'flex'; 
            videoBtn.href = urlVideo;
            if (videoSeparator) videoSeparator.style.display = 'block';
        } else {
            videoBtn.style.display = 'none';
            if (videoSeparator) videoSeparator.style.display = 'none';
        }
    }

    // --- NAVEGAÇÃO BÁSICA ---
    document.getElementById('prevBtn').onclick = () => pageFlip.flipPrev();
    document.getElementById('nextBtn').onclick = () => pageFlip.flipNext();
    
    const pageInput = document.getElementById('pageInput');
    const totalPagesSpan = document.getElementById('totalPages');
    const goPageBtn = document.getElementById('goPageBtn');

    setTimeout(() => {
        if(totalPagesSpan) totalPagesSpan.innerText = pageFlip.getPageCount();
        checkVideoAvailability();
    }, 1000);

    function updatePageInput() {
        if (!pageInput) return;
        pageInput.value = pageFlip.getCurrentPageIndex() + 1;
    }

    pageFlip.on('flip', (e) => {
        checkVideoAvailability(); 
        updatePageInput();        
        if (e && e.data !== undefined) {
            preloadPages(e.data);
        }
    });

    function goToTypedPage() {
        if (!pageInput) return;
        let pageNum = parseInt(pageInput.value);
        const total = pageFlip.getPageCount();
        if (pageNum < 1) pageNum = 1;
        if (pageNum > total) pageNum = total;
        pageFlip.flip(pageNum - 1);
        pageInput.blur();
    }

    if (goPageBtn) goPageBtn.onclick = goToTypedPage;
    if (pageInput) {
        pageInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') goToTypedPage();
        });
    }

    document.addEventListener('keydown', (e) => {
        if (document.activeElement !== pageInput && !isPanMode) {
            if (e.key === 'ArrowLeft') pageFlip.flipPrev();
            if (e.key === 'ArrowRight') pageFlip.flipNext();
        }
    });
};