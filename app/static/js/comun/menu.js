document.addEventListener("DOMContentLoaded", () => {
  const menu = document.getElementById("menu-usuario");
  if (!menu) return;
  const boton = menu.querySelector(".avatar-btn");
  const panel = menu.querySelector(".menu-pop");
  boton.addEventListener("click", () => {
    const abierto = boton.getAttribute("aria-expanded") === "true";
    boton.setAttribute("aria-expanded", abierto ? "false" : "true");
    panel.classList.toggle("hidden", abierto);
  });
  document.addEventListener("mousedown", (evento) => {
    if (!menu.contains(evento.target)) {
      boton.setAttribute("aria-expanded", "false");
      panel.classList.add("hidden");
    }
  });
});
