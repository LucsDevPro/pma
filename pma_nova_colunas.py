# -*- coding: utf-8 -*-

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import re
import os
import time
import getpass
import sys
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

# ============================ AJUSTES RÁPIDOS ============================
MARGEM_COLUNA = 0           # folga extra na largura das colunas (0 = ajuste exato; 1, 2... = mais folga)
GERAR_INDIVIDUAL_PADRAO = True   # checkbox "relatório individual por semana" já marcado?
GERAR_TOTAL_PADRAO = True        # checkbox "planilha total (várias semanas)" já marcado?
TIMEOUT_COMANDO = 600       # segundos que o Selenium espera uma resposta do navegador (padrão era 120)
TIMEOUT_PAGINA = 300        # segundos para uma página terminar de carregar
ESTRATEGIA_CARGA = "eager"  # "eager" = não espera imagens/scripts externos lentos (só o HTML); "normal" = espera tudo
# =========================================================================

# ================= CONFIG =================
URL_LOGIN = "https://evisita.saude.ms.gov.br/login"
URL_BASE = "https://evisita.saude.ms.gov.br/endemias/pncd_v2"
URL_FOCOS = "https://evisita.saude.ms.gov.br/endemias/relatorios/geral"

# Credenciais: use credenciais_local.py (uso local) ou as variáveis de ambiente
# EVISITA_USUARIO / EVISITA_SENHA (GitHub Secrets). Se faltarem, o script pergunta.
try:
    # arquivo local (NÃO vai para o GitHub): crie credenciais_local.py com USUARIO = "..." e SENHA = "..."
    from credenciais_local import USUARIO, SENHA
except ImportError:
    USUARIO = os.environ.get("EVISITA_USUARIO", "")
    SENHA = os.environ.get("EVISITA_SENHA", "")

COD_MUNICIPIO = "5006606"   # Ponta Porã/MS
TOTAL_MUNICIPIO = 47246     # total de imóveis do município (configurável)

# Mantém o comportamento do script original (descarta células vazias antes de
# aplicar os índices 6, 8, 9, 11, 12, 14, 16-22), que já funcionava corretamente.
FILTRAR_CELULAS_VAZIAS = True

AVISOS = []  # problemas de extração, exibidos ao final

# Ciclos e as semanas (ids do sistema) que pertencem a cada um: (id_ciclo, semana_inicio, semana_fim)
CICLOS_URB_RURAL = [
    (164, 322, 330),
    (165, 331, 339),
]
CICLOS_PE = [
    (156, 322, 326),
    (157, 327, 330),
    (158, 331, 334),
    (159, 335, 339),
]

# Números "reais" mostrados ao usuário = id do sistema - deslocamento
DESLOC_SEMANA = 287     # id 322 = semana 35
DESLOC_CICLO = 159      # id 164 = ciclo 5 (URB/RURAL)
DESLOC_CICLO_PE = 147   # id 156 = ciclo 9 (P.E)

# Botões de semana: (número real, id do sistema) — somente semanas que têm ciclo definido
SEMANAS_ID = sorted({w for _, ini, fim in CICLOS_URB_RURAL for w in range(ini, fim + 1)} &
                    {w for _, ini, fim in CICLOS_PE for w in range(ini, fim + 1)})
OPCOES_SEMANA = [(i - DESLOC_SEMANA, i) for i in SEMANAS_ID]


def ciclo_da_semana(tabela, id_semana):
    """Retorna o id do ciclo ao qual a semana pertence."""
    for id_ciclo, ini, fim in tabela:
        if ini <= id_semana <= fim:
            return id_ciclo
    raise ValueError(f"Semana (id {id_semana}) fora dos ciclos pré-definidos")

PE_EXISTENTE_PADRAO = 62
PASTA_RELATORIOS = "relatorios"   # pasta (ao lado do script) onde os arquivos são salvos

