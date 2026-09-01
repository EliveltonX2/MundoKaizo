// Lógica simples para o Dropdown
function toggleDropdown() {
    document.getElementById("userMenu").classList.toggle("show");
}

// Fecha o dropdown se clicar fora dele
window.onclick = function(event) {
    if (!event.target.matches('.user-dropdown-btn') && !event.target.closest('.user-dropdown-btn')) {
        var dropdowns = document.getElementsByClassName("user-dropdown-content");
        for (var i = 0; i < dropdowns.length; i++) {
            var openDropdown = dropdowns[i];
            if (openDropdown.classList.contains('show')) {
                openDropdown.classList.remove('show');
            }
        }
    }
}
