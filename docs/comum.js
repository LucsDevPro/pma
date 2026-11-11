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
  const marcadas = [...b.closest("table").querySelectorAll("input.ck:checked")].map(c => c.closest("tr"))
    .sort((x, y) => x.querySelector("td.s").dataset.o - y.querySelector("td.s").dataset.o);   // semana mais antiga primeiro, mesmo com a tabela ordenada
  const linhas = marcadas.length ? marcadas : [b.closest("tr")];
  copiarTexto(linhas.map(valoresLinha).join("\n"), b, linhas.length > 1 ? `${linhas.length} linhas copiadas!` : "Copiado!");
});

// ===== Ordenação por coluna (A→Z / Z→A, menor→maior / maior→menor) =====
function chaveOrdem(td) {
  if (td.dataset.o !== undefined) return +td.dataset.o;          // chave própria (ex.: id da semana)
  const t = td.textContent.trim(), n = t.replace(/%$/, "").replace(/\./g, "").replace(",", ".");
  return /^-?\d+(\.\d+)?$/.test(n) ? +n : t.toLowerCase();
}

function ordenar(tabela, idx, dir) {   // dir: 1 crescente, -1 decrescente, 0 ordem original
  const tb = tabela.tBodies[0], linhas = [...tb.rows];
  linhas.forEach((r, i) => { if (r.dataset.i === undefined) r.dataset.i = i; });
  linhas.sort((a, b) => {
    if (!dir) return a.dataset.i - b.dataset.i;
    const x = chaveOrdem(a.cells[idx]), y = chaveOrdem(b.cells[idx]);
    return (typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), "pt-BR", {numeric: true})) * dir;
  });
  linhas.forEach(r => tb.appendChild(r));
  [...tabela.querySelectorAll("th")].forEach((th, i) => (th.dataset.dir = dir && i === idx ? (dir > 0 ? "asc" : "desc") : ""));
  const sel = tabela.parentElement.querySelector("select.ord");
  if (sel) sel.value = dir ? `${idx}:${dir}` : "";
}

function montarOrdenacao(tabela) {   // lista "Ordenar por" (funciona também no modo cartões, sem cabeçalho)
  if (!tabela) return;
  const ths = [...tabela.querySelectorAll("th")];
  ths.forEach(th => (th.title = "Clique para ordenar (A→Z, Z→A, padrão)"));
  const opc = ths.map((th, i) => `<option value="${i}:1">${th.textContent} ▲ (A–Z / menor→maior)</option><option value="${i}:-1">${th.textContent} ▼ (Z–A / maior→menor)</option>`).join("");
  const d = document.createElement("div");
  d.className = "ordbar";
  d.innerHTML = `<label>Ordenar por <select class="ord"><option value="">Padrão (mais recente primeiro)</option>${opc}</select></label>`;
  tabela.parentElement.insertBefore(d, tabela);
  d.querySelector("select").onchange = e => { const [i, k] = e.target.value ? e.target.value.split(":").map(Number) : [0, 0]; ordenar(tabela, i, k); };
}

document.addEventListener("click", e => {   // clique no cabeçalho: crescente → decrescente → padrão
  const th = e.target.closest("table.rt th"); if (!th) return;
  ordenar(th.closest("table"), th.cellIndex, th.dataset.dir === "asc" ? -1 : th.dataset.dir === "desc" ? 0 : 1);
});