# ================= DRIVER =================
def criar_driver():
    opt = Options()
    if os.environ.get("EVISITA_HEADLESS") == "1":      # usado no GitHub Actions
        opt.add_argument("--headless=new")
        opt.add_argument("--no-sandbox")
        opt.add_argument("--disable-dev-shm-usage")
    opt.add_argument("--window-size=1920,1080")
    opt.add_argument("--log-level=3")
    opt.add_experimental_option("excludeSwitches", ["enable-logging"])
    opt.page_load_strategy = ESTRATEGIA_CARGA
    driver = webdriver.Chrome(options=opt)
    try:
        driver.command_executor._client_config.timeout = TIMEOUT_COMANDO
    except Exception:
        pass
    driver.set_page_load_timeout(TIMEOUT_PAGINA)
    return driver

# ================= UTILS =================
def num(txt):
    return int(re.sub(r"[^\d]", "", txt) or 0)

def num_float(txt):
    txt = txt.replace(",", ".").replace("%", "")
    return float(re.sub(r"[^\d.]", "", txt) or 0)

# ================= EXTRAÇÃO PRINCIPAL =================
def extrair_dados(html, nome):
    soup = BeautifulSoup(html, "html.parser")

    dados = {
        "Area": nome,
        "Total_Imoveis": 0,
        "Trat_Focal": 0,
        "Recuperados": 0,
        "Amostras": 0,
        "Fechados": 0,
        "Recusado": 0,
        "A1": 0, "A2": 0, "B": 0, "C": 0, "D1": 0, "D2": 0, "E": 0,
        "Larvicida_Gramas": 0,
        "Adulticida_Gramas": 0,
        "Focos_Trabalhados": 0,
        "Focos_Recuperados": 0
    }

    try:
        t = soup.find_all("table", class_="table-bordered")[0]
        linha = t.find_all("tr")[2]
        tds = linha.find_all("td")
        if FILTRAR_CELULAS_VAZIAS:
            cols = [c.get_text(strip=True) for c in tds if c.get_text(strip=True)]
        else:
            cols = [c.get_text(strip=True) for c in tds]

        # diagnóstico: permite conferir cada índice com a tela do eVisita
        print(f"   [{nome}] células lidas: {len(cols)}")
        for i in (6, 8, 9, 11, 12, 14, 16, 17, 18, 19, 20, 21, 22):
            if i < len(cols):
                print(f"   [{nome}] cols[{i}] = {cols[i]!r}")

        if len(cols) < 23:
            raise ValueError(f"linha com {len(cols)} células (esperado >= 23): estrutura HTML mudou?")

        dados["Total_Imoveis"] = num(cols[8])
        dados["Trat_Focal"] = num(cols[6])
        dados["Recuperados"] = num(cols[9])
        dados["Amostras"] = num(cols[11])
        dados["Fechados"] = num(cols[12])
        dados["Recusado"] = num(cols[14])

        dados["A1"] = num(cols[16])
        dados["A2"] = num(cols[17])
        dados["B"] = num(cols[18])
        dados["C"] = num(cols[19])
        dados["D1"] = num(cols[20])
        dados["D2"] = num(cols[21])
        dados["E"] = num(cols[22])

        dep = soup.find_all("table", class_="table-bordered")[2]
        ult = dep.find_all("tr")[-1].find_all("td")

        if len(ult) >= 7:
            dados["Larvicida_Gramas"] = num_float(ult[2].get_text())
            dados["Adulticida_Gramas"] = num_float(ult[6].get_text())
        else:
            AVISOS.append(f"{nome}: tabela de depósitos com {len(ult)} células (esperado >= 7); larvicida/adulticida = 0")

        if dados["Amostras"] > dados["Total_Imoveis"]:
            AVISOS.append(f"{nome}: Amostras > Total_Imoveis — verifique os índices das colunas")

    except Exception as e:
        print(f"❌ Erro dados {nome}:", e)
        AVISOS.append(f"{nome}: falha na extração dos dados principais ({e}); valores zerados")

    return dados

# ================= FOCOS =================
def extrair_focos(html, nome=""):
    soup = BeautifulSoup(html, "html.parser")

    try:
        tabela = soup.find("table", class_="table-relatorios")
        linha = tabela.find("tbody").find("tr")
        cols = linha.find_all("td")

        return {
            "Focos_Trabalhados": num(cols[7].get_text()),
            "Focos_Recuperados": num(cols[14].get_text())
        }

    except Exception as e:
        print(f"❌ Erro focos {nome}:", e)
        AVISOS.append(f"{nome}: falha na extração de focos ({e}); valores zerados")
        return {"Focos_Trabalhados": 0, "Focos_Recuperados": 0}

