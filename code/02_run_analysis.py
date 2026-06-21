"""
02_run_analysis.py
===================
Executa toda a analise de process mining sobre o event log sintetico
(../data/event_log.csv) e salva:
  - figuras (PNG) em ../figures/
  - tabelas (CSV) em ../data/
  - um resumo de metricas (JSON) em ../data/metrics_summary.json

Secoes:
  1. Exploracao inicial
  2. Process Discovery (Alpha Miner, Inductive Miner, DFG/Heuristic-like)
  3. Conformance Checking (fitness, precision, generalization, simplicity)
  4. Performance Analysis (gargalos)
  5. Variantes
"""

import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import graphviz
import shutil
import os

import pm_toolkit as pm

sns.set_theme(style="whitegrid", font_scale=0.95)
FIG_DIR = "../report/figures"
DATA_DIR = "../data"
GV_TMP = os.path.join(DATA_DIR, "gv_tmp")
os.makedirs(GV_TMP, exist_ok=True)

# ===========================================================================
# 0. CARGA
# ===========================================================================
df = pm.load_log(f"{DATA_DIR}/event_log.csv")
traces, times = pm.get_traces(df)
n_cases = df["case:concept:name"].nunique()
n_events = len(df)

metrics = {}
metrics["n_cases"] = int(n_cases)
metrics["n_events"] = int(n_events)
metrics["n_activities"] = int(df["concept:name"].nunique())
metrics["events_per_case_mean"] = float(n_events / n_cases)
metrics["period_start"] = str(df["time:timestamp"].min())
metrics["period_end"] = str(df["time:timestamp"].max())

# ===========================================================================
# 1. EXPLORACAO INICIAL
# ===========================================================================

# 1.1 Atividades mais frequentes
act_freq = df["concept:name"].value_counts()
act_freq.to_csv(f"{DATA_DIR}/activity_frequency.csv")

fig, ax = plt.subplots(figsize=(8, 6))
act_freq.sort_values().plot(kind="barh", ax=ax, color="#2a6f97")
ax.set_xlabel("Frequência absoluta (nº de eventos)")
ax.set_ylabel("Atividade")
ax.set_title("Frequência de atividades no event log")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/01_activity_frequency.png", dpi=150)
plt.close()

# 1.2 Distribuição temporal (eventos por mês)
df["month"] = df["time:timestamp"].dt.to_period("M").astype(str)
monthly = df.groupby("month").size()
fig, ax = plt.subplots(figsize=(9, 4.5))
monthly.plot(kind="bar", ax=ax, color="#1b4965")
ax.set_xlabel("Mês")
ax.set_ylabel("Nº de eventos")
ax.set_title("Distribuição temporal dos eventos")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/02_temporal_distribution.png", dpi=150)
plt.close()

# 1.3 Duração dos casos
durations = pm.case_durations(traces, times)
durations.to_csv(f"{DATA_DIR}/case_durations.csv", index=False)
metrics["case_duration_mean_days"] = float(durations["duration_days"].mean())
metrics["case_duration_median_days"] = float(durations["duration_days"].median())
metrics["case_duration_p90_days"] = float(durations["duration_days"].quantile(0.9))
metrics["case_duration_max_days"] = float(durations["duration_days"].max())

fig, ax = plt.subplots(figsize=(8, 5))
sns.histplot(durations["duration_days"], bins=40, ax=ax, color="#52b69a")
ax.axvline(durations["duration_days"].mean(), color="red", linestyle="--", label="média")
ax.axvline(durations["duration_days"].median(), color="orange", linestyle="--", label="mediana")
ax.set_xlabel("Duração do caso (dias)")
ax.set_ylabel("Nº de casos")
ax.set_title("Distribuição da duração dos casos (lead time)")
ax.legend()
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/03_case_duration_distribution.png", dpi=150)
plt.close()

# 1.4 Atividades iniciais e finais
dfg, start_acts, end_acts, act_freq_c = pm.build_dfg(traces)
pd.Series(start_acts).sort_values(ascending=False).to_csv(f"{DATA_DIR}/start_activities.csv")
pd.Series(end_acts).sort_values(ascending=False).to_csv(f"{DATA_DIR}/end_activities.csv")
metrics["start_activities"] = dict(start_acts.most_common())
metrics["end_activities"] = dict(end_acts.most_common())

fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
pd.Series(start_acts).sort_values().plot(kind="barh", ax=axes[0], color="#168aad")
axes[0].set_title("Atividades iniciais")
pd.Series(end_acts).sort_values().plot(kind="barh", ax=axes[1], color="#d62828")
axes[1].set_title("Atividades finais")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/04_start_end_activities.png", dpi=150)
plt.close()

# 1.5 Variantes
variants = pm.variant_analysis(traces)
variants.to_csv(f"{DATA_DIR}/variants.csv", index=False)
metrics["n_variants"] = int(len(variants))
metrics["top5_variants_pct_cumsum"] = float(variants["pct"].head(5).sum())
metrics["top1_variant_pct"] = float(variants["pct"].iloc[0])

fig, ax = plt.subplots(figsize=(9, 5))
top_n = 10
sns.barplot(data=variants.head(top_n), y=variants.head(top_n).index.astype(str), x="pct", ax=ax, color="#6a4c93")
ax.set_yticks(range(top_n))
ax.set_yticklabels([f"Variante {i+1} ({row.n_activities} at.)" for i, row in variants.head(top_n).iterrows()])
ax.set_xlabel("% dos casos")
ax.set_title(f"Top {top_n} variantes mais frequentes (de {len(variants)} no total)")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/05_top_variants.png", dpi=150)
plt.close()

# ===========================================================================
# 2. PROCESS DISCOVERY
# ===========================================================================

# 2.1 DFG completo (visualizacao "Heuristic-Miner-like": filtra arestas fracas)
def render_dfg(dfg, act_freq, start_acts, end_acts, path, freq_threshold_ratio=0.0, title=""):
    g = graphviz.Digraph(format="png")
    g.attr(rankdir="LR", fontsize="10")
    max_f = max(dfg.values())
    shown_acts = set()
    for (a, b), f in dfg.items():
        if f >= freq_threshold_ratio * max_f:
            shown_acts.add(a)
            shown_acts.add(b)
    for a in shown_acts:
        g.node(a, shape="box", style="rounded,filled", fillcolor="#cde7f0",
               fontsize="10", label=f"{a}\n({act_freq[a]})")
    g.node("START", shape="ellipse", style="filled", fillcolor="#90be6d", label="START")
    g.node("END", shape="ellipse", style="filled", fillcolor="#f3722c", label="END")
    for a, f in start_acts.items():
        if a in shown_acts:
            g.edge("START", a, label=str(f))
    for a, f in end_acts.items():
        if a in shown_acts:
            g.edge(a, "END", label=str(f))
    for (a, b), f in dfg.items():
        if f >= freq_threshold_ratio * max_f:
            g.edge(a, b, label=str(f), penwidth=str(1 + 4 * f / max_f))
    tmp_path = os.path.join(GV_TMP, os.path.basename(path))
    g.render(tmp_path, cleanup=False)
    shutil.copy(tmp_path + ".png", path + ".png")

render_dfg(dfg, act_freq_c, start_acts, end_acts, f"{FIG_DIR}/06_dfg_full", freq_threshold_ratio=0.0)
render_dfg(dfg, act_freq_c, start_acts, end_acts, f"{FIG_DIR}/07_dfg_filtered_heuristic", freq_threshold_ratio=0.10)

# 2.2 Alpha Miner
alpha_res = pm.alpha_miner(traces)
metrics["alpha_n_places"] = len(alpha_res.places)
metrics["alpha_n_transitions"] = len(alpha_res.transitions)

def render_alpha_net(alpha_res, path):
    g = graphviz.Digraph(format="png")
    g.attr(rankdir="LR")
    for t in alpha_res.transitions:
        g.node(t, shape="box", style="filled", fillcolor="#ffd6a5", fontsize="9")
    for p in alpha_res.places:
        g.node(p, shape="circle", style="filled", fillcolor="#caffbf", width="0.25", label="")
        for a in alpha_res.flow_in[p]:
            g.edge(a, p)
        for b in alpha_res.flow_out[p]:
            g.edge(p, b)
    tmp_path = os.path.join(GV_TMP, os.path.basename(path))
    g.render(tmp_path, cleanup=False)
    shutil.copy(tmp_path + ".png", path + ".png")

render_alpha_net(alpha_res, f"{FIG_DIR}/08_alpha_miner_net")

