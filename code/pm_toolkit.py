"""
pm_toolkit.py
=============
Biblioteca própria de Process Mining (substitui o PM4Py, indisponível por
falta de acesso à internet no ambiente de execução — ver Secao 9 do
relatorio). Implementa, a partir de pandas/numpy/graphviz puros:

  - Directly-Follows Graph (DFG)
  - Alpha Miner (algoritmo classico de descoberta, van der Aalst et al., 2004)
  - Inductive Miner simplificado (cortes sequencia/XOR/paralelo/loop sobre o DFG,
    inspirado em Leemans, Fahland & van der Aalst, 2013)
  - Conformance checking por replay de tokens (fitness), precisao por arcos
    de escape (escaping edges), generalizacao e simplicidade
  - Analise de performance (tempos entre atividades, gargalos)
  - Analise de variantes

Todas as funcoes recebem um DataFrame no formato XES "achatado":
colunas obrigatorias: case:concept:name, concept:name, time:timestamp
"""

import numpy as np
import pandas as pd
from collections import defaultdict, Counter
from itertools import combinations

START = "▶START"
END = "■END"


# ---------------------------------------------------------------------------
# 1. CARGA E PREPARACAO
# ---------------------------------------------------------------------------

def load_log(path):
    df = pd.read_csv(path, parse_dates=["time:timestamp"])
    return df


def get_traces(df):
    """Retorna dict {case_id: [lista ordenada de atividades]} e
    dict {case_id: [lista ordenada de timestamps]}."""
    traces, times = {}, {}
    for case_id, g in df.groupby("case:concept:name", sort=False):
        g = g.sort_values("time:timestamp")
        traces[case_id] = list(g["concept:name"])
        times[case_id] = list(g["time:timestamp"])
    return traces, times


# ---------------------------------------------------------------------------
# 2. DIRECTLY-FOLLOWS GRAPH
# ---------------------------------------------------------------------------

def build_dfg(traces):
    """Conta, para cada par (a,b), quantas vezes b segue a diretamente
    dentro do mesmo caso. Retorna Counter{(a,b): freq}, Counter de
    atividades iniciais e finais."""
    dfg = Counter()
    start_acts = Counter()
    end_acts = Counter()
    act_freq = Counter()
    for trace in traces.values():
        if not trace:
            continue
        start_acts[trace[0]] += 1
        end_acts[trace[-1]] += 1
        for a in trace:
            act_freq[a] += 1
        for a, b in zip(trace, trace[1:]):
            dfg[(a, b)] += 1
    return dfg, start_acts, end_acts, act_freq


# ---------------------------------------------------------------------------
# 3. ALPHA MINER
# ---------------------------------------------------------------------------

class AlphaMinerResult:
    def __init__(self, places, transitions, flow_in, flow_out, start_acts, end_acts):
        self.places = places              # lista de nomes de "places"
        self.transitions = transitions    # lista de atividades
        self.flow_in = flow_in            # dict place -> set(transitions) [entrada do place]
        self.flow_out = flow_out          # dict place -> set(transitions) [saida do place]
        self.start_acts = start_acts
        self.end_acts = end_acts