# ================= URLs =================
def url(regiao, atv, ciclo, semana):
    return (
        f"{URL_BASE}?"
        f"id_municipio=62&"
        f"id_regiao={regiao}&"
        f"id_area=&"
        f"id_atividade={atv}&"
        f"id_ano=14&"
        f"id_ciclo={ciclo}&"
        f"semana_inicio={semana}&"
        f"semana_fim={semana}&"
        f"acao=filtrar"
    )

def url_focos(atv, ciclo, semana):
    return (
        f"{URL_FOCOS}?"
        f"id_municipio=62&"
        f"id_atividade={atv}&"
        f"id_ano=14&"
        f"id_ciclo={ciclo}&"
        f"semana_inicio={semana}&"
        f"semana_fim={semana}&"
        f"acao=filtrar"
    )

# ================= EXCEL: COLUNAS OFICIAIS =================
COLS_ESTADUAL = [
    "Imóvel trabalhado", "Trabalhado com foco", "Tratado com larvicida",
    "Fechado", "Recusa", "Recuperado", "Recuperado com foco",
    "Not - Den", "Not - Chik", "Not - Zik",
    "PE Existente", "PE Trabalhado",
    "IIP", "IB", "IIP_2",          # IIP_2 vira "IIP" no cabeçalho do Excel
    "Focal - Gramas", "Perifocal - Sachê"
]

COLS_COORDENADA = [
    "Imóveis trab", "Imóveis pendentes",
    "Bloqueios de transmissão (portátil)", "Quarteirões - UBV pesado",
    "Índice de pendência (%)", "Cobertura (%)",
    "A1", "A2", "B", "C", "D1", "D2", "E"
]

COLS_PERCENTUAL = {"IIP", "IB", "IIP_2", "Índice de pendência (%)", "Cobertura (%)"}


def pct(a, b):
    return round(a / b * 100, 2) if b else 0


def montar_estadual(df, pe_existente):
    linhas = []
    for _, r in df.iterrows():
        e_pe = r["Area"] == "P.E"
        iip = pct(r["Amostras"], r["Total_Imoveis"])
        linhas.append([
            "P.E." if e_pe else r["Area"],
            r["Total_Imoveis"], r["Focos_Trabalhados"], r["Trat_Focal"],
            r["Fechados"], r["Recusado"], r["Recuperados"], r["Focos_Recuperados"],
            0, 0, 0,
            pe_existente if e_pe else 0,
            r["Total_Imoveis"] if e_pe else 0,
            iip, iip, 0,
            r["Larvicida_Gramas"], r["Adulticida_Gramas"]
        ])

    pe = df[df["Area"] == "P.E"].iloc[0]
    iip_pe = pct(pe["Amostras"], pe["Total_Imoveis"])
    linhas.append([
        "TOTAL",
        df["Total_Imoveis"].sum(), df["Focos_Trabalhados"].sum(), df["Trat_Focal"].sum(),
        df["Fechados"].sum(), df["Recusado"].sum(), df["Recuperados"].sum(),
        df["Focos_Recuperados"].sum(),
        0, 0, 0,
        pe_existente,              # contado uma única vez
        pe["Total_Imoveis"],       # somente P.E.
        iip_pe, iip_pe, 0,
        df["Larvicida_Gramas"].sum(), df["Adulticida_Gramas"].sum()
    ])
    return pd.DataFrame(linhas, columns=["Atividade"] + COLS_ESTADUAL)


