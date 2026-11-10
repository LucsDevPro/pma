# -*- coding: utf-8 -*-
"""
Coleta automática (sem janela) para rodar no GitHub Actions.

- Descobre a semana atual pela data (semanas começam no domingo).
- Rotina normal: coleta a semana atual e as 2 anteriores (ex.: ids 332, 331, 330).
- Primeira vez (ainda não existe docs/dados.json) ou com --tudo: coleta da
  semana 35 (id 322) até a atual.
- Guarda somente a linha TOTAL de cada semana, nas duas planilhas, em docs/dados.json
  (que alimenta a página docs/index.html).

Reaproveita toda a lógica de pma_nova_colunas.py (extração, ciclos, fórmulas, colunas).
"""

import os
import sys
import json
import time
import datetime as dt

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import pma_nova_colunas as base

# ================= CONFIG =================
# Âncora do calendário: a semana de id 332 (semana 45) começou no domingo 08/11/2026.
ANCORA_ID = 332
ANCORA_DATA = dt.date(2026, 11, 8)

PRIMEIRA_ID = 322            # semana 35: início do histórico
ULTIMAS_N = 3                # semana atual + 2 anteriores
FUSO = dt.timezone(dt.timedelta(hours=-4))   # Mato Grosso do Sul (UTC-4)

ARQ_DADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "dados.json")

ULTIMA_ID_DEFINIDA = max(
    w for tabela in (base.CICLOS_URB_RURAL, base.CICLOS_PE)
    for _, ini, fim in tabela for w in range(ini, fim + 1)
)


# ================= CALENDÁRIO =================
def agora():
    return dt.datetime.now(FUSO)


def id_semana_atual(hoje):
    return ANCORA_ID + (hoje - ANCORA_DATA).days // 7


def periodo_semana(id_semana):
    ini = ANCORA_DATA + dt.timedelta(days=(id_semana - ANCORA_ID) * 7)
    return ini, ini + dt.timedelta(days=6)


def escolher_ids(atual, tudo, ja_existe_historico):
    if atual < PRIMEIRA_ID:
        raise SystemExit(f"❌ Semana atual (id {atual}) anterior ao início do histórico (id {PRIMEIRA_ID}).")
    if atual > ULTIMA_ID_DEFINIDA:
        raise SystemExit(
            f"❌ Semana atual (id {atual}) fora dos ciclos definidos (último id: {ULTIMA_ID_DEFINIDA}). "
            "Atualize CICLOS_URB_RURAL, CICLOS_PE, os deslocamentos e a âncora de calendário "
            "(virada de ano) em pma_nova_colunas.py e coleta_automatica.py."
        )
    if tudo or not ja_existe_historico:
        return list(range(PRIMEIRA_ID, atual + 1))
    return list(range(max(PRIMEIRA_ID, atual - (ULTIMAS_N - 1)), atual + 1))


# ================= DADOS =================
def carregar_dados():
    if os.path.exists(ARQ_DADOS):
        with open(ARQ_DADOS, encoding="utf-8") as f:
            return json.load(f)
    return None


def nativo(lista):
    """Converte valores numpy em tipos nativos do Python (para o JSON)."""
    return [x.item() if hasattr(x, "item") else x for x in lista]


def montar_entrada(id_semana, df, pe_existente, ciclo, ciclo_pe):
    est, coord = base.salvar_relatorio(df, pe_existente)     # sem gravar Excel
    ini, fim = periodo_semana(id_semana)
    return {
        "id_semana": id_semana,
        "semana": id_semana - base.DESLOC_SEMANA,
        "ciclo_urb_rural": ciclo - base.DESLOC_CICLO,
        "ciclo_pe": ciclo_pe - base.DESLOC_CICLO_PE,
        "inicio": ini.isoformat(),
        "fim": fim.isoformat(),
        "coletado_em": agora().isoformat(timespec="minutes"),
        "estadual": nativo(est.iloc[-1, 1:].tolist()),        # linha TOTAL
        "coordenada": nativo(coord.iloc[-1, 1:].tolist()),    # linha TOTAL
    }


def gravar_dados(semanas_por_id):
    dados = {
        "atualizado_em": agora().isoformat(timespec="minutes"),
        "municipio": "Ponta Porã/MS",
        "colunas_estadual": ["IIP" if c == "IIP_2" else c for c in base.COLS_ESTADUAL],
        "colunas_coordenada": list(base.COLS_COORDENADA),
        "semanas": [semanas_por_id[k] for k in sorted(semanas_por_id)],
    }
    os.makedirs(os.path.dirname(ARQ_DADOS), exist_ok=True)
    with open(ARQ_DADOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)


# ================= LOGIN =================
def fazer_login(driver, usuario, senha):
    wait = WebDriverWait(driver, 30)
    driver.get(base.URL_LOGIN)
    wait.until(EC.presence_of_element_located((By.NAME, "cpf"))).send_keys(usuario)
    driver.find_element(By.ID, "senha").send_keys(senha)
    time.sleep(1)
    driver.find_element(By.CSS_SELECTOR, "button.btn-success[type=submit]").click()
    WebDriverWait(driver, 30).until(lambda d: "login" not in d.current_url)


# ================= MAIN =================
def main():
    tudo = "--tudo" in sys.argv
    usuario, senha = base.USUARIO, base.SENHA
    if not usuario or not senha:
        raise SystemExit("❌ Credenciais ausentes: defina EVISITA_USUARIO e EVISITA_SENHA (GitHub Secrets).")
    pe_existente = int(os.environ.get("PE_EXISTENTE") or base.PE_EXISTENTE_PADRAO)

    existente = carregar_dados()
    atual = id_semana_atual(agora().date())
    ids = escolher_ids(atual, tudo, existente is not None)

    print(f"Hoje (UTC-4): {agora():%d/%m/%Y %H:%M} | semana atual: {atual - base.DESLOC_SEMANA} (id {atual})")
    print("Semanas a coletar:", [f"{i - base.DESLOC_SEMANA} (id {i})" for i in ids])
    print(f"PE Existente: {pe_existente}")

    por_id = {s["id_semana"]: s for s in (existente or {}).get("semanas", [])}
    falhas = []

    driver = base.criar_driver()
    try:
        print("🔐 Login...")
        fazer_login(driver, usuario, senha)
        print("✅ Login OK")

        for n, sid in enumerate(ids, start=1):
            real = sid - base.DESLOC_SEMANA
            print(f"\n==================== SEMANA {real} (id {sid}) — {n}/{len(ids)} ====================")
            ciclo = base.ciclo_da_semana(base.CICLOS_URB_RURAL, sid)
            ciclo_pe = base.ciclo_da_semana(base.CICLOS_PE, sid)
            base.AVISOS.clear()
            try:
                df = base.coletar_semana(driver, sid, ciclo, ciclo_pe)
                if base.AVISOS:
                    # extração incompleta: não publica valores zerados por engano
                    raise RuntimeError("extração incompleta: " + " | ".join(base.AVISOS))
                por_id[sid] = montar_entrada(sid, df, pe_existente, ciclo, ciclo_pe)
                print(f"✅ Semana {real} coletada")
            except Exception as e:
                print(f"❌ Semana {real} falhou: {e}")
                falhas.append((real, str(e)))
    finally:
        driver.quit()

    if por_id:
        gravar_dados(por_id)
        print(f"\n💾 {ARQ_DADOS} atualizado ({len(por_id)} semanas no histórico)")

    if falhas:
        print("\n⚠️ Semanas com falha (os valores anteriores, se existirem, foram mantidos):")
        for real, msg in falhas:
            print(f"  - Semana {real}: {msg}")
        sys.exit(1)
    print("\n✅ Concluído sem falhas.")


if __name__ == "__main__":
    main()