# 2.3 Inductive Miner
tree = pm.inductive_miner(traces)
with open(f"{DATA_DIR}/inductive_tree.txt", "w", encoding="utf-8") as f:
    f.write(repr(tree))
metrics["inductive_tree_repr"] = repr(tree)
metrics["inductive_n_leaves"] = len(pm.process_tree_leaves_in_order(tree))

# Modelo derivado da semantica formal da process tree (estruturalmente
# independente do DFG do log) - usado abaixo na secao de conformidade
_, _, model_edges_inductive = pm.process_tree_semantics(tree)

# ===========================================================================
# 3. CONFORMANCE CHECKING
# ===========================================================================
# Modelo de referencia = DFG filtrado (>=10% da frequencia maxima), simulando
# um "modelo de processo esperado" mais limpo, conforme pratica usual em
# estudos de conformidade (comparar log bruto a um modelo idealizado)
model_edges_strict = pm.dfg_based_model_edges(dfg, freq_threshold_ratio=0.10)
model_edges_loose = pm.dfg_based_model_edges(dfg, freq_threshold_ratio=0.0)

# Modelo independente: pares (a,b) implicitamente permitidos pela rede do
# Alpha Miner (a in flow_in[p] e b in flow_out[p] para algum place p). Ao
# contrário dos modelos baseados no DFG (que são, por definição, um
# subconjunto do próprio log e por isso produzem precisão trivialmente
# igual a 1), este modelo é derivado de um algoritmo de descoberta
# independente e pode conter conexões nunca observadas no log (low
# precision) ou deixar de representar conexões observadas (low fitness) -
# uma comparação efetivamente informativa.
model_edges_alpha = set()
for p in alpha_res.places:
    for a in alpha_res.flow_in[p]:
        for b in alpha_res.flow_out[p]:
            model_edges_alpha.add((a, b))

fit_strict = pm.conformance_fitness(traces, model_edges_strict, start_acts, end_acts)
fit_loose = pm.conformance_fitness(traces, model_edges_loose, start_acts, end_acts)
fit_alpha = pm.conformance_fitness(traces, model_edges_alpha, start_acts, end_acts)
fit_ind = pm.conformance_fitness(traces, model_edges_inductive, start_acts, end_acts)
prec_strict = pm.conformance_precision(traces, model_edges_strict, act_freq_c)
prec_loose = pm.conformance_precision(traces, model_edges_loose, act_freq_c)
prec_alpha = pm.conformance_precision(traces, model_edges_alpha, act_freq_c)
prec_ind = pm.conformance_precision(traces, model_edges_inductive, act_freq_c)
gen_strict = pm.conformance_generalization(traces, model_edges_strict)
gen_loose = pm.conformance_generalization(traces, model_edges_loose)
gen_alpha = pm.conformance_generalization(traces, model_edges_alpha)
gen_ind = pm.conformance_generalization(traces, model_edges_inductive)
simp_strict = pm.conformance_simplicity(model_edges_strict, act_freq_c.keys())
simp_loose = pm.conformance_simplicity(model_edges_loose, act_freq_c.keys())
simp_alpha = pm.conformance_simplicity(model_edges_alpha, act_freq_c.keys())
simp_ind = pm.conformance_simplicity(model_edges_inductive, act_freq_c.keys())

metrics["conformance_strict_model"] = {
    "fitness": fit_strict["fitness"], "edge_fitness": fit_strict["edge_fitness"],
    "precision": prec_strict, "generalization": gen_strict, "simplicity": simp_strict,
    "top_deviations": fit_strict["top_deviations"],
    "n_model_edges": len(model_edges_strict),
}
metrics["conformance_loose_model"] = {
    "fitness": fit_loose["fitness"], "edge_fitness": fit_loose["edge_fitness"],
    "precision": prec_loose, "generalization": gen_loose, "simplicity": simp_loose,
    "top_deviations": fit_loose["top_deviations"],
    "n_model_edges": len(model_edges_loose),
}
metrics["conformance_alpha_model"] = {
    "fitness": fit_alpha["fitness"], "edge_fitness": fit_alpha["edge_fitness"],
    "precision": prec_alpha, "generalization": gen_alpha, "simplicity": simp_alpha,
    "top_deviations": fit_alpha["top_deviations"],
    "n_model_edges": len(model_edges_alpha),
}
metrics["conformance_inductive_model"] = {
    "fitness": fit_ind["fitness"], "edge_fitness": fit_ind["edge_fitness"],
    "precision": prec_ind, "generalization": gen_ind, "simplicity": simp_ind,
    "top_deviations": fit_ind["top_deviations"],
    "n_model_edges": len(model_edges_inductive),
}