def montar_coordenada(df):
    linhas = []
    for _, r in df.iterrows():
        trab, pend = r["Total_Imoveis"], r["Fechados"]
        linhas.append([
            "P.E." if r["Area"] == "P.E" else r["Area"],
            trab, pend, 0, 0,
            pct(pend, trab + pend), pct(trab, TOTAL_MUNICIPIO),
            r["A1"], r["A2"], r["B"], r["C"], r["D1"], r["D2"], r["E"]
        ])

    trab, pend = df["Total_Imoveis"].sum(), df["Fechados"].sum()
    linhas.append([
        "TOTAL", trab, pend, 0, 0,
        pct(pend, trab + pend), pct(trab, TOTAL_MUNICIPIO),
        df["A1"].sum(), df["A2"].sum(), df["B"].sum(), df["C"].sum(),
        df["D1"].sum(), df["D2"].sum(), df["E"].sum()
    ])
    return pd.DataFrame(linhas, columns=["Atividade"] + COLS_COORDENADA)


def formatar_aba(worksheet, df, corpo_limpo=False):   # corpo_limpo mantido por compatibilidade (sem efeito)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    FONTE, TAM = "Bahnschrift Light", 8

    # renomeia IIP_2 -> IIP (mantém os dois campos IIP)
    for cell in worksheet[1]:
        if cell.value == "IIP_2":
            cell.value = "IIP"

    # autoajuste das colunas, com margem 0 (largura = maior texto exibido na coluna)
    for idx, col in enumerate(df.columns, start=1):
        nome_col = "IIP" if col == "IIP_2" else str(col)
        if col in COLS_PERCENTUAL:
            textos = [f"{float(v):.2f}" for v in df[col]]     # como aparece no Excel (0.00)
        else:
            textos = [str(v) for v in df[col]]
        max_len = max(max(len(t) for t in textos), len(nome_col))
        worksheet.column_dimensions[worksheet.cell(row=1, column=idx).column_letter].width = min(max_len + MARGEM_COLUNA, 60)

    # corpo: centralizado + percentuais com 2 casas
    ultima = worksheet.max_row
    for row in worksheet.iter_rows(min_row=2, max_row=ultima):
        for cell in row:
            cell.alignment = Alignment(horizontal='center')
            cell.font = Font(name=FONTE, size=TAM)
            cell.border = thin_border   # todas as bordas
            if df.columns[cell.column - 1] in COLS_PERCENTUAL:
                cell.number_format = "0.00"

    # cabeçalho
    for cell in worksheet[1]:
        cell.fill = header_fill
        cell.font = Font(name=FONTE, size=TAM, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = thin_border

    # linha TOTAL: sem preenchimento e sem negrito (fundo branco normal), com todas as bordas
    for col_idx in range(1, worksheet.max_column + 1):
        cell = worksheet.cell(row=ultima, column=col_idx)
        cell.font = Font(name=FONTE, size=TAM)
        cell.fill = PatternFill(fill_type=None)
        cell.border = thin_border

    worksheet.freeze_panes = "A2"

# ================= VALIDAÇÕES =================
def validar(nome_arquivo, df):
    from openpyxl import load_workbook
    problemas = list(AVISOS)
    wb = load_workbook(nome_arquivo)

    if wb.sheetnames != ["Planilha Estadual", "Resposta Coordenada"]:
        problemas.append(f"Abas incorretas: {wb.sheetnames}")

    esperado = {
        "Planilha Estadual": ["Atividade"] + [c if c != "IIP_2" else "IIP" for c in COLS_ESTADUAL],
        "Resposta Coordenada": ["Atividade"] + COLS_COORDENADA,
    }
    for aba, cab in esperado.items():
        if aba not in wb.sheetnames:
            continue
        ws = wb[aba]
        if [c.value for c in ws[1]] != cab:
            problemas.append(f"Ordem/nomes de colunas incorretos em '{aba}'")
        if [ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)] != ["RURAL", "P.E.", "URBANA", "TOTAL"]:
            problemas.append(f"Linhas incorretas em '{aba}'")
        for row in ws.iter_rows(min_row=2, min_col=2):
            for c in row:
                if c.value is None or c.value == "" or c.value != c.value:
                    problemas.append(f"Célula vazia/NaN em {aba}!{c.coordinate}")

    # TOTAL = soma das atividades
    ws = wb["Resposta Coordenada"]
    if ws.cell(row=5, column=2).value != df["Total_Imoveis"].sum():
        problemas.append("Imóveis trab (TOTAL) não confere com a soma das atividades")
    if ws.cell(row=5, column=3).value != df["Fechados"].sum():
        problemas.append("Imóveis pendentes (TOTAL) não confere com a soma de Fechados")

    for _, r in df.iterrows():
        if r["Total_Imoveis"] == 0:
            problemas.append(f"{r['Area']}: Total_Imoveis = 0 (confira semana/ciclo)")

    return problemas

# ================= SELEÇÃO DE PARÂMETROS (BOTÕES) =================
def rotulo(opcoes, cod):
    """Converte o id do sistema no número real mostrado ao usuário."""
    return next(r for r, c in opcoes if str(c) == str(cod))


def _combinacao(id_semana):
    """(id_semana, id_ciclo URB/RURAL, id_ciclo P.E) de uma semana."""
    return (
        int(id_semana),
        ciclo_da_semana(CICLOS_URB_RURAL, int(id_semana)),
        ciclo_da_semana(CICLOS_PE, int(id_semana)),
    )


def _interpretar_semanas(txt):
    """Aceita '35,36,40-44' (números reais). Retorna lista de ids ou None se inválido."""
    reais = {r: c for r, c in OPCOES_SEMANA}
    ids = set()
    try:
        for parte in txt.replace(" ", "").split(","):
            if not parte:
                continue
            if "-" in parte:
                ini, fim = (int(x) for x in parte.split("-"))
                nums = range(ini, fim + 1)
            else:
                nums = [int(parte)]
            for n in nums:
                if n not in reais:
                    return None
                ids.add(reais[n])
    except ValueError:
        return None
    return sorted(ids) or None


def _escolher_terminal():
    while True:
        txt = input(
            f"Semanas ({OPCOES_SEMANA[0][0]} a {OPCOES_SEMANA[-1][0]}; ex.: 35,36,40-44): "
        ).strip()
        ids = _interpretar_semanas(txt)
        if ids:
            break
        print("Valor fora das opções permitidas.")
    pe = input(f"PE Existente [{PE_EXISTENTE_PADRAO}]: ").strip()
    individual, total = True, False
    if len(ids) > 1:
        while True:
            op = input("Gerar: 1 = só individuais | 2 = só planilha total | 3 = ambos [3]: ").strip() or "3"
            if op in ("1", "2", "3"):
                break
        individual, total = op in ("1", "3"), op in ("2", "3")
    return ([_combinacao(i) for i in ids],
            int(pe) if pe.isdigit() else PE_EXISTENTE_PADRAO, individual, total)