def alpha_miner(traces):
    """Implementacao do algoritmo Alpha classico (van der Aalst, Weijters &
    Maruster, 2004), em sua forma simplificada (sem tratamento de loops de
    tamanho 1/2 nem atividades duplicadas, conforme limitacoes documentadas
    do proprio algoritmo).

    Passos do algoritmo original:
      1. T_L = conjunto de atividades que aparecem no log
      2. T_I = atividades iniciais; T_O = atividades finais
      3. Relacoes de footprint: causalidade (>), exclusividade (#), paralelismo (||)
      4. X_L = pares (A,B) de conjuntos de atividades onde toda a em A causa
         toda b em B, A e' internamente exclusivo, B e' internamente exclusivo
      5. Y_L = pares maximais de X_L (nao dominados por outro par)
      6. P_L = um place para cada par em Y_L + place inicial/final
      7. Constroi a rede de Petri (T_L, P_L, F_L)
    """
    dfg, start_acts, end_acts, act_freq = build_dfg(traces)
    activities = sorted(act_freq.keys())

    # Footprint: relacao de causalidade direta a>b
    follows = set(dfg.keys())

    def causal(a, b):
        return (a, b) in follows and (b, a) not in follows

    def parallel(a, b):
        return (a, b) in follows and (b, a) in follows

    def exclusive(a, b):
        return (a, b) not in follows and (b, a) not in follows

    # Conjuntos de atividades mutuamente exclusivas entre si (para A e B)
    def internally_exclusive(group):
        return all(exclusive(x, y) for x, y in combinations(group, 2)) if len(group) > 1 else True

    def causal_set(A, B):
        return all(causal(a, b) for a in A for b in B)

    # Gera candidatos (A,B) a partir de subconjuntos nao vazios (limitado a
    # tamanho pratico para custo computacional)
    from itertools import chain

    def subsets(seq, max_size=3):
        return list(chain.from_iterable(combinations(seq, r) for r in range(1, max_size + 1)))

    candidates = subsets(activities, max_size=3)
    XL = []
    for A in candidates:
        for B in candidates:
            if internally_exclusive(A) and internally_exclusive(B) and causal_set(A, B):
                XL.append((frozenset(A), frozenset(B)))

    # Y_L: pares maximais (nao subconjunto proprio de outro par em ambas as componentes)
    YL = []
    for (A, B) in XL:
        dominated = False
        for (A2, B2) in XL:
            if (A, B) != (A2, B2) and A.issubset(A2) and B.issubset(B2) and (A != A2 or B != B2):
                dominated = True
                break
        if not dominated:
            YL.append((A, B))
    # remove duplicatas
    YL = list(set(YL))

    places = [f"p_{i}" for i in range(len(YL))]
    flow_in = {}   # place -> activities that flow INTO place (i.e. A)
    flow_out = {}  # place -> activities that flow OUT of place (i.e. B)
    for p, (A, B) in zip(places, YL):
        flow_in[p] = set(A)
        flow_out[p] = set(B)

    return AlphaMinerResult(places, activities, flow_in, flow_out, start_acts, end_acts)


# ---------------------------------------------------------------------------
# 4. INDUCTIVE MINER SIMPLIFICADO (process tree via cortes no DFG)
# ---------------------------------------------------------------------------

class PTNode:
    def __init__(self, op=None, children=None, leaf=None):
        self.op = op            # '->' sequencia, 'x' XOR, '+' paralelo, '*' loop, None=leaf
        self.children = children or []
        self.leaf = leaf

    def __repr__(self):
        if self.leaf is not None:
            return self.leaf
        sym = {"->": "→", "x": "×", "+": "∧", "*": "↻"}[self.op]
        return f"{sym}(" + ", ".join(repr(c) for c in self.children) + ")"


def inductive_miner(traces, max_depth=6):
    """Versao didatica e simplificada do Inductive Miner (Leemans, Fahland &
    van der Aalst, 2013). Constroi recursivamente uma process tree a partir
    do DFG, procurando, em ordem de prioridade, cortes:
        sequencia -> XOR -> paralelo -> loop -> base (folha/flower)
    Não garante todas as propriedades formais do IM original (p.ex. divide-
    and-conquer sobre componentes fortemente conexas), mas captura a lógica
    central do algoritmo para fins didáticos."""

    def mine(sub_traces, depth):
        activities = sorted({a for t in sub_traces for a in t})
        if len(activities) == 0:
            return PTNode(leaf="tau")
        if len(activities) == 1:
            return PTNode(leaf=activities[0])
        if depth >= max_depth:
            return PTNode(op="x", children=[PTNode(leaf=a) for a in activities])

        dfg, starts, ends, freq = build_dfg({i: t for i, t in enumerate(sub_traces)})

        # --- tentativa de corte de SEQUENCIA ---
        # particiona atividades em grupos ordenados onde nao ha aresta de volta
        cut = try_sequence_cut(activities, dfg)
        if cut:
            children = []
            for group in cut:
                filtered = [[a for a in t if a in group] for t in sub_traces]
                filtered = [t for t in filtered if t]
                children.append(mine(filtered, depth + 1))
            return PTNode(op="->", children=children)

        # --- tentativa de corte XOR (exclusivo) ---
        cut = try_xor_cut(activities, sub_traces)
        if cut:
            children = []
            for group in cut:
                filtered = [t for t in sub_traces if any(a in group for a in t)]
                filtered = [[a for a in t if a in group] for t in filtered]
                children.append(mine(filtered, depth + 1))
            return PTNode(op="x", children=children)

        # --- tentativa de corte PARALELO ---
        cut = try_parallel_cut(activities, dfg)
        if cut:
            children = []
            for group in cut:
                filtered = [[a for a in t if a in group] for t in sub_traces]
                children.append(mine(filtered, depth + 1))
            return PTNode(op="+", children=children)

        # fallback: "flower model" (XOR de todas as atividades, sem ordem) -
        # representa explicitamente a incapacidade de estruturar aquele trecho
        return PTNode(op="*", children=[PTNode(op="x", children=[PTNode(leaf=a) for a in activities]),
                                         PTNode(leaf="tau")])

    root = mine(list(traces.values()), 0)
    return root


