# eVisita — totais por semana (Ponta Porã/MS)

Coleta automática no eVisita e página com **o TOTAL de cada semana** nas duas planilhas
(`Planilha Estadual` e `Resposta Coordenada`).

- **Segunda e terça, 03:00 (Ponta Porã)** o GitHub Actions coleta a **semana atual e as 2 anteriores**
  (ex.: ids 332, 331 e 330). As semanas já coletadas são atualizadas, e as novas entram no histórico.
- **Na primeira execução** (ainda sem `docs/dados.json`) coleta **da semana 35 (id 322) até a atual**.
- A página `docs/index.html` (GitHub Pages) lê `docs/dados.json` e mostra uma linha por semana.

## Como publicar

1. Crie o repositório no GitHub e envie estes arquivos.
   > **Nunca** envie `credenciais_local.py` (já está no `.gitignore`). A senha só vai nos *Secrets*.
2. **Settings → Secrets and variables → Actions → New repository secret**:
   - `EVISITA_USUARIO` — CPF de acesso ao eVisita
   - `EVISITA_SENHA` — senha
3. (Opcional) **Variables → New repository variable**: `PE_EXISTENTE` (padrão 62 se não existir).
4. **Settings → Pages → Build and deployment**: *Deploy from a branch* → branch `main`, pasta `/docs`.
5. **Actions → Coleta eVisita → Run workflow** para a primeira coleta (marque *tudo* se quiser refazer o histórico).
   O site fica em `https://SEU-USUARIO.github.io/NOME-DO-REPOSITORIO/`.

> No plano gratuito o GitHub Pages exige repositório **público**: qualquer pessoa com o link vê os totais.
> Confirme com a Secretaria se a divulgação é permitida. Se não for, use repositório privado (sem Pages)
> e baixe os dados, ou use um plano que permita Pages privado.

## Conferir antes de confiar

- O eVisita pode recusar acessos vindos dos servidores do GitHub (ficam fora do Brasil). Teste uma vez com
  *Run workflow*; se o login falhar, o log do Actions mostra o erro.
- Compare os valores de uma semana com a tela do eVisita antes de divulgar.
- Se a extração de alguma semana falhar, o valor anterior é mantido (nada zerado é publicado) e a execução
  fica marcada como falha, para você ser avisado.

## Virada de ano

Quando o ano acabar (semana 52 = id 339), a coleta para com uma mensagem. Atualize:

- `pma_nova_colunas.py`: `CICLOS_URB_RURAL`, `CICLOS_PE`, `DESLOC_SEMANA`, `DESLOC_CICLO`, `DESLOC_CICLO_PE`
  e `id_ano` (hoje 14, nas URLs).
- `coleta_automatica.py`: `ANCORA_ID`, `ANCORA_DATA` (id e data de início de uma semana conhecida) e `PRIMEIRA_ID`.

## Uso local (opcional)

```
pip install -r requirements.txt
cp credenciais_local.py.exemplo credenciais_local.py   # preencha CPF e senha
python pma_nova_colunas.py        # janela com botões; gera os Excel em ./relatorios
python coleta_automatica.py       # mesma coleta do Actions; atualiza docs/dados.json
```

## Dashboard e bloqueios

`docs/dashboard.html` mostra os resultados por semana e por mês, com destaque para os **bloqueios realizados**.
Como o eVisita não traz esse dado, preencha `docs/bloqueios.csv` (colunas: `semana` real, `bloqueios`, `quarteiroes_ubv`;
semana ausente = 0). Para usar uma planilha online, publique-a como CSV e troque `BLOQUEIOS_URL` no início do script da página.
O mês de cada semana é o mês em que cai a maioria dos seus dias (domingo a sábado).
