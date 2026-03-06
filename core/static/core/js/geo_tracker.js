// core/static/core/js/geo_tracker.js

document.addEventListener('DOMContentLoaded', function() {
    // 1. Verifica se já tentamos capturar o GPS nesta sessão (evita floodar o usuário)
    if (sessionStorage.getItem('gps_verificado') === 'true') {
        return; 
    }

    // 2. Pergunta ao navegador se o dispositivo suporta GPS
    if ("geolocation" in navigator) {
        navigator.geolocation.getCurrentPosition(
            // SUCESSO: O usuário clicou em "Permitir"
            function(position) {
                const lat = position.coords.latitude;
                const lon = position.coords.longitude;

                // Envia as coordenadas para o nosso backend em Python
                fetch('/api/atualizar-gps/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken') // Pega o token de segurança do Django
                    },
                    body: JSON.stringify({ latitude: lat, longitude: lon })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'sucesso') {
                        // Marca na sessão que já resolvemos isso
                        sessionStorage.setItem('gps_verificado', 'true');
                    }
                });
            },
            // ERRO: O usuário clicou em "Bloquear"
            function(error) {
                console.log("GPS bloqueado ou falhou. Mantendo localização via IP.");
                // Marca para não perguntar de novo até ele fechar o navegador
                sessionStorage.setItem('gps_verificado', 'true'); 
            },
            // Opções: Timeout de 10 segundos
            { timeout: 10000 }
        );
    }
});

// Função auxiliar obrigatória do Django para requisições POST via JS
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}