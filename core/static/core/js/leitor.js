console.log("[KAIZO] Script leitor.js iniciado.");

window.onload = function() {
    console.log("[KAIZO] Evento window.onload disparado.");
    
    // --- LÓGICA DO LOADER GLOBAL ---
    const loader = document.getElementById("globalLoader");
    const imagens = document.querySelectorAll(".pagina-livro");
    
    console.log(`[KAIZO] Elemento loader encontrado?`, !!loader);
    console.log(`[KAIZO] Total de imagens (.pagina-livro) encontradas:`, imagens.length);

    function esconderLoader() {
        console.log("[KAIZO] Função esconderLoader() chamada.");
        if(loader) {
            loader.classList.add("oculto");
            console.log("[KAIZO] Classe 'oculto' adicionada com sucesso.");
        } else {
            console.error("[KAIZO] ERRO: Elemento 'globalLoader' não encontrado no HTML!");
        }
    }

    // Pega apenas as 2 primeiras páginas
    const imagensParaVerificar = Array.from(imagens).slice(0, 2);
    console.log(`[KAIZO] Imagens selecionadas para verificação (Capa/Verso):`, imagensParaVerificar.length);
    
    let imagensPendentes = 0;

    if (imagensParaVerificar.length === 0) {
        console.log("[KAIZO] Nenhuma imagem na página. Escondendo loader.");
        esconderLoader();
    } else {
        imagensParaVerificar.forEach((img, index) => {
            console.log(`[KAIZO] Analisando Imagem ${index + 1}: complete=${img.complete}, src=${img.src}`);
            
            if (!img.complete) {
                imagensPendentes++;
                console.log(`[KAIZO] Imagem ${index + 1} pendente. Total pendentes:`, imagensPendentes);
                
                img.addEventListener("load", () => {
                    imagensPendentes--;
                    console.log(`[KAIZO] Imagem ${index + 1} CARREGOU. Pendentes restando:`, imagensPendentes);
                    if (imagensPendentes === 0) esconderLoader();
                });
                
                img.addEventListener("error", () => {
                    imagensPendentes--;
                    console.error(`[KAIZO] ERRO na Imagem ${index + 1}. Pendentes restando:`, imagensPendentes);
                    if (imagensPendentes === 0) esconderLoader();
                });
            } else {
                console.log(`[KAIZO] Imagem ${index + 1} já estava cacheada/carregada (complete=true).`);
            }
        });
        
        console.log(`[KAIZO] Verificação inicial concluída. Pendentes finais:`, imagensPendentes);
        if (imagensPendentes === 0) {
            console.log("[KAIZO] Nenhuma imagem pendente de carregamento. Escondendo loader imediato.");
            esconderLoader();
        }
    }
    // --------------------------------

    const pageFlipElement = document.getElementById('flipbook');
    const movableLayer = document.getElementById('movable');
    const stage = document.getElementById('stage');
    
    // 1. CONFIGURAÇÃO INICIAL
    const safetyFactor = 0.85; 
    const maxWidth = stage.clientWidth * safetyFactor;
    const maxHeight = stage.clientHeight * safetyFactor;
    const pageRatio = 0.707;
    
    let pageWidth = maxHeight * pageRatio;
    let pageHeight = maxHeight;

    if ((pageWidth * 2) > maxWidth) {
        pageWidth = maxWidth / 2;
        pageHeight = pageWidth / pageRatio;
    }

    // 2. INICIALIZAÇÃO DO PAGEFLIP
    const pageFlip = new St.PageFlip(pageFlipElement, {
        width: Math.floor(pageWidth),
        height: Math.floor(pageHeight),
        size: 'fixed',
        autoSize: true,
        maxShadowOpacity: 0.5,
        showCover: true,
        mobileScrollSupport: false,
        usePortrait: false 
    });

    pageFlipElement.style.display = 'block';
    pageFlip.loadFromHTML(document.querySelectorAll('.page'));

    // 3. CONTROLES DE ZOOM E PAN
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

    document.getElementById('zoomIn').onclick = () => { if(currentScale < 3) { currentScale += 0.2; updateTransform(); updatePanButtonState(); }};
    document.getElementById('zoomOut').onclick = () => { if(currentScale > 0.8) { currentScale -= 0.2; updateTransform(); updatePanButtonState(); }};
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

    stage.addEventListener('mousedown', (e) => { if (isPanMode) { isDragging = true; startX = e.clientX - translateX; startY = e.clientY - translateY; stage.style.cursor = 'grabbing'; }});
    stage.addEventListener('mousemove', (e) => { if (isDragging && isPanMode) { e.preventDefault(); translateX = e.clientX - startX; translateY = e.clientY - startY; updateTransform(); }});
    stage.addEventListener('mouseup', () => { if (isPanMode) { isDragging = false; stage.style.cursor = 'grab'; } });
    stage.addEventListener('mouseleave', () => { isDragging = false; });


    // 4. LÓGICA DO VÍDEO CONTEXTUAL (COM SPREAD/PÁGINA DUPLA)
    const videoBtn = document.getElementById('videoBtn');
    const videoSeparator = document.getElementById('videoSeparator');

    function checkVideoAvailability() {
        if (!videoBtn) return; 

        // Índice base (Página da esquerda)
        const currentIndex = pageFlip.getCurrentPageIndex(); 
        const paginaEsquerda = currentIndex + 1;
        
        const mapa = window.mapaVideos || {};
        
        let urlVideo = mapa[paginaEsquerda];
        let paginaEncontrada = paginaEsquerda;

        // Se não for capa, checa página da direita também
        if (currentIndex > 0) {
            const paginaDireita = currentIndex + 2;
            const videoDireita = mapa[paginaDireita];
            
            if (!urlVideo && videoDireita) {
                urlVideo = videoDireita;
                paginaEncontrada = paginaDireita;
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

    pageFlip.on('flip', checkVideoAvailability);
    setTimeout(checkVideoAvailability, 500);

    // --- 5. NAVEGAÇÃO BÁSICA ---
    document.getElementById('prevBtn').onclick = () => pageFlip.flipPrev();
    document.getElementById('nextBtn').onclick = () => pageFlip.flipNext();
    
    // --- 6. NAVEGAÇÃO PELA NAVBAR ---
    const pageInput = document.getElementById('pageInput');
    const totalPagesSpan = document.getElementById('totalPages');
    const goPageBtn = document.getElementById('goPageBtn');

    setTimeout(() => {
        if(totalPagesSpan) {
            totalPagesSpan.innerText = pageFlip.getPageCount();
        }
    }, 1000);

    function updatePageInput() {
        if (!pageInput) return;
        const currentPage = pageFlip.getCurrentPageIndex() + 1;
        pageInput.value = currentPage;
    }

    pageFlip.on('flip', (e) => {
        checkVideoAvailability(); 
        updatePageInput();        
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

    if (goPageBtn) {
        goPageBtn.onclick = goToTypedPage;
    }

    if (pageInput) {
        pageInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                goToTypedPage();
            }
        });
    }

    // --- ATALHOS DE TECLADO ---
    document.addEventListener('keydown', (e) => {
        if (document.activeElement !== pageInput && !isPanMode) {
            if (e.key === 'ArrowLeft') pageFlip.flipPrev();
            if (e.key === 'ArrowRight') pageFlip.flipNext();
        }
    });

};