def escolher_parametros():
    """Janela com botões de semana (várias podem ser marcadas). Os ciclos são
    definidos automaticamente. Retorna ([(id_semana, id_ciclo, id_ciclo_pe), ...], pe_existente, gerar_individual, gerar_total)."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
    except Exception:
        print("⚠️ Interface gráfica indisponível; usando o terminal.")
        return _escolher_terminal()

    root.title("eVisita - Parâmetros")
    root.resizable(False, False)

    vars_sem = {cod: tk.IntVar(value=0) for _, cod in OPCOES_SEMANA}
    vars_sem[OPCOES_SEMANA[-1][1]].set(1)   # última semana já marcada
    v_info = tk.StringVar()
    v_pe_exist = tk.StringVar(value=str(PE_EXISTENTE_PADRAO))
    resultado = {}

    def atualizar(*_):
        marcadas = sorted(c for c, v in vars_sem.items() if v.get())
        if not marcadas:
            v_info.set("Nenhuma semana selecionada")
            return
        reais = ", ".join(str(c - DESLOC_SEMANA) for c in marcadas)
        v_info.set(f"{len(marcadas)} semana(s): {reais}")

    def marcar(ids):
        for c, v in vars_sem.items():
            v.set(1 if c in ids else 0)
        atualizar()

    frame = tk.LabelFrame(root, text="Semanas (clique para marcar/desmarcar)", padx=6, pady=6)
    frame.grid(row=0, column=0, padx=10, pady=6, sticky="ew")
    for i, (real, cod) in enumerate(OPCOES_SEMANA):
        tk.Checkbutton(
            frame, text=str(real), variable=vars_sem[cod], command=atualizar,
            indicatoron=0, width=6, pady=4, selectcolor="#9DC3E6"
        ).grid(row=i // 9, column=i % 9, padx=2, pady=2)

    rapido = tk.LabelFrame(root, text="Seleção rápida", padx=6, pady=6)
    rapido.grid(row=1, column=0, padx=10, pady=6, sticky="ew")
    tk.Button(rapido, text="Todas", width=10,
              command=lambda: marcar({c for _, c in OPCOES_SEMANA})).pack(side="left", padx=3)
    tk.Button(rapido, text="Limpar", width=10, command=lambda: marcar(set())).pack(side="left", padx=3)
    for id_ciclo, ini, fim in CICLOS_URB_RURAL:
        tk.Button(
            rapido, text=f"Ciclo URB/RURAL {id_ciclo - DESLOC_CICLO}", width=18,
            command=lambda i=ini, f=fim: marcar(set(range(i, f + 1)) & {c for _, c in OPCOES_SEMANA})
        ).pack(side="left", padx=3)

    tk.Label(root, textvariable=v_info, font=("Segoe UI", 10, "bold")).grid(row=2, column=0, pady=4)

    f = tk.LabelFrame(root, text="PE Existente", padx=6, pady=6)
    f.grid(row=3, column=0, padx=10, pady=6, sticky="ew")
    tk.Entry(f, textvariable=v_pe_exist, width=10, justify="center").pack()
    atualizar()

    v_ind = tk.IntVar(value=1 if GERAR_INDIVIDUAL_PADRAO else 0)
    v_tot = tk.IntVar(value=1 if GERAR_TOTAL_PADRAO else 0)
    saida = tk.LabelFrame(root, text="O que gerar", padx=6, pady=6)
    saida.grid(row=4, column=0, padx=10, pady=6, sticky="ew")
    tk.Checkbutton(saida, text="Relatório individual de cada semana", variable=v_ind).pack(anchor="w")
    tk.Checkbutton(saida, text="Planilha total (uma linha por semana; só com 2 ou mais semanas)",
                   variable=v_tot).pack(anchor="w")

    def iniciar():
        marcadas = sorted(c for c, v in vars_sem.items() if v.get())
        if not marcadas:
            messagebox.showerror("Erro", "Selecione ao menos uma semana.")
            return
        if not v_pe_exist.get().strip().isdigit():
            messagebox.showerror("Erro", "PE Existente deve ser um número.")
            return
        if not v_ind.get() and not v_tot.get():
            messagebox.showerror("Erro", "Marque ao menos uma opção em 'O que gerar'.")
            return
        resultado["v"] = ([_combinacao(c) for c in marcadas], int(v_pe_exist.get().strip()),
                          bool(v_ind.get()), bool(v_tot.get()))
        root.destroy()

    b = tk.Frame(root)
    b.grid(row=5, column=0, pady=10)
    tk.Button(b, text="Iniciar", width=12, command=iniciar).pack(side="left", padx=6)
    tk.Button(b, text="Cancelar", width=12, command=root.destroy).pack(side="left", padx=6)

    root.mainloop()
    if "v" not in resultado:
        print("Cancelado.")
        sys.exit(0)
    return resultado["v"]

# ================= COLETA DE UMA SEMANA =================
def coletar_semana(driver, semana, ciclo, ciclo_pe):
    areas = [
        ("RURAL",  218, 2, ciclo),
        ("P.E",    263, 3, ciclo_pe),
        ("URBANA", 217, 4, ciclo)
    ]
    dados = []

    for nome, reg, atv, ciclo_ref in areas:
        print(f"\n🔍 Coletando {nome}...")

        # ===== DADOS PRINCIPAIS =====
        u = url(reg, atv, ciclo_ref, semana)
        print("URL dados:", u)
        t1 = time.time()
        driver.get(u)

        # espera tabela carregar
        WebDriverWait(driver, 120).until(
            lambda d: len(d.find_elements(By.CSS_SELECTOR, "table.table-bordered tr")) >= 3
        )
        print(f"⏱️ Carregado em {time.time() - t1:.1f}s")

        d = extrair_dados(driver.page_source, nome)

        # ===== FOCOS =====
        uf = url_focos(atv, ciclo_ref, semana)
        print("URL focos:", uf)
        t2 = time.time()
        driver.get(uf)

        WebDriverWait(driver, 120).until(
            lambda d: "Trabalhados c/ Focos" in d.page_source
        )
        print(f"⏱️ Focos carregados em {time.time() - t2:.1f}s")

        d.update(extrair_focos(driver.page_source, nome))
        dados.append(d)
        print(f"✅ {nome} concluído!")

    return pd.DataFrame(dados)


def salvar_relatorio(df, pe_existente, caminho=None):
    """Monta as duas tabelas e, se 'caminho' for informado, grava o Excel individual."""
    df_estadual = montar_estadual(df, pe_existente)
    df_coord = montar_coordenada(df)

    if caminho:
        with pd.ExcelWriter(caminho, engine='openpyxl') as writer:
            df_estadual.to_excel(writer, index=False, sheet_name='Planilha Estadual')
            df_coord.to_excel(writer, index=False, sheet_name='Resposta Coordenada')
            formatar_aba(writer.sheets['Planilha Estadual'], df_estadual)
            formatar_aba(writer.sheets['Resposta Coordenada'], df_coord)

    return df_estadual, df_coord


def validar_sem_arquivo(df):
    """Validação básica quando o relatório individual não é gravado."""
    problemas = list(AVISOS)
    for _, r in df.iterrows():
        if r["Total_Imoveis"] == 0:
            problemas.append(f"{r['Area']}: Total_Imoveis = 0 (confira semana/ciclo)")
    return problemas


def salvar_consolidado(totais, caminho):
    """totais: lista de (semana_real, df_estadual, df_coord) de cada semana gerada.
    Gera um Excel com uma linha TOTAL por semana, nas duas abas."""
    linhas_e, linhas_c = [], []
    for real, df_e, df_c in totais:
        linhas_e.append([f"Semana {real}"] + df_e.iloc[-1, 1:].tolist())   # linha TOTAL
        linhas_c.append([f"Semana {real}"] + df_c.iloc[-1, 1:].tolist())
    cons_e = pd.DataFrame(linhas_e, columns=["Semana"] + COLS_ESTADUAL)
    cons_c = pd.DataFrame(linhas_c, columns=["Semana"] + COLS_COORDENADA)

    with pd.ExcelWriter(caminho, engine='openpyxl') as writer:
        cons_e.to_excel(writer, index=False, sheet_name='Planilha Estadual')
        cons_c.to_excel(writer, index=False, sheet_name='Resposta Coordenada')
        formatar_aba(writer.sheets['Planilha Estadual'], cons_e, corpo_limpo=True)
        formatar_aba(writer.sheets['Resposta Coordenada'], cons_c, corpo_limpo=True)


def nome_consolidado(reais):
    if reais == list(range(reais[0], reais[-1] + 1)):
        sufixo = f"{reais[0]}_a_{reais[-1]}"
    elif len(reais) <= 8:
        sufixo = "_".join(str(r) for r in reais)
    else:
        sufixo = f"{reais[0]}_a_{reais[-1]}_{len(reais)}sem"
    return f"total_semanas_{sufixo}.xlsx"

# ================= MAIN =================
def main():
    semanas, pe_existente, gerar_individual, gerar_total = escolher_parametros()

    # Com uma única semana não há planilha total: gera sempre o individual
    if len(semanas) == 1:
        gerar_individual, gerar_total = True, False
    # Planilha total só faz sentido com 2+ semanas; se só ela foi pedida, não grava individuais
    print(f"PE Existente: {pe_existente}")
    print(f"Individuais: {'sim' if gerar_individual else 'não'} | Planilha total: {'sim' if gerar_total else 'não'}")
    print("Semanas selecionadas:")
    for sem, cic, cic_pe in semanas:
        print(
            f"  Semana {sem - DESLOC_SEMANA} (id {sem}) | "
            f"Ciclo URB/RURAL {cic - DESLOC_CICLO} (id {cic}) | "
            f"Ciclo P.E {cic_pe - DESLOC_CICLO_PE} (id {cic_pe})"
        )

    pasta = os.path.join(os.path.dirname(os.path.abspath(__file__)), PASTA_RELATORIOS)
    os.makedirs(pasta, exist_ok=True)

    usuario = USUARIO or os.environ.get("EVISITA_USUARIO") or input("CPF/Usuário eVisita: ").strip()
    senha = SENHA or os.environ.get("EVISITA_SENHA") or getpass.getpass("Senha eVisita: ")

    driver = criar_driver()
    wait = WebDriverWait(driver, 15)
    resumo = []   # (semana real, arquivo individual ou None, [problemas], coletou_ok)
    totais = []   # (semana real, df_estadual, df_coord) das semanas geradas

    try:
        # ===== LOGIN (uma única vez) =====
        print("🔐 Login...")
        driver.get(URL_LOGIN)

        wait.until(EC.presence_of_element_located((By.NAME, "cpf"))).send_keys(usuario)
        driver.find_element(By.ID, "senha").send_keys(senha)
        time.sleep(1)
        driver.find_element(By.CSS_SELECTOR, "button.btn-success[type=submit]").click()

        # espera sair da tela de login
        WebDriverWait(driver, 30).until(
            lambda d: "login" not in d.current_url
        )
        print("✅ Login OK - URL:", driver.current_url)

        for n, (sem, cic, cic_pe) in enumerate(semanas, start=1):
            real = sem - DESLOC_SEMANA
            print(f"\n==================== SEMANA {real} ({n}/{len(semanas)}) ====================")
            AVISOS.clear()
            try:
                df = coletar_semana(driver, sem, cic, cic_pe)
                caminho = os.path.join(pasta, f"relatorio_semana_{real}.xlsx") if gerar_individual else None
                df_e, df_c = salvar_relatorio(df, pe_existente, caminho)
                problemas = validar(caminho, df) if caminho else validar_sem_arquivo(df)
                totais.append((real, df_e, df_c))
                resumo.append((real, caminho, problemas, True))
                if caminho:
                    print(f"✅ Semana {real} salva: {caminho}")
                else:
                    print(f"✅ Semana {real} coletada (entra só na planilha total)")
            except Exception as e:
                print(f"❌ Semana {real} falhou: {e}")
                resumo.append((real, None, [f"falha na coleta/gravação: {e}"], False))

        # ===== PLANILHA CONSOLIDADA (só quando mais de uma semana foi pedida) =====
        arquivo_consolidado = None
        if gerar_total and len(semanas) > 1 and totais:
            try:
                reais = [t[0] for t in totais]
                arquivo_consolidado = os.path.join(pasta, nome_consolidado(reais))
                salvar_consolidado(totais, arquivo_consolidado)
                print(f"\n📊 Planilha consolidada salva: {arquivo_consolidado}")
            except Exception as e:
                print(f"❌ Falha ao gerar a planilha consolidada: {e}")
                arquivo_consolidado = None

        # ===== RESUMO =====
        print("\n==================== RESUMO ====================")
        for real, caminho, problemas, ok in resumo:
            destino = os.path.basename(caminho) if caminho else "somente na planilha total"
            if ok and not problemas:
                print(f"✅ Semana {real}: OK -> {destino}")
            elif ok:
                print(f"⚠️ Semana {real}: coletada com problemas -> {destino}")
                for p in problemas:
                    print("     -", p)
            else:
                print(f"❌ Semana {real}: NÃO gerada")
                for p in problemas:
                    print("     -", p)
        if arquivo_consolidado:
            faltando = [r for r, _, _, ok in resumo if not ok]
            print(f"\n📊 Consolidado: {os.path.basename(arquivo_consolidado)}")
            if faltando:
                print(f"   ⚠️ Semanas ausentes no consolidado (falharam): {faltando}")
        print(f"\n📁 Pasta: {pasta}")
        print("Confira os valores de cada atividade com a tela do eVisita.")

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
