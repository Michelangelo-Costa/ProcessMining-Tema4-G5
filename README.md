# Process Mining — Tema 4 | Grupo G5

**Disciplina:** Mineração de Dados — UNIFESSPA  
**Docente:** Prof. Adam D. F. dos Santos  
**Grupo:** Michelangelo · João Marcos · André · Daniel  
**Apresentação:** 23/06/2026

---

## Sobre o trabalho

Aplicação de técnicas de **Process Mining** ao processo de concessão de empréstimos
do BPI Challenge 2017, cobrindo:

- Descoberta de processos: Alpha Miner e Inductive Miner
- Conformance checking: fitness, precision, generalization, simplicity
- Análise de performance e identificação de gargalos

> **Nota:** O dataset real (BPI17) não pôde ser baixado por restrições de rede no
> ambiente de execução. Foi usado um log sintético estruturalmente fiel ao processo real,
> gerado de forma determinística (seed = 42). As limitações são documentadas em detalhe
> no relatório (Seção 9).

---

## Estrutura do repositório

```
ProcessMining-G5/
├── notebook/
│   └── PM_Tema4_BPI2017_Notebook.ipynb   # Notebook reprodutível (principal entregável)
│
├── report/
│   ├── main.tex                           # Relatório técnico (LaTeX)
│   └── figures/                           # Figuras geradas pelo código
│
├── code/
│   ├── pm_toolkit.py                      # Biblioteca própria de process mining
│   ├── 01_generate_log.py                 # Geração do event log sintético
│   └── 02_run_analysis.py                 # Pipeline de análise completo
│
├── data/                                  # Gerado ao rodar o código
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

> Necessário ter o [Graphviz](https://graphviz.org/download/) instalado no sistema
> (além do pacote Python).

### Passo a passo

```bash
# 1. Gerar o event log sintético
cd code
python 01_generate_log.py

# 2. Rodar a análise completa (gera figuras e tabelas)
python 02_run_analysis.py

# 3. Abrir o notebook para análise interativa
cd ../notebook
jupyter notebook PM_Tema4_BPI2017_Notebook.ipynb
```

### Compilar o relatório (Overleaf ou local)

1. Faça upload da pasta `report/` para o [Overleaf](https://overleaf.com)  
2. Certifique-se de que as imagens estão na subpasta `figures/`  
3. Compile `main.tex` com **pdfLaTeX**

---

## Referências principais

- VAN DER AALST, W. M. P. *Process Mining: Data Science in Action*. 2. ed. Springer, 2016.
- VAN DER AALST et al. Process Mining Manifesto. 2011.
- Documentação PM4Py: https://pm4py.fit.fraunhofer.de/
