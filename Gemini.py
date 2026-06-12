import requests
import pandas as pd
import re
import time

print("Script iniciou")

# =========================================================
# API KEY
# =========================================================
API_KEY = "AQ.Ab8RN6Ikb6e8n1fFOExvEdXfM1D6gwGBi7YV0d_VB3Q8v4mbFQ"

# =========================================================
# ENDPOINT GEMINI
# =========================================================
url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"

headers = {
    "Content-Type": "application/json",
    "X-goog-api-key": API_KEY
}

# =========================================================
# LER CSV
# =========================================================
print("Lendo CSV...")

df = pd.read_csv("input.csv")

print("CSV carregado")
print("Linhas originais:", len(df))

# =========================================================
# JOGADORES ALVO
# =========================================================
jogadores_alvo = [
    "boaster",
    "less",
    "aspas",
    "saadhak",
    "cryocells",
    "asuna",
    "yay",
    "jinggg",
    "forsak3n",
    "nats",
    "kingg",
    "sacy",
    "mazino",
    "valyn",
    "jawgemo",
    "boo",
    "monyet",
    "mwzera",
    "derke",
    "tuyz"
]

# =========================================================
# LIMPAR NOME DOS PLAYERS
# =========================================================
df["player_clean"] = (
    df["player"]
    .astype(str)
    .apply(lambda x: re.sub(r"<.*?>", "", x))
    .str.lower()
    .str.strip()
)

# =========================================================
# FILTRAR PLAYERS
# =========================================================
df = df[df["player_clean"].isin(jogadores_alvo)]

print("Jogadores filtrados:", len(df))

print("Jogadores encontrados:")
print(df["player_clean"].unique())

# =========================================================
# ORDENAR POR DATA
# =========================================================
meses = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12
}

df["MesNumero"] = df["Mês"].str.lower().map(meses)

df["DataCompleta"] = pd.to_datetime(
    dict(
        year=df["Ano"],
        month=df["MesNumero"],
        day=df["Dia"]
    ),
    errors="coerce"
)

df = df.sort_values(
    by="DataCompleta",
    ascending=False
)

# =========================================================
# CONFIGURAÇÕES
# =========================================================
MAX_RETRIES = 5

DELAY_ENTRE_JOGADORES = 8

DELAY_RATE_LIMIT = 65

resultados = []

# =========================================================
# LISTA FINAL DE PLAYERS
# =========================================================
players_unicos = df["player_clean"].unique()

print("Total players únicos:", len(players_unicos))

# =========================================================
# LOOP PRINCIPAL
# =========================================================
for player in players_unicos:

    print(f"\nProcessando jogador: {player}")

    # =====================================================
    # DADOS DO JOGADOR
    # =====================================================
    dados_jogador = (
        df[df["player_clean"] == player]
        .sort_values("DataCompleta", ascending=False)
        .head(15)
    )

    # =====================================================
    # MONTAR TEXTO
    # =====================================================
    linhas_texto = []

    for _, jogo in dados_jogador.iterrows():

        linha = (
            f"Data: {jogo['Dia']}/{jogo['MesNumero']}/{jogo['Ano']} | "
            f"Mapa: {jogo['map_name']} | "
            f"Agente: {jogo['agent']} | "
            f"ACS: {jogo['ACS']} | "
            f"ADR: {jogo['ADR']} | "
            f"Kills: {jogo['Kills']} | "
            f"Deaths: {jogo['Deaths']} | "
            f"Assists: {jogo['Assists']} | "
            f"KAST: {jogo['KAST']} | "
            f"Rating: {jogo['rating']}"
        )

        linhas_texto.append(linha)

    texto = "\n".join(linhas_texto)

    # =====================================================
    # PROMPT
    # =====================================================
    prompt = f"""
Você é um analista profissional de performance de Valorant.

Analise APENAS os dados abaixo:

{texto}

Retorne EXATAMENTE neste formato:

Resumo:
<2 frases curtas e analíticas>

Pontos Fortes:
- <insight curto>
- <insight curto>
- <insight curto>

Pontos Fracos:
- <insight curto>
- <insight curto>
- <insight curto>

Regras IMPORTANTES:
- Escreva TUDO em português do Brasil
- Seja direto e analítico
- Não invente informações
- Use apenas os dados fornecidos
- Cite contexto de mapa, agente ou estatística
- Evite frases genéricas
- Máximo de 12 palavras por bullet
- Foque em padrões de performance
- Considere ACS, ADR, KAST, kills e deaths
- Identifique tendências reais
- Detecte inconsistência ou estabilidade
- Não use markdown
- Não use negrito
- Não escreva introduções
"""

    body = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ]
    }

    resultado = "Erro desconhecido"

    # =====================================================
    # RETRY LOOP
    # =====================================================
    for tentativa in range(MAX_RETRIES):

        try:

            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=45
            )

            status = response.status_code

            print("Status:", status)

            # =================================================
            # SUCESSO
            # =================================================
            if status == 200:

                resposta_json = response.json()

                resultado = (
                    resposta_json["candidates"][0]
                    ["content"]["parts"][0]["text"]
                )

                print("Análise gerada")

                break

            # =================================================
            # RATE LIMIT
            # =================================================
            elif status == 429:

                print("Limite da API atingido")
                print(f"Esperando {DELAY_RATE_LIMIT} segundos...")

                time.sleep(DELAY_RATE_LIMIT)

            # =================================================
            # SERVIDOR SOBRECARREGADO
            # =================================================
            elif status == 503:

                print("API sobrecarregada")
                print("Tentando novamente em 10 segundos")

                time.sleep(10)

            # =================================================
            # OUTROS ERROS
            # =================================================
            else:

                print("Erro API:")
                print(response.text)

                resultado = f"Erro API {status}"

                break

        # =====================================================
        # TIMEOUT
        # =====================================================
        except requests.exceptions.Timeout:

            print("Timeout")
            print("Tentando novamente em 10 segundos")

            time.sleep(10)

        # =====================================================
        # ERRO GERAL
        # =====================================================
        except Exception as e:

            print("ERRO:")
            print(e)

            resultado = "Erro na execução"

            break

    # =========================================================
    # SALVAR RESULTADO
    # =========================================================
    resultados.append({
        "player": player,
        "analise": resultado
    })

    print("Resultado salvo")

    # =========================================================
    # DELAY ENTRE REQUESTS
    # =========================================================
    print(f"Esperando {DELAY_ENTRE_JOGADORES}s...")

    time.sleep(DELAY_ENTRE_JOGADORES)

# =========================================================
# EXPORTAR CSV FINAL
# =========================================================
df_out = pd.DataFrame(resultados)

df_out.to_csv(
    "output.csv",
    index=False,
    encoding="utf-8-sig"
)

print("output.csv gerado com sucesso")
print("Total processado:", len(df_out))