def try_sequence_cut(activities, dfg):
    """Heurística: ordena atividades pela primeira ocorrência média e separa
    em blocos quando não há nenhuma aresta do bloco posterior para o bloco
    anterior (corte de sequência)."""
    # Ordena por grau de "profundidade" topológica aproximada usando contagem
    # de predecessores diretos
    preds = defaultdict(set)
    for (a, b) in dfg:
        preds[b].add(a)
    order = sorted(activities, key=lambda a: len(preds[a]))
    # tenta dividir em 2 blocos no melhor ponto de corte
    best_cut = None
    for i in range(1, len(order)):
        first, second = set(order[:i]), set(order[i:])
        backward = any((b, a) in dfg for a in first for b in second)
        if not backward:
            best_cut = [first, second]
            break
    return best_cut


def try_xor_cut(activities, sub_traces):
    """Particiona atividades em grupos que nunca co-ocorrem no mesmo trace
    (escolha exclusiva)."""
    co_occurs = defaultdict(set)
    for t in sub_traces:
        present = set(t)
        for a in present:
            co_occurs[a] |= present

    remaining = set(activities)
    groups = []
    while remaining:
        a = next(iter(remaining))
        comp = {a}
        frontier = [a]
        while frontier:
            cur = frontier.pop()
            for b in remaining:
                if b in co_occurs[cur] and b not in comp:
                    comp.add(b)
                    frontier.append(b)
        groups.append(comp)
        remaining -= comp
    return groups if len(groups) > 1 else None


def try_parallel_cut(activities, dfg):
    """Particiona atividades em grupos onde toda atividade de um grupo tem
    aresta bidirecional (a->b e b->a) com toda atividade de outro grupo."""
    n = len(activities)
    if n < 2:
        return None
    idx = {a: i for i, a in enumerate(activities)}
    adj = np.zeros((n, n), dtype=bool)
    for (a, b) in dfg:
        if (b, a) in dfg:
            adj[idx[a], idx[b]] = True
            adj[idx[b], idx[a]] = True
    # componentes onde todas as arestas cruzadas existem (busca gulosa simples)
    visited = set()
    groups = []
    for a in activities:
        if a in visited:
            continue
        group = {a}
        visited.add(a)
        groups.append(group)
    # agrupa por pares totalmente interligados via union-find
    pairs_ok = []
    for a, b in combinations(activities, 2):
        if adj[idx[a], idx[b]]:
            pairs_ok.append((a, b))
    if not pairs_ok:
        return None
    # union-find
    parent = {a: a for a in activities}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for a, b in pairs_ok:
        union(a, b)
    comp_map = defaultdict(set)
    for a in activities:
        comp_map[find(a)].add(a)
    result = list(comp_map.values())
    return result if len(result) > 1 else None


def process_tree_leaves_in_order(node):
    """Retorna lista de folhas (sem tau) na ordem aproximada do tree, para
    fins de impressao/relatorio."""
    if node.leaf is not None:
        return [] if node.leaf == "tau" else [node.leaf]
    out = []
    for c in node.children:
        out.extend(process_tree_leaves_in_order(c))
    return out


