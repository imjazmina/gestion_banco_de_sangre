(function () {
  function sid() {
    return sessionStorage.getItem("sid") || "";
  }

  function pintarDocumento(html) {
    var oculto = "<style>html{visibility:hidden}</style>";
    var revelar = "<script>(function(){var nodos=document.querySelectorAll('link[rel=\"stylesheet\"]');var hojas=[];for(var i=0;i<nodos.length;i++){var href=nodos[i].getAttribute('href')||'';if(href.indexOf('fonts.googleapis.com')===-1)hojas.push(nodos[i]);}function ver(){document.documentElement.style.visibility='visible';}if(!hojas.length){ver();return;}var n=hojas.length;function fin(){n-=1;if(n<=0)ver();}for(var j=0;j<hojas.length;j++){var hoja=hojas[j];if(hoja.sheet){fin();continue;}hoja.addEventListener('load',fin);hoja.addEventListener('error',fin);}setTimeout(ver,3000);})();<" + "/script>";
    var cabeza = html.search(/<head[^>]*>/i);
    if (cabeza !== -1) {
      var finCabeza = html.indexOf(">", cabeza) + 1;
      html = html.slice(0, finCabeza) + oculto + html.slice(finCabeza);
    }
    var cuerpo = html.search(/<\/body>/i);
    if (cuerpo !== -1) html = html.slice(0, cuerpo) + revelar + html.slice(cuerpo);
    else html += revelar;
    document.open();
    document.write(html);
    document.close();
  }

  window.pintarDocumento = pintarDocumento;

  document.addEventListener("submit", function (evento) {
    var id = sid();
    if (!id) return;
    var form = evento.target;
    if (!form || form.tagName !== "FORM") return;
    evento.preventDefault();
    var datos = new FormData(form);
    var boton = evento.submitter;
    if (boton && boton.name) {
      datos.set(boton.name, boton.value);
    }
    var metodo = (form.getAttribute("method") || "GET").toUpperCase();
    var accion = form.getAttribute("action") || window.location.href;
    var opciones = {
      method: metodo,
      headers: {
        "X-Sesion": id,
        "X-Sesion-Resuelta": "1",
        "Accept": "text/html"
      },
      credentials: "same-origin",
      redirect: "follow"
    };
    var url = accion;
    if (metodo === "GET") {
      url = accion.split("?")[0] + "?" + new URLSearchParams(datos).toString();
    } else {
      opciones.body = datos;
    }
    fetch(url, opciones).then(function (respuesta) {
      if (respuesta.redirected) {
        window.location.replace(respuesta.url);
        return null;
      }
      return respuesta.text();
    }).then(function (html) {
      if (!html) return;
      pintarDocumento(html);
    });
  }, true);

  window.setInterval(function () {
    var id = sid();
    if (!id) return;
    fetch("/sesion/renovar", {
      method: "POST",
      headers: {"X-Sesion": id, "X-Sesion-Resuelta": "1"},
      credentials: "same-origin"
    });
  }, 10 * 60 * 1000);
})();
