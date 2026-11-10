async function copiarTexto(txt, btn) {
  try { await navigator.clipboard.writeText(txt); }
  catch (e) { const t = document.createElement("textarea"); t.value = txt; document.body.appendChild(t); t.select(); document.execCommand("copy"); t.remove(); }
  if (btn) { const a = btn.textContent; btn.textContent = "Copiado!"; setTimeout(() => (btn.textContent = a), 1400); }
}
// botão "Copiar" de uma linha: copia só os valores (sem o rótulo da semana), separados por tab,
// na ordem das colunas — pronto para colar na planilha oficial
document.addEventListener("click", e => {
  const b = e.target.closest(".cp"); if (!b) return;
  copiarTexto([...b.closest("tr").querySelectorAll("td.v")].map(td => td.textContent).join("\t"), b);
});