def process_tree_semantics(node):
    """Calcula recursivamente (first_set, last_set, edges) para um nodo da
    process tree, segundo a semantica de operadores de van der Aalst (2016,
    cap. 4): sequencia (->), escolha exclusiva (x), paralelismo (+) e laco (*).
    'edges' e' o conjunto de pares (a,b) de atividades que o modelo permite
    como transicao direta dentro da subarvore.

    Esta funcao e' usada para derivar um modelo de conformidade a partir do
    Inductive Miner que e' estruturalmente DIFERENTE do DFG do log (ao
    contrario de uma comparacao trivial), permitindo avaliar genuinamente o
    classico trade-off fitness x precision: um modelo "flor" (loop de XOR
    de todas as atividades, tipico de fallback do Inductive Miner sobre
    trechos pouco estruturados) tende a fitness alto e precision baixa,
    pois permite combinacoes nunca observadas no log real.
    """
    if node.leaf is not None:
        if node.leaf == "tau":
            return set(), set(), set()
        return {node.leaf}, {node.leaf}, set()

    if node.op == "->":
        edges = set()
        first, last = None, set()
        prev_last = None
        for c in node.children:
            cf, cl, ce = process_tree_semantics(c)
            edges |= ce
            if prev_last:
                for a in prev_last:
                    for b in cf:
                        edges.add((a, b))
            if cf:
                if first is None:
                    first = set(cf)
                prev_last = cl
            if cl:
                last = cl if cf or cl else last
        if first is None:
            first = set()
        return first, last, edges

    if node.op == "x":
        first, last, edges = set(), set(), set()
        for c in node.children:
            cf, cl, ce = process_tree_semantics(c)
            first |= cf
            last |= cl
            edges |= ce
        return first, last, edges

    if node.op == "+":
        first, last, edges = set(), set(), set()
        child_acts = []
        for c in node.children:
            cf, cl, ce = process_tree_semantics(c)
            first |= cf
            last |= cl
            edges |= ce
            child_acts.append(cf | cl)
        for i in range(len(child_acts)):
            for j in range(len(child_acts)):
                if i == j:
                    continue
                for a in child_acts[i]:
                    for b in child_acts[j]:
                        edges.add((a, b))
        return first, last, edges

    if node.op == "*":
        # children[0] = corpo do laco, children[1] = tau (saida)
        body = node.children[0]
        bf, bl, be = process_tree_semantics(body)
        edges = set(be)
        for a in bl:
            for b in bf:
                edges.add((a, b))  # arco de retorno do laco
        return bf, bl, edges

    raise ValueError(f"Operador desconhecido: {node.op}")


# ---------------------------------------------------------------------------
# 5. CONFORMANCE CHECKING (a partir do DFG / process tree)
# ---------------------------------------------------------------------------

def dfg_based_model_edges(dfg, freq_threshold_ratio=0.0):
    """Filtra o DFG, opcionalmente removendo arestas raras (proxy para
    'modelo de referencia' usado no conformance checking)."""
    if not dfg:
        return set()
    max_f = max(dfg.values())
    return {pair for pair, f in dfg.items() if f >= freq_threshold_ratio * max_f}


def conformance_fitness(traces, model_edges, start_acts, end_acts):
    """Fitness baseado em replay simplificado: para cada trace, conta quantas
    transicoes (a,b) consecutivas existem no modelo (model_edges) e quantas
    nao existem (desvios "moves no modelo"/log nao sincronizados). Tambem
    pondera se a atividade inicial/final do trace pertence aos conjuntos de
    inicio/fim aceitos pelo modelo.

    fitness_trace = (#transicoes_validas + bonus_inicio_fim) / (#transicoes_totais + 2)
    fitness_log = media ponderada por frequencia das variantes
    """
    total_valid, total_edges = 0, 0
    total_start_ok, total_end_ok, n_traces = 0, 0, 0
    deviation_counter = Counter()

    for trace in traces.values():
        n_traces += 1
        if trace[0] in start_acts:
            total_start_ok += 1
        if trace[-1] in end_acts:
            total_end_ok += 1
        for a, b in zip(trace, trace[1:]):
            total_edges += 1
            if (a, b) in model_edges:
                total_valid += 1
            else:
                deviation_counter[(a, b)] += 1

    edge_fitness = total_valid / total_edges if total_edges else 1.0
    start_fitness = total_start_ok / n_traces if n_traces else 1.0
    end_fitness = total_end_ok / n_traces if n_traces else 1.0
    # combinacao ponderada (pesos refletem maior peso ao fluxo interno)
    fitness = 0.8 * edge_fitness + 0.1 * start_fitness + 0.1 * end_fitness
    return {
        "fitness": fitness,
        "edge_fitness": edge_fitness,
        "start_fitness": start_fitness,
        "end_fitness": end_fitness,
        "top_deviations": deviation_counter.most_common(10),
    }


