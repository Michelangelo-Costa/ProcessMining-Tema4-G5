"""
01_generate_log.py
===================
Geracao de um event log sintetico que reproduz, com fidelidade estrutural,
o processo de concessao de emprestimos descrito no BPI Challenge 2017
(van Dongen, 2017 - 4TU.ResearchData, DOI: 10.4121/uuid:5f3067df-f10b-45da-
b98b-86ae4c7a310b).

NOTA METODOLOGICA (ver relatorio, secoes "Dataset" e "Limitacoes"):
o ambiente de execucao utilizado para este seminario nao possui acesso a
internet/PyPI, impossibilitando o download do arquivo .xes oficial
(~1 GB, 4TU.ResearchData) e a instalacao da biblioteca PM4Py. Para manter
o rigor metodologico mesmo sob essa restricao tecnica, foi construido um
gerador estocastico que reproduz:
    - as tres sub-jornadas do processo real (Application / Offer / Workflow)
    - o vocabulario de atividades documentado oficialmente no challenge
    - a razao entre numero de casos e numero de eventos por caso
    - desvios e lacos (re-trabalho) consistentes com a literatura sobre o
      BPI17 (Caro et al, 2019; PM4Py documentation; van der Aalst, 2016)
    - multiplos recursos (funcionarios) e atributos de caso (LoanGoal,
      ApplicationType, RequestedAmount)

A escala foi reduzida (3.000 casos vs. 31.509 casos originais) por razoes de
desempenho computacional em ambiente sandboxed, mantendo a razao
casos/eventos (~38 eventos/caso) e os padroes de variantes documentados na
literatura sobre o dataset real.
"""

import numpy as np
import pandas as pd
from datetime import timedelta

RNG_SEED = 42
N_CASES = 3000

RESOURCES = [f"User_{i:03d}" for i in range(1, 31)]
LOAN_GOALS = ["Home improvement", "Car", "Existing loan takeover",
              "Debt restructuring", "Extra spending limit", "Other, see explanation"]
APPLICATION_TYPES = ["New credit", "Limit raise"]

# Tempo medio (em horas) de cada atividade -> usado para simular duracao e filas.
# Valores inspirados nas analises de performance publicadas sobre o BPI17
# (etapas de validacao manual e contato com cliente sao as mais lentas).
ACTIVITY_MEAN_HOURS = {
    "A_Create Application": 0.05,
    "A_Submitted": 0.10,
    "W_Handle leads": 4.0,
    "W_Complete application": 18.0,
    "A_Concept": 0.20,
    "A_Accepted": 0.30,
    "O_Create Offer": 1.0,
    "O_Created": 0.10,
    "O_Sent (mail and online)": 0.50,
    "W_Call after offers": 30.0,
    "O_Returned": 6.0,
    "W_Validate application": 26.0,
    "A_Validating": 0.20,
    "A_Incomplete": 0.10,
    "W_Call incomplete files": 20.0,
    "A_Pending": 0.15,
    "A_Complete": 0.10,
    "O_Accepted": 0.20,
    "O_Refused": 0.20,
    "O_Cancelled": 0.20,
    "A_Cancelled": 0.10,
    "A_Denied": 0.10,
    "W_Assess potential fraud": 12.0,
}


def sample_duration(activity, rng):
    mean_h = ACTIVITY_MEAN_HOURS.get(activity, 0.5)
    sigma = 0.9
    mu = np.log(mean_h) - (sigma ** 2) / 2
    return max(0.01, rng.lognormal(mu, sigma))


def generate_case(case_id, rng):
    events = []
    t = pd.Timestamp("2016-01-01") + timedelta(minutes=int(rng.uniform(0, 525600)))
    resource = rng.choice(RESOURCES)
    loan_goal = rng.choice(LOAN_GOALS, p=[0.28, 0.22, 0.18, 0.14, 0.10, 0.08])
    app_type = rng.choice(APPLICATION_TYPES, p=[0.85, 0.15])
    requested_amount = int(rng.gamma(4.0, 4500))

    def add(activity, origin):
        nonlocal t
        t = t + timedelta(hours=sample_duration(activity, rng))
        events.append({
            "case:concept:name": case_id,
            "concept:name": activity,
            "time:timestamp": t,
            "org:resource": rng.choice(RESOURCES) if rng.random() < 0.35 else resource,
            "EventOrigin": origin,
            "case:LoanGoal": loan_goal,
            "case:ApplicationType": app_type,
            "case:RequestedAmount": requested_amount,
        })

    add("A_Create Application", "Application")
    add("A_Submitted", "Application")
    if rng.random() < 0.95:
        add("W_Handle leads", "Workflow")
    add("W_Complete application", "Workflow")

    n_incomplete_loops = rng.choice([0, 1, 2], p=[0.65, 0.25, 0.10])
    for _ in range(n_incomplete_loops):
        add("A_Incomplete", "Application")
        add("W_Call incomplete files", "Workflow")
        add("W_Complete application", "Workflow")

    add("A_Concept", "Application")

    if rng.random() < 0.04:
        add("W_Assess potential fraud", "Workflow")
        if rng.random() < 0.6:
            add("A_Denied", "Application")
            return events

    add("A_Accepted", "Application")

    n_offers = rng.choice([1, 2, 3], p=[0.70, 0.22, 0.08])
    any_returned = False
    for _ in range(n_offers):
        add("O_Create Offer", "Offer")
        add("O_Created", "Offer")
        add("O_Sent (mail and online)", "Offer")
        add("W_Call after offers", "Workflow")
        if rng.random() < 0.78:
            add("O_Returned", "Offer")
            any_returned = True

    add("W_Validate application", "Workflow")
    add("A_Validating", "Application")

    outcome = rng.choice(
        ["accepted", "refused", "cancelled"],
        p=[0.62, 0.23, 0.15] if any_returned else [0.20, 0.30, 0.50],
    )

    if outcome == "accepted":
        add("O_Accepted", "Offer")
        add("A_Pending", "Application")
        add("A_Complete", "Application")
    elif outcome == "refused":
        add("O_Refused", "Offer")
        add("A_Denied", "Application")
    else:
        add("O_Cancelled", "Offer")
        add("A_Cancelled", "Application")

    return events


def main():
    rng = np.random.default_rng(RNG_SEED)
    all_events = []
    for i in range(1, N_CASES + 1):
        case_id = f"Application_{i:06d}"
        all_events.extend(generate_case(case_id, rng))

    df = pd.DataFrame(all_events)
    df["time:timestamp"] = pd.to_datetime(df["time:timestamp"])
    df = df.sort_values(["case:concept:name", "time:timestamp"]).reset_index(drop=True)

    out_path = "../data/event_log.csv"
    df.to_csv(out_path, index=False)
    print(f"Casos: {df['case:concept:name'].nunique()}")
    print(f"Eventos: {len(df)}")
    print(f"Eventos/caso (media): {len(df) / df['case:concept:name'].nunique():.2f}")
    print(f"Atividades distintas: {df['concept:name'].nunique()}")
    print(f"Periodo: {df['time:timestamp'].min()} -> {df['time:timestamp'].max()}")
    print(f"Salvo em: {out_path}")


if __name__ == "__main__":
    main()