# grafico comparativo das 4 metricas para os modelos de descoberta
comp_df = pd.DataFrame({
    "Métrica": ["Fitness", "Precision", "Generalization", "Simplicity"] * 4,
    "Valor": [fit_strict["fitness"], prec_strict, gen_strict, simp_strict,
              fit_alpha["fitness"], prec_alpha, gen_alpha, simp_alpha,
              fit_ind["fitness"], prec_ind, gen_ind, simp_ind,
              fit_loose["fitness"], prec_loose, gen_loose, simp_loose],
    "Modelo": ["DFG filtrado (Heuristic-like)"] * 4 + ["Alpha Miner"] * 4
               + ["Inductive Miner"] * 4 + ["DFG completo (bruto)"] * 4,
})
fig, ax = plt.subplots(figsize=(10, 5.5))
sns.barplot(data=comp_df, x="Métrica", y="Valor", hue="Modelo", ax=ax,
            palette=["#1b4965", "#7b2cbf", "#bc6c25", "#52796f"])
ax.set_ylim(0, 1.05)
ax.set_title("Métricas de conformidade por algoritmo de descoberta")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.35), ncol=2)
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/09_conformance_metrics.png", dpi=150)
plt.close()

# desvios mais frequentes (modelo filtrado, mais informativo p/ relatorio)
dev_df = pd.DataFrame(fit_strict["top_deviations"], columns=["transicao", "frequencia"])
dev_df["transicao"] = dev_df["transicao"].apply(lambda x: f"{x[0]} -> {x[1]}")
dev_df.to_csv(f"{DATA_DIR}/top_deviations.csv", index=False)

fig, ax = plt.subplots(figsize=(9, 5))
sns.barplot(data=dev_df, y="transicao", x="frequencia", ax=ax, color="#9d0208")
ax.set_title("Top 10 desvios (transições fora do modelo filtrado)")
ax.set_xlabel("Frequência (nº de ocorrências no log)")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/10_top_deviations.png", dpi=150)
plt.close()

# ===========================================================================
# 4. PERFORMANCE ANALYSIS
# ===========================================================================
perf = pm.performance_per_transition(traces, times)
perf.to_csv(f"{DATA_DIR}/performance_per_transition.csv", index=False)

top_bottlenecks = perf.head(10)
metrics["top_bottlenecks"] = top_bottlenecks.to_dict(orient="records")

fig, ax = plt.subplots(figsize=(9, 5.5))
labels = top_bottlenecks.apply(lambda r: f"{r['from']} → {r['to']}", axis=1)
sns.barplot(x=top_bottlenecks["mean_h"] / 24, y=labels, ax=ax, color="#e85d04")
ax.set_xlabel("Tempo médio de espera (dias)")
ax.set_title("Top 10 gargalos (maior tempo médio entre atividades consecutivas)")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/11_bottlenecks.png", dpi=150)
plt.close()

# tempo medio por atividade "de origem" (quanto tempo se espera depois dela)
act_wait = perf.groupby("from")["mean_h"].mean().sort_values(ascending=False)
fig, ax = plt.subplots(figsize=(8, 6))
(act_wait / 24).plot(kind="barh", ax=ax, color="#3a0ca3")
ax.set_xlabel("Tempo médio de espera após a atividade (dias)")
ax.invert_yaxis()
ax.set_title("Tempo médio de espera por atividade de origem")
plt.tight_layout()
plt.savefig(f"{FIG_DIR}/12_wait_by_activity.png", dpi=150)
plt.close()

# ===========================================================================
# 5. SALVAR METRICAS
# ===========================================================================
def default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    return str(o)

with open(f"{DATA_DIR}/metrics_summary.json", "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2, ensure_ascii=False, default=default)

print("=== RESUMO ===")
for k, v in metrics.items():
    if isinstance(v, (dict, list)):
        continue
    print(f"{k}: {v}")
print("\nFiguras e tabelas salvas em ../figures e ../data")