def conformance_precision(traces, model_edges, act_freq):
    """Precisao aproximada via 'escaping edges': para cada atividade que
    aparece como origem em alguma aresta do modelo, mede a fracao de
    transicoes observadas no log que realmente ocorrem (denominador) versus
    o total de transicoes permitidas pelo modelo a partir daquela atividade
    (numerador seria o quao "enxuto" o modelo e' em relacao ao que o log usa).

    Aqui aplicamos uma aproximacao pratica amplamente usada em estudos
    didaticos: precision ~= (# arcos do modelo realmente exercitados pelo log)
                              / (# arcos totais do modelo)
    Um modelo que permite muitas transicoes nunca observadas (under-fitting)
    tera precisao baixa.
    """
    observed_edges = set()
    for trace in traces.values():
        for a, b in zip(trace, trace[1:]):
            observed_edges.add((a, b))
    if not model_edges:
        return 0.0
    exercised = observed_edges & model_edges
    precision = len(exercised) / len(model_edges)
    return precision


def conformance_generalization(traces, model_edges):
    """Generalizacao aproximada: 1 - fracao de arcos do modelo que foram
    exercitados por poucas variantes (proxy de overfitting ao log de treino).
    Usamos a razao entre arcos vistos em >=2 casos distintos e o total de
    arcos do modelo - um modelo que so generaliza arcos vistos 1x tende a
    superajustar."""
    edge_case_count = defaultdict(set)
    for case_id, trace in traces.items():
        for a, b in zip(trace, trace[1:]):
            edge_case_count[(a, b)].add(case_id)
    if not model_edges:
        return 0.0
    robust = sum(1 for e in model_edges if len(edge_case_count.get(e, [])) >= 2)
    return robust / len(model_edges)


def conformance_simplicity(model_edges, activities):
    """Simplicidade: métrica inversamente proporcional ao tamanho do modelo
    (numero de nodes + arestas), normalizada por um teto de referencia."""
    n_nodes = len(activities)
    n_edges = len(model_edges)
    size = n_nodes + n_edges
    # normalizacao heuristica: quanto menor o tamanho relativo ao numero de
    # atividades ao quadrado (grafo completo), mais simples o modelo
    max_possible = n_nodes + n_nodes ** 2
    simplicity = 1 - (size / max_possible) if max_possible else 0.0
    return max(0.0, min(1.0, simplicity))


# ---------------------------------------------------------------------------
# 6. PERFORMANCE ANALYSIS
# ---------------------------------------------------------------------------

def performance_per_transition(traces, times):
    """Para cada par (a,b) consecutivo, calcula estatisticas de tempo de
    espera (em horas) entre o fim de a e o inicio de b."""
    deltas = defaultdict(list)
    for case_id, trace in traces.items():
        ts = times[case_id]
        for i in range(len(trace) - 1):
            a, b = trace[i], trace[i + 1]
            dt_hours = (ts[i + 1] - ts[i]).total_seconds() / 3600.0
            deltas[(a, b)].append(dt_hours)
    rows = []
    for (a, b), vals in deltas.items():
        vals = np.array(vals)
        rows.append({
            "from": a, "to": b, "count": len(vals),
            "mean_h": vals.mean(), "median_h": np.median(vals),
            "p90_h": np.percentile(vals, 90), "max_h": vals.max(),
        })
    return pd.DataFrame(rows).sort_values("mean_h", ascending=False)


def case_durations(traces, times):
    rows = []
    for case_id, trace in traces.items():
        ts = times[case_id]
        dur_days = (ts[-1] - ts[0]).total_seconds() / 86400.0
        rows.append({"case_id": case_id, "n_events": len(trace), "duration_days": dur_days})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 7. VARIANTES
# ---------------------------------------------------------------------------

def variant_analysis(traces):
    counter = Counter(tuple(t) for t in traces.values())
    total = sum(counter.values())
    rows = []
    for variant, freq in counter.most_common():
        rows.append({
            "variant": " -> ".join(variant),
            "n_activities": len(variant),
            "frequency": freq,
            "pct": 100 * freq / total,
        })
    return pd.DataFrame(rows)
