"""
generate_graph_figures.py
Gera figuras 06, 07 e 08 usando networkx + matplotlib (sem o executável dot).
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx

import pm_toolkit as pm

FIG_DIR = "../report/figures"
DATA_DIR = "../data"
os.makedirs(FIG_DIR, exist_ok=True)

# ── Carrega log ──────────────────────────────────────────────────────────────
df = pm.load_log(f"{DATA_DIR}/event_log.csv")
traces, times = pm.get_traces(df)
dfg, start_acts, end_acts, act_freq = pm.build_dfg(traces)

# ── Helpers ──────────────────────────────────────────────────────────────────
def short(name):
    """Abrevia nomes longos para caber nos nós."""
    return name.replace("W_", "W·").replace("A_", "A·").replace("O_", "O·")

def draw_dfg(dfg, act_freq, start_acts, end_acts, path,
             freq_threshold_ratio=0.0, title=""):
    max_f = max(dfg.values())
    shown = set()
    edges = {}
    for (a, b), f in dfg.items():
        if f >= freq_threshold_ratio * max_f:
            shown.add(a); shown.add(b)
            edges[(a, b)] = f

    G = nx.DiGraph()
    G.add_nodes_from(["▶ START", "■ END"])
    G.add_nodes_from(shown)
    for a, f in start_acts.items():
        if a in shown:
            G.add_edge("▶ START", a, weight=f)
    for a, f in end_acts.items():
        if a in shown:
            G.add_edge(a, "■ END", weight=f)
    for (a, b), f in edges.items():
        G.add_edge(a, b, weight=f)

    pos = nx.spring_layout(G, seed=42, k=2.5, iterations=80)

    # tamanho proporcional ao número de nós
    n = len(G.nodes)
    fig, ax = plt.subplots(figsize=(max(14, n * 0.7), max(10, n * 0.5)))
    ax.set_axis_off()
    if title:
        ax.set_title(title, fontsize=11, pad=8)

    # nós de atividade
    act_nodes = [v for v in G.nodes if v not in ("▶ START", "■ END")]
    nx.draw_networkx_nodes(G, pos, nodelist=act_nodes, ax=ax,
                           node_color="#cde7f0", node_size=2200,
                           node_shape="s")
    labels_act = {v: short(v) for v in act_nodes}
    nx.draw_networkx_labels(G, pos, labels=labels_act, ax=ax,
                            font_size=7, font_weight="bold")

    # nós START / END
    nx.draw_networkx_nodes(G, pos, nodelist=["▶ START"], ax=ax,
                           node_color="#90be6d", node_size=1200)
    nx.draw_networkx_nodes(G, pos, nodelist=["■ END"], ax=ax,
                           node_color="#f3722c", node_size=1200)
    nx.draw_networkx_labels(G, pos, labels={"▶ START": "START", "■ END": "END"},
                            ax=ax, font_size=8, font_color="white", font_weight="bold")

    # arestas com espessura proporcional
    edge_weights = [G[u][v]["weight"] for u, v in G.edges()]
    max_w = max(edge_weights) if edge_weights else 1
    widths = [0.5 + 3.5 * w / max_w for w in edge_weights]
    nx.draw_networkx_edges(G, pos, ax=ax, width=widths,
                           edge_color="#555555", arrows=True,
                           arrowsize=15, arrowstyle="-|>",
                           connectionstyle="arc3,rad=0.05",
                           node_size=2200)

    plt.tight_layout()
    plt.savefig(f"{path}.png", dpi=180, bbox_inches="tight")
    plt.close()
    print(f"  Salvo: {path}.png")

def draw_alpha_net(alpha_res, path):
    G = nx.DiGraph()
    for t in alpha_res.transitions:
        G.add_node(t, kind="transition")
    for p in alpha_res.places:
        G.add_node(p, kind="place")
        for a in alpha_res.flow_in[p]:
            G.add_edge(a, p)
        for b in alpha_res.flow_out[p]:
            G.add_edge(p, b)

    pos = nx.spring_layout(G, seed=7, k=2.2, iterations=100)

    n = len(alpha_res.transitions) + len(alpha_res.places)
    fig, ax = plt.subplots(figsize=(max(16, n * 0.6), max(12, n * 0.45)))
    ax.set_axis_off()
    ax.set_title("Rede de Petri — Alpha Miner", fontsize=11, pad=8)

    trans_nodes = list(alpha_res.transitions)
    place_nodes = list(alpha_res.places)

    nx.draw_networkx_nodes(G, pos, nodelist=trans_nodes, ax=ax,
                           node_color="#ffd6a5", node_size=2000, node_shape="s")
    nx.draw_networkx_nodes(G, pos, nodelist=place_nodes, ax=ax,
                           node_color="#caffbf", node_size=600, node_shape="o")
    trans_labels = {t: short(t) for t in trans_nodes}
    nx.draw_networkx_labels(G, pos, labels=trans_labels, ax=ax,
                            font_size=7, font_weight="bold")

    nx.draw_networkx_edges(G, pos, ax=ax, width=1.2,
                           edge_color="#444444", arrows=True,
                           arrowsize=14, arrowstyle="-|>",
                           connectionstyle="arc3,rad=0.04",
                           node_size=2000)

    leg = [mpatches.Patch(color="#ffd6a5", label="Transição (atividade)"),
           mpatches.Patch(color="#caffbf", label="Place (condição)")]
    ax.legend(handles=leg, loc="upper right", fontsize=8)

    plt.tight_layout()
    plt.savefig(f"{path}.png", dpi=180, bbox_inches="tight")
    plt.close()
    print(f"  Salvo: {path}.png")

# ── Gera figuras ─────────────────────────────────────────────────────────────
print("Gerando 06_dfg_full...")
draw_dfg(dfg, act_freq, start_acts, end_acts,
         f"{FIG_DIR}/06_dfg_full", 0.0, "DFG Completo")

print("Gerando 07_dfg_filtered_heuristic...")
draw_dfg(dfg, act_freq, start_acts, end_acts,
         f"{FIG_DIR}/07_dfg_filtered_heuristic", 0.10, "DFG Filtrado (limiar 10%)")

print("Gerando 08_alpha_miner_net...")
alpha_res = pm.alpha_miner(traces)
draw_alpha_net(alpha_res, f"{FIG_DIR}/08_alpha_miner_net")

print("\nPronto! Figuras 06, 07, 08 geradas em", FIG_DIR)
