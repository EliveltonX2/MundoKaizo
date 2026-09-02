// livros.js
// Interatividade para o frontend de Livros Interativos

document.addEventListener("DOMContentLoaded", function() {
    console.log("Módulo Livros Interativos (Hierarquia) carregado");
});

function toggleBook(livroId) {
    const content = document.getElementById(`content-book-${livroId}`);
    const icon = document.getElementById(`icon-book-${livroId}`);
    
    if (content.classList.contains('open')) {
        content.classList.remove('open');
        icon.classList.remove('open');
    } else {
        content.classList.add('open');
        icon.classList.add('open');
    }
}
