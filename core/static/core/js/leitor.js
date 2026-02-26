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

    // --- CONFIGURAÇÃO DO PAGEFLIP (Inteligência Stretch Nativa) ---
    const pageFlipElement = document.getElementById('flipbook');
    const movableLayer = document.getElementById('movable');
    const stage = document.getElementById('stage');

    const pageFlip = new St.PageFlip(pageFlipElement, {
        width: 420,  // Proporção exata de largura
        height: 594, // Proporção exata de altura
        size: 'fixed', // A MÁGICA 1: Mantém a proporção de folha A4 intacta
        autoSize: true, // A MÁGICA 2: Dá um "Zoom" inteligente para caber na tela sem distorcer
        minWidth: 300,
        maxWidth: 1000,
        minHeight: 400,
        maxHeight: 1500,
        maxShadowOpacity: 0.5,
        showCover: true,
        mobileScrollSupport: false, 
        usePortrait: true // Mantém a inteligência de 1 pág no celular e 2 no PC
    });

    pageFlipElement.style.display = 'block';
    pageFlip.loadFromHTML(document.querySelectorAll('.page'));

    // --- SISTEMA DE PRÉ-CARREGAMENTO INTELIGENTE ---
    function preloadPages(currentIndex) {
        // Pega de 2 páginas antes até 3 páginas depois da atual
        const startIndex = Math.max(0, currentIndex - 2);
        const endIndex = Math.min(imagens.length - 1, currentIndex + 3);

        for (let i = startIndex; i <= endIndex; i++) {
            let img = imagens[i];
            // Se a imagem tem o data-src, significa que ainda não foi carregada
            if (img && img.hasAttribute('data-src')) {
                img.src = img.getAttribute('data-src'); // Aciona o download invisível
                img.removeAttribute('data-src'); // Remove para não baixar duas vezes
            }
        }
    }
    
    // Roda uma vez no início para garantir as páginas ao redor da capa
    preloadPages(0);

    // Espera a biblioteca terminar de calcular o "autoSize" antes de mostrar
    pageFlip.on('init', () => {
        setTimeout(() => {
            pageFlipElement.style.opacity = '1';
        }, 50);
    });

    // --- CONTROLES DE ZOOM E PAN (Agora entende Touch do Celular!) ---
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
            // Devolve o controle para virar as páginas com o dedo/mouse
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
            // BLOQUEIA O PAGEFLIP: Evita virar a página sem querer enquanto você passeia pela imagem no Zoom!
            pageFlipElement.style.pointerEvents = 'none'; 
        } else {
            panBtn.classList.remove('active');
            stage.style.cursor = 'default';
            pageFlipElement.style.pointerEvents = 'auto';
        }
    };

    // FUNÇÕES UNIFICADAS PARA MOUSE E TOUCH (DEDO)
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
        e.preventDefault(); // Impede a tela do celular de rolar
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

    // Eventos Mouse
    stage.addEventListener('mousedown', handleDragStart);
    stage.addEventListener('mousemove', handleDragMove);
    stage.addEventListener('mouseup', handleDragEnd);
    stage.addEventListener('mouseleave', handleDragEnd);

    // Eventos Touch (Celular)
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

        // Se o modo retrato está inativo (vendo 2 páginas), checa a da direita tbm
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

    // EVENTO FLIP: Acionado toda vez que uma página é virada
    pageFlip.on('flip', (e) => {
        checkVideoAvailability(); 
        updatePageInput();        
        
        // A MÁGICA DO PRELOAD ACONTECE AQUI AGORA (seguro e com o "e" correto!)
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