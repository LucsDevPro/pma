async function copiarTexto(txt, btn, rotulo) {
  try { await navigator.clipboard.writeText(txt); }
  catch (e) { const t = document.createElement("textarea"); t.value = txt; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); }
  if (btn) { const a = btn.textContent; btn.textContent = rotulo || "Copiado!"; setTimeout(() => (btn.textContent = a), 1400); }
}
const valoresLinha = tr => [...tr.querySelectorAll("td.v")].map(td => td.textContent).join("\t");

function rotular() {   // os botões "Copiar" mostram quantas linhas estão marcadas
  const n = document.querySelectorAll("input.ck:checked").length;
  document.querySelectorAll(".cp").forEach(b => (b.textContent = n ? `Copiar (${n})` : "Copiar"));
}

document.addEventListener("change", e => {
  if (!e.target.matches("input.ck")) return;
  e.target.closest("tr").classList.toggle("marcada", e.target.checked);
  rotular();
});

document.addEventListener("click", e => {
  const m = e.target.closest("[data-marcar]");
  if (m) {   // Marcar todas / Limpar
    const on = m.dataset.marcar === "todas";
    document.querySelectorAll("table.rt input.ck").forEach(c => { c.checked = on; c.closest("tr").classList.toggle("marcada", on); });
    rotular();
    return;
  }
  const b = e.target.closest(".cp"); if (!b) return;
  // com linhas marcadas: copia todas elas (da semana mais antiga para a mais recente); sem marcação: só a linha do botão.
  // Copia apenas os valores, na ordem das colunas, sem o rótulo da semana.
  const marcadas = [...b.closest("table").querySelectorAll("input.ck:checked")].map(c => c.closest("tr")).reverse();
  const linhas = marcadas.length ? marcadas : [b.closest("tr")];
  copiarTexto(linhas.map(valoresLinha).join("\n"), b, linhas.length > 1 ? `${linhas.length} linhas copiadas!` : "Copiado!");
});
