document.addEventListener("click", (evento) => {
  const abrir = evento.target.closest("[data-abrir]");
  if (abrir) {
    const modal = document.getElementById(abrir.dataset.abrir);
    if (modal) modal.classList.remove("hidden");
  }
  const cerrar = evento.target.closest("[data-cerrar]");
  if (cerrar) {
    const modal = document.getElementById(cerrar.dataset.cerrar);
    if (modal) modal.classList.add("hidden");
  }
  const tab = evento.target.closest(".tab[data-tab]");
  if (tab && tab.closest(".tabs")) {
    const grupo = tab.parentElement;
    const raiz = grupo.parentElement;
    grupo.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item === tab));
    raiz.querySelectorAll("[data-panel]").forEach((panel) => {
      panel.classList.toggle("hidden", panel.dataset.panel !== tab.dataset.tab);
    });
  }
});
