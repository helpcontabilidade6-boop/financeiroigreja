import pandas as pd
import re


def ler_livro_caixa_txt(arquivo):

    linhas = arquivo.read().decode("utf-8").splitlines()

    registros = []

    data_atual = ""

    for linha in linhas:

        linha = linha.strip()

        if not linha:
            continue

        # Captura datas tipo 03/05/26
        if re.match(r"\d{2}/\d{2}/\d{2}$", linha):

            dia, mes, ano = linha.split("/")

            data_atual = f"{dia}/{mes}/20{ano}"

            continue

        # Captura:
        # Dízimos 180.00
        # Ofertas 359.50
        match = re.search(r"(.+?)\s+([\d.]+)$", linha)

        if not match:
            continue

        descricao = match.group(1).strip()

        try:
            valor = float(match.group(2))
        except:
            continue

        registros.append(
            {
                "Data": data_atual,
                "Nome": descricao,
                "Valor": valor,
                "Tipo": "Entrada",
            }
        )

    return pd.DataFrame(registros)