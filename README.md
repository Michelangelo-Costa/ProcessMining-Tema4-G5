# Process Mining — Tema 4 | Grupo G5

**Disciplina:** Mineração de Dados — UNIFESSPA  
**Docente:** Prof. Adam D. F. dos Santos  
**Grupo G5:** Michelangelo · João Marcos · André · Daniel  
**Apresentação:** 23/06/2026

---

## Resumo do trabalho

Este repositório contém o trabalho completo do **Tema 4 — Process Mining: Análise de Conformidade e Descoberta de Processos**, aplicado ao processo de concessão de empréstimos pessoais do **BPI Challenge 2017**.

O trabalho cobre o pipeline completo de Process Mining:

| Etapa | Técnica | Arquivo principal |
|---|---|---|
| Geração do log | Log sintético fiel ao BPI17 (seed=42) | `code/01_generate_log.py` |
| Exploração (EDA) | Frequência, duração, variantes | `notebook/` |
| Descoberta de processo | DFG, Alpha Miner, Inductive Miner | `code/pm_toolkit.py` |
| Conformance Checking | Fitness, Precision, Generalization, Simplicity | `code/pm_toolkit.py` |
| Análise de performance | Gargalos por par de atividades | `code/pm_toolkit.py` |

---

## Nota metodológica (importante)

O dataset real do BPI Challenge 2017 (arquivo `.xes`, ~1 GB, disponível em [4TU.ResearchData](https://doi.org/10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b)) **não pôde ser baixado** por restrições de rede no ambiente de execução disponível. Da mesma forma, o **PM4Py** não pôde ser instalado.

Diante dessa restrição, adotou-se a seguinte solução, documentada explicitamente no relatório (Seção 9 — Limitações):

1. **Log sintético estruturalmente fiel ao BPI17** — reproduz o vocabulário oficial de atividades, os três sub-processos reais (Application, Offer, Workflow), os laços de retrabalho e os múltiplos desfechos, com durações calibradas por distribuição log-normal. Gerado de forma determinística (`seed=42`), totalmente reprodutível.

2. **Implementação própria dos algoritmos** em Python puro (pandas, numpy, graphviz), sem dependência de PM4Py: DFG, Alpha Miner, Inductive Miner (com semântica formal de process tree), métricas de conformidade e análise de performance.

Os valores quantitativos absolutos (durações exatas, frequências exatas) **não devem ser comparados diretamente** à literatura do BPI17. A validade pretendida é **metodológica** — demonstração correta do pipeline completo com os padrões qualitativos corretos (gargalos em etapas manuais, alta variabilidade de variantes, laços de retrabalho), todos consistentes com os relatados na literatura publicada sobre o dataset real.

---

## Principais resultados

| Resultado | Valor |
|---|---|
| Casos no log | 3.000 |
| Eventos totais | 54.597 |
| Atividades distintas | 23 |
| Variantes distintas | 169 |
| Variante mais frequente | 19,3% dos casos |
| Duração média dos casos | ~5 dias |
| Duração p90 dos casos | ~8,4 dias |
| Fitness — DFG filtrado | 0,989 |
| Precision — DFG filtrado | 1,000 |
| Fitness — Inductive Miner | 0,997 |
| Precision — Inductive Miner | 0,066 (modelo flor) |
| Gargalos principais | W\_Call after offers, W\_Validate application |

O **Inductive Miner** gerou um **modelo flor** (fitness alta, precision muito baixa), revelando que o processo não possui estrutura hierárquica rígida o suficiente para decomposição em blocos sequência/paralelo/exclusão — achado qualitativo coerente com o processo real documentado na literatura.

---

## Estrutura do repositório

```
ProcessMining-G5/
├── notebook/
│   └── PM_Tema4_BPI2017_Notebook.ipynb   ← notebook principal (Google Colab)
│
├── report/
│   ├── main.tex                           ← relatório técnico (LaTeX/pdfLaTeX)
│   └── figures/                           ← figuras geradas pelo código
│       ├── 06_dfg_full.png
│       ├── 07_dfg_filtered_heuristic.png
│       └── 08_alpha_miner_net.png
│
├── code/
│   ├── pm_toolkit.py                      ← biblioteca própria de process mining
│   ├── 01_generate_log.py                 ← geração do event log sintético
│   ├── 02_run_analysis.py                 ← pipeline de análise completo
│   └── build_slides.py                    ← geração da apresentação (.pptx)
│
├── data/                                  ← gerado ao rodar o código
│   ├── event_log.csv
│   ├── variants.csv
│   ├── case_durations.csv
│   ├── top_deviations.csv
│   ├── performance_per_transition.csv
│   └── metrics_summary.json
│
└── Apresentacao_Tema4_ProcessMining_G5.pptx
```

---

## Como reproduzir

### Dependências

```bash
pip install pandas numpy matplotlib seaborn graphviz
```

> Necessário ter o executável [Graphviz](https://graphviz.org/download/) instalado no sistema (além do pacote Python `graphviz`).

### Opção A — Google Colab (recomendado)

1. Faça upload de `code/pm_toolkit.py` e `data/event_log.csv` para o Colab  
2. Abra e execute `notebook/PM_Tema4_BPI2017_Notebook.ipynb`  
3. A última célula gera e baixa automaticamente um `.zip` com todas as figuras

### Opção B — Local (requer Graphviz instalado)

```bash
# 1. Gerar o event log
cd code
python 01_generate_log.py

# 2. Rodar a análise (gera figuras e tabelas em report/figures/ e data/)
python 02_run_analysis.py

# 3. Notebook interativo
cd ../notebook
jupyter notebook PM_Tema4_BPI2017_Notebook.ipynb
```

### Compilar o relatório

1. Faça upload da pasta `report/` para o [Overleaf](https://overleaf.com)  
2. Verifique que as imagens estão em `figures/`  
3. Compile `main.tex` com **pdfLaTeX** (requer pacote `rotating`)

---

## Referências

- VAN DER AALST, W. M. P. *Process Mining: Data Science in Action*. 2. ed. Springer, 2016.
- VAN DER AALST, W. M. P.; WEIJTERS, A. J. M. M.; MARUSTER, L. Workflow Mining: Discovering Process Models from Event Logs. *IEEE TKDE*, v. 16, n. 9, 2004.
- LEEMANS, S. J. J.; FAHLAND, D.; VAN DER AALST, W. M. P. Discovering Block-Structured Process Models from Event Logs. *PETRI NETS*, 2013.
- VAN DONGEN, B. F. *BPI Challenge 2017*. 4TU.ResearchData, 2017. DOI: 10.4121/uuid:5f3067df-f10b-45da-b98b-86ae4c7a310b
- IEEE TASK FORCE ON PROCESS MINING. *Process Mining Manifesto*. 2011.
