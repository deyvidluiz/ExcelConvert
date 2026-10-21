"""Catálogo revisado da ficha CEMIG — TCA ITMU (aba Plan1 do modelo de referência).

As 437 células do pacote original são apenas candidatas: a lista foi gerada por
permissão de célula, sem distinguir campo variável de rótulo digitado em célula
livre. Este catálogo é a revisão dessa lista célula por célula, com o rótulo
impresso ao lado de cada entrada como âncora para a leitura da foto.

CONFIRMED reúne os destinos cujo significado está sustentado por um rótulo
adjacente, por um cabeçalho de coluna ou por uma fórmula da própria planilha.
PENDING reúne os destinos que ainda precisam de confirmação humana: eles são
cadastrados como campo para revisão, mas nunca recebem mapeamento no Excel.
PENDING_BLOCKS descreve um bloco inteiro cuja estrutura não pôde ser concluída.
PRESERVED_TEXT são textos fixos digitados em células desbloqueadas: parecem
campos na varredura de permissões, mas são rótulos e nomenclatura da ficha.
"""

TEMPLATE_CODE = "cemig-tca-itmu"
TEMPLATE_NAME = "CEMIG — TCA ITMU"
TEMPLATE_ISSUER = "CEMIG"
TEMPLATE_DESCRIPTION = (
    "Ficha de ensaios de comissionamento de transformador de corrente no formato TCA ITMU. "
    "Derivada da referência TCA VÃO 217F - ITMU; a exportação usa o próprio Excel como base."
)
SHEET_NAME = "Plan1"
PRINT_AREA = "A1:S57"
WORKBOOK_FILENAME = "modelo_tca.xlsx"
CANDIDATES_FILENAME = "campos_para_revisar.json"


def _field(field_id, name, section, cell, anchor, *, expected_type="text", required=False, rule=""):
    return {
        "field_id": field_id,
        "name": name,
        "section": section,
        "cell": cell,
        "anchor": anchor,
        "expected_type": expected_type,
        "required": required,
        "rule": rule,
    }


# --------------------------------------------------------------------------- #
# identificação e instrumentos
# --------------------------------------------------------------------------- #

IDENTIFICATION = [
    _field("folha_numero", "Folha nº", "Identificação", "R1", "cabeçalho, à direita de 'Folha Nº:'"),
    _field("fase", "Fase", "Identificação", "B4", "1ª linha de identificação, à direita de 'Fase:'", required=True),
    _field("fabricante", "Fabricante", "Identificação", "I4", "1ª linha de identificação, à direita de 'Fabricante:'"),
    _field("tensao_circuito", "Tensão do circuito", "Identificação", "P4", "1ª linha de identificação, à direita de 'Tensão do circuito:'"),
    _field("instalacao", "Instalação", "Identificação", "C5", "2ª linha de identificação, à direita de 'Instalação:'", required=True),
    _field("tipo", "Tipo", "Identificação", "H5", "2ª linha de identificação, à direita de 'Tipo:'"),
    _field("classe_isolamento", "Classe de isolamento", "Identificação", "P5", "2ª linha de identificação, à direita de 'Classe Isolamento:'"),
    _field("ampliacao", "Ampliação", "Identificação", "C6", "3ª linha de identificação, à direita de 'Ampliação:'"),
    _field("numero_serie", "Nº de série", "Identificação", "I6", "3ª linha de identificação, à direita de 'Nº Série:'", required=True, rule="preservar pontos, espaços e zeros como escritos"),
    _field("classe_exatidao_sec_v", "Cl. exatidão sec. V", "Identificação", "P6", "coluna direita, à direita de 'Cl. Exat.( sec.V ):'"),
    _field("circuito", "Circuito", "Identificação", "C7", "4ª linha de identificação, à direita de 'Circuito:'", required=True),
    _field("corrente_nominal_1", "Corrente nominal (1ª linha)", "Identificação", "I7", "4ª linha de identificação, à direita do primeiro 'Corr. Nom.:'"),
    _field("classe_exatidao_sec_x", "Cl. exatidão sec. X", "Identificação", "P7", "coluna direita, à direita de 'Cl. Exat.( sec.X ):'"),
    _field("numero_manual_instrucao", "Nº do manual de instrução", "Identificação", "D8", "5ª linha de identificação, à direita de 'Nº Manual Instrução:'"),
    _field("corrente_nominal_2", "Corrente nominal (2ª linha)", "Identificação", "I8", "5ª linha de identificação, à direita do segundo 'Corr. Nom.:'"),
    _field("classe_exatidao_sec_y", "Cl. exatidão sec. Y", "Identificação", "P8", "coluna direita, à direita de 'Cl. Exat.( sec.Y ):'"),
    _field("fator_termico", "Fator térmico", "Identificação", "C9", "6ª linha de identificação, à direita de 'Fator Térmico:'"),
    _field("nivel_basico_impulso", "Nível básico de impulso", "Identificação", "J9", "6ª linha de identificação, à direita de 'Nivel básico impulso.:'"),
    _field("classe_exatidao_sec_w", "Cl. exatidão sec. W", "Identificação", "P9", "coluna direita, à direita de 'Cl. Exat.( sec.W ):'"),
    _field("corrente_termica", "Corrente térmica", "Identificação", "J10", "7ª linha de identificação, à direita de 'Corrente Térmica:'"),
    _field("classe_exatidao_sec_z", "Cl. exatidão sec. Z", "Identificação", "P10", "coluna direita, à direita de 'Cl. Exat.( sec.Z ):'"),
]

INSTRUMENTS = [
    _field("relacao_alicate_amperimetro", "Alicate amperímetro", "Instrumentos e condições", "H12", "bloco 'Relação Transformação', à direita de 'Alicate Amp:'"),
    _field("relacao_voltimetro", "Voltímetro da relação", "Instrumentos e condições", "H13", "bloco 'Relação Transformação', à direita de 'Voltimetro:'"),
    _field("relacao_metodo", "Método da relação", "Instrumentos e condições", "H15", "bloco 'Relação Transformação', à direita de 'Método:'", rule="transcrever a marcação como aparece, inclusive um 'x'"),
    _field("resistencia_temperatura_ambiente", "Temperatura ambiente da resistência", "Instrumentos e condições", "L14", "bloco 'Resistência Ôhmica', valor isolado acima da coluna 'Med.Temp. Amb.'", expected_type="decimal", rule="as fórmulas de correção a 75 °C leem esta célula"),
    _field("resistencia_umidade_relativa", "Umidade relativa da resistência", "Instrumentos e condições", "N14", "bloco 'Resistência Ôhmica', à direita de 'UR %:'", expected_type="decimal"),
    _field("resistencia_ponte_numero", "Ponte nº da resistência", "Instrumentos e condições", "M15", "bloco 'Resistência Ôhmica', à direita de 'Ponte Nº:'"),
    _field("derivacao_voltimetro", "Voltímetro da derivação", "Instrumentos e condições", "Q15", "bloco 'Derivação Inicial/Final', à direita de 'Voltim.:'"),
    _field("derivacao_amperimetro", "Amperímetro da derivação", "Instrumentos e condições", "S15", "bloco 'Derivação Inicial/Final', à direita de 'Amper.:'"),
]


# --------------------------------------------------------------------------- #
# isolamento com C.C.: uma medição por linha, identificada pelos rótulos A/B/C
# --------------------------------------------------------------------------- #

_ELEMENT_SLUGS = {
    "Prim.": "prim",
    "Sec's+M": "secs_m",
    "Sec's": "secs",
    "Massa": "massa",
    "Sec.V": "sec_v",
    "Sec.X": "sec_x",
    "Sec.Y": "sec_y",
    "Sec.W": "sec_w",
    "Sec.Z": "sec_z",
}

# (linha, elemento em A, elemento em B, guarda impressa em C)
ISOLATION_ROWS = [
    (14, "Prim.", "Sec's+M", "_"),
    (15, "Prim.", "Sec's", "Massa"),
    (16, "Prim.", "Massa", "Sec's"),
    (17, "Prim.", "Sec.V", "xywzm"),
    (18, "Prim.", "Sec.X", "vywzm"),
    (19, "Prim.", "Sec.Y", "vxwzm"),
    (20, "Prim.", "Sec.W", "vxyzm"),
    (21, "Prim.", "Sec.Z", "vxywm"),
    (22, "Sec.V", "Massa", "xywzh"),
    (23, "Sec.V", "Sec.X", "ywzmh"),
    (24, "Sec.V", "Sec.Y", "xwzmh"),
    (25, "Sec.V", "Sec.W", "xyzmh"),
    (26, "Sec.V", "Sec.Z", "xywmh"),
    (27, "Sec.X", "Massa", "vywzh"),
    (28, "Sec.X", "Sec.Y", "vwzmh"),
    (29, "Sec.X", "Sec.W", "vyzmh"),
    (30, "Sec.X", "Sec.Z", "vywmh"),
    (31, "Sec.Y", "Massa", "vxwzh"),
    (32, "Sec.Y", "Sec.W", "vxzmh"),
    (33, "Sec.Y", "Sec.Z", "vxwmh"),
    (34, "Sec.W", "Massa", "vxyzh"),
    (35, "Sec.W", "Sec.Z", "vxymh"),
    (36, "Sec.Z", "Massa", "vxywh"),
    (37, "Sec's", "Massa", "Prim."),
]

ISOLATION = [
    _field(
        "isolamento_cc_{}_{}".format(_ELEMENT_SLUGS[first], _ELEMENT_SLUGS[second]),
        "Isolamento C.C. {} – {}".format(first, second),
        "Isolamento com C.C.",
        "D{}".format(row),
        "coluna 'MΩ' da tabela 'Isolamento Com C.C.', linha {} / {} (guarda {})".format(first, second, guard),
        rule="preservar sinais como '>' e o separador decimal escrito",
    )
    for row, first, second, guard in ISOLATION_ROWS
]


# --------------------------------------------------------------------------- #
# relação de transformação e resistência ôhmica: mesmas linhas, colunas distintas
# --------------------------------------------------------------------------- #

# (linha, rótulo impresso da linha, identificador)
RATIO_ROWS = [(row, terminal, terminal.replace("-", "_")) for row, terminal in [
    (18, "v1-v2"), (19, "v1-v3"), (20, "v1-v4"), (21, "v1-v5"),
    (22, "x1-x2"), (23, "x1-x3"), (24, "x1-x4"), (25, "x1-x5"),
    (26, "y1-y2"), (27, "y1-y3"), (28, "y1-y4"), (29, "y1-y5"),
    (30, "w1-w2"), (31, "w1-w3"), (32, "w1-w4"), (33, "w1-w5"),
    (34, "z1-z2"), (35, "z1-z3"), (36, "z1-z4"), (37, "z1-z5"),
]] + [
    (38, "Primário Série, terminais 1S1-1S2", "1s1_1s2_serie"),
    (39, "Primário Ligado em Série - Paralelo, terminais 1S1-1S2", "1s1_1s2_serie_paralelo"),
    (40, "Primário Ligado em Paralelo, terminais 1S1-1S2", "1s1_1s2_paralelo"),
    (41, "Primário Série, terminais 2S1-2S2", "2s1_2s2_serie"),
    (42, "Primário Ligado em Série - Paralelo, terminais 2S1-2S2", "2s1_2s2_serie_paralelo"),
    (43, "Primário Ligado em Paralelo, terminais 2S1-2S2", "2s1_2s2_paralelo"),
]

# As colunas H, J, L e N da tabela são fórmulas da planilha e não recebem escrita.
RATIO_COLUMNS = [
    ("F", "corrente_primaria", "Corrente primária", "coluna 'Corrente Primária'", "decimal"),
    ("G", "corrente_secundaria", "Corrente secundária", "coluna 'Corrente Secund.'", "decimal"),
    ("I", "relacao_nominal", "Relação nominal", "coluna 'Relação Nominal'", "text"),
]

RATIO = [
    _field(
        "relacao_{}_{}".format(slug, suffix),
        "Relação {} — {}".format(label, title.lower()),
        "Relação de transformação",
        "{}{}".format(column, row),
        "tabela 'Relação Transformação', {}, linha {}".format(anchor, label),
        expected_type=expected_type,
        rule="transcrever como escrito, sem arredondar",
    )
    for row, label, slug in RATIO_ROWS
    for column, suffix, title, anchor, expected_type in RATIO_COLUMNS
]

# A planilha só corrige resistência a 75 °C nas linhas em que há fórmula em L/N.
RESISTANCE_ROWS = [item for item in RATIO_ROWS if item[0] <= 38 or item[0] == 41]

RESISTANCE_COLUMNS = [
    ("K", "medida", "Resistência medida na temperatura ambiente", "coluna 'Med.Temp. Amb. / Medido'"),
    ("M", "fabricante", "Resistência do fabricante a 75 °C", "coluna 'FABRIC. / 75°C'"),
]

RESISTANCE = [
    _field(
        "resistencia_{}_{}".format(slug, suffix),
        "Resistência {} — {}".format(label, title.lower()),
        "Resistência ôhmica",
        "{}{}".format(column, row),
        "tabela 'Resistência Ôhmica( mΩ )', {}, linha {}".format(anchor, label),
        expected_type="decimal",
        rule="transcrever como escrito, sem arredondar",
    )
    for row, label, slug in RESISTANCE_ROWS
    for column, suffix, title, anchor in RESISTANCE_COLUMNS
]


# --------------------------------------------------------------------------- #
# blocos inferiores
# --------------------------------------------------------------------------- #

AC_INSULATION = [
    _field("isolamento_ca_meu_numero", "MEU nº do isolamento C.A.", "Isolamento com C.A.", "E44", "linha 'Isolamento Com C.A. MEU Nº:', primeiro valor à direita"),
    _field("isolamento_ca_kv_ensaio", "kV de ensaio", "Isolamento com C.A.", "K44", "linha do isolamento C.A., à direita de 'kV ensaio:'", expected_type="decimal", rule="as fórmulas de fator de potência só tratam 2,5 e 10"),
    _field("isolamento_ca_temperatura_ambiente", "Temperatura ambiente do isolamento C.A.", "Isolamento com C.A.", "N44", "linha do isolamento C.A., à direita de 'Temp. Amb.(°C):'", expected_type="decimal", rule="a correção a 20 °C lê esta célula"),
    _field("isolamento_ca_umidade_relativa", "Umidade relativa do isolamento C.A.", "Isolamento com C.A.", "R44", "linha do isolamento C.A., à direita de 'U.R.(%):'", expected_type="decimal"),
    _field("isolamento_ca_corrente_lida", "Corrente lida do isolamento C.A.", "Isolamento com C.A.", "E47", "linha 'Prim. / Sec's / Ground', valor antes do resultado da coluna 'm A'", expected_type="decimal"),
    _field("isolamento_ca_potencia_lida", "Potência lida do isolamento C.A.", "Isolamento com C.A.", "K47", "linha 'Prim. / Sec's / Ground', valor antes do resultado da coluna 'mW'", expected_type="decimal"),
]

OIL_POWER_FACTOR = [
    _field("oleo_corrente_lida", "Corrente lida do óleo", "Fator de potência do óleo", "E48", "linha 'Fator de Potência do Óleo', valor antes do resultado da coluna 'm A'", expected_type="decimal"),
    _field("oleo_potencia_lida", "Potência lida do óleo", "Fator de potência do óleo", "K48", "linha 'Fator de Potência do Óleo', valor antes do resultado da coluna 'mW'", expected_type="decimal"),
]

MANUFACTURER_NAMES = [
    _field("nomenclatura_sec_v", "Nomenclatura do fabricante — V", "Nomenclatura do fabricante", "M50", "bloco 'Nomenclatura do Fabricante', à direita de 'V:'"),
    _field("nomenclatura_sec_x", "Nomenclatura do fabricante — X", "Nomenclatura do fabricante", "M51", "bloco 'Nomenclatura do Fabricante', à direita de 'X:'"),
    _field("nomenclatura_sec_y", "Nomenclatura do fabricante — Y", "Nomenclatura do fabricante", "M52", "bloco 'Nomenclatura do Fabricante', à direita de 'Y:'"),
    _field("nomenclatura_sec_w", "Nomenclatura do fabricante — W", "Nomenclatura do fabricante", "Q50", "bloco 'Nomenclatura do Fabricante', à direita de 'W:'"),
    _field("nomenclatura_sec_z", "Nomenclatura do fabricante — Z", "Nomenclatura do fabricante", "Q51", "bloco 'Nomenclatura do Fabricante', à direita de 'Z:'"),
]

# A média das amostras fica em K52, que é fórmula da planilha.
DIELECTRIC_STRENGTH = [
    _field(
        "rigidez_amostra_{}".format(index),
        "Rigidez dielétrica — amostra {}".format(index),
        "Rigidez dielétrica",
        cell,
        "bloco 'Rigidez Dielétrica (kV)', {}ª medição, valor imediatamente antes do rótulo 'kV'".format(index),
        expected_type="decimal",
    )
    for index, cell in enumerate(["A52", "C52", "E52", "G52", "I52"], start=1)
]

NOTES = [
    _field(
        "observacoes_linha_{}".format(index),
        "Observações — linha {}".format(index),
        "Observações",
        cell,
        "bloco 'Observações:', {}ª linha de texto livre".format(index),
    )
    for index, cell in enumerate(["C53", "C54", "C55"], start=1)
]

SIGNATURES = [
    _field("executante", "Executante", "Assinaturas", "C56", "rodapé, à direita de 'Executante:'"),
    _field("executante_orgao_empresa", "Órgão/Empresa do executante", "Assinaturas", "L56", "rodapé, à direita do 'Órgão/Empresa:' da linha do executante"),
    _field("executante_data", "Data do ensaio", "Assinaturas", "R56", "rodapé, à direita do 'Data:' da linha do executante", rule="não normalizar: transcrever exatamente como escrito (a referência traz '02/0626')"),
    _field("visto", "Visto", "Assinaturas", "C57", "rodapé, à direita de 'Visto:'"),
]

CONFIRMED = [
    *IDENTIFICATION,
    *INSTRUMENTS,
    *ISOLATION,
    *RATIO,
    *RESISTANCE,
    *AC_INSULATION,
    *OIL_POWER_FACTOR,
    *MANUFACTURER_NAMES,
    *DIELECTRIC_STRENGTH,
    *NOTES,
    *SIGNATURES,
]


def _pending(field_id, name, section, cell, anchor, doubt, *, expected_type="text"):
    return {**_field(field_id, name, section, cell, anchor, expected_type=expected_type), "doubt": doubt}


PENDING = [
    _pending(
        "isolamento_cc_instrumento", "Instrumento do isolamento C.C.", "Isolamento com C.C.", "B12",
        "logo abaixo do título 'Isolamento Com C.C.', sem rótulo à esquerda",
        "A célula não tem rótulo adjacente. O valor da referência ('UI1086I') tem a forma de número de megôhmetro, mas isso não está impresso na ficha.",
    ),
    _pending(
        "isolamento_cc_temperatura", "Temperatura do isolamento C.C.", "Isolamento com C.C.", "D12",
        "acima do rótulo de unidade 'MΩ' da coluna de medições",
        "Sem rótulo. O valor da referência (31,6) é igual à temperatura ambiente das outras seções, o que sugere temperatura, mas a célula fica no topo da coluna em MΩ.",
        expected_type="decimal",
    ),
    _pending(
        "isolamento_ca_mh_numero", "MH nº do isolamento C.A.", "Isolamento com C.A.", "H44",
        "linha do isolamento C.A., à direita do texto 'MH º:'",
        "O rótulo 'MH º:' está digitado na célula desbloqueada G44, não no texto fixo da ficha. É preciso confirmar a sigla e se o valor vai em H44.",
    ),
    _pending(
        "isolamento_ca_multiplicador_corrente", "Multiplicador de corrente do isolamento C.A.", "Isolamento com C.A.", "G47",
        "linha 'Prim. / Sec's / Ground', coluna sob os rótulos 'LV' e 'swith'",
        "A fórmula I47=E47*G47 mostra que é um multiplicador, mas falta confirmar se o valor vem da posição da chave LV do instrumento ou de uma leitura.",
        expected_type="decimal",
    ),
    _pending(
        "isolamento_ca_multiplicador_potencia", "Multiplicador de potência do isolamento C.A.", "Isolamento com C.A.", "M47",
        "linha 'Prim. / Sec's / Ground', coluna antes do resultado 'mW'",
        "Mesma dúvida da coluna de corrente: a fórmula O47=K47*M47 indica multiplicador, sem rótulo impresso que confirme a origem do número.",
        expected_type="decimal",
    ),
    _pending(
        "oleo_multiplicador_corrente", "Multiplicador de corrente do óleo", "Fator de potência do óleo", "G48",
        "linha 'Fator de Potência do Óleo', coluna sob os rótulos 'LV' e 'swith'",
        "Mesma dúvida do multiplicador da linha de isolamento C.A.",
        expected_type="decimal",
    ),
    _pending(
        "oleo_multiplicador_potencia", "Multiplicador de potência do óleo", "Fator de potência do óleo", "M48",
        "linha 'Fator de Potência do Óleo', coluna antes do resultado 'mW'",
        "Mesma dúvida do multiplicador da linha de isolamento C.A.",
        expected_type="decimal",
    ),
    _pending(
        "rigidez_instrumento", "Instrumento da rigidez dielétrica", "Rigidez dielétrica", "I50",
        "bloco 'Rigidez Dielétrica (kV)', à direita de 'Instr. Nº:'",
        "O rótulo está em G50 e há três células livres à direita (I50, J50 e K50), todas vazias na referência. O destino exato precisa ser confirmado na ficha impressa.",
    ),
    _pending(
        "rigidez_temperatura_ambiente", "Temperatura ambiente da rigidez dielétrica", "Rigidez dielétrica", "C51",
        "bloco 'Rigidez Dielétrica (kV)', à direita de 'Temp. Amb. (°c):'",
        "O rótulo está em A51 e tanto C51 como D51 estão livres e vazias na referência.",
        expected_type="decimal",
    ),
    _pending(
        "rigidez_umidade_relativa", "Umidade relativa da rigidez dielétrica", "Rigidez dielétrica", "I51",
        "bloco 'Rigidez Dielétrica (kV)', à direita de 'U. R.(%):'",
        "O rótulo está em H51 e tanto I51 como J51 estão livres e vazias na referência.",
        expected_type="decimal",
    ),
    _pending(
        "visto_data", "Data do visto", "Assinaturas", "R57",
        "rodapé, à direita do 'Data:' da linha do visto",
        "Diferente da linha do executante, R57 e S57 não são mescladas e o 'Órgão/Empresa' dessa linha (L57) está protegido. Confirmar onde a data do visto é escrita.",
    ),
]

PENDING_BLOCKS = [
    {
        "name": "Derivação Inicial/Final",
        "ranges": ["O18:S43"],
        "doubt": (
            "As colunas 'Volts' e 'Amp.' inicial e final existem nas linhas 18 a 43, mas a correspondência entre "
            "cada linha e a derivação identificada na coluna O não está impressa: O18:O21, O22:O25, O26:O29, "
            "O30:O33 e O34:O37 são mescladas de quatro em quatro linhas e, da linha 38 em diante, são células "
            "soltas. A referência só traz dados nas linhas 41 a 43. Nenhum campo foi criado para este bloco."
        ),
    },
]

PRESERVED_TEXT = [
    {"range": "M14", "text": "UR %: ", "reason": "rótulo da umidade relativa digitado em célula desbloqueada"},
    {"range": "M16", "text": "FABRIC.", "reason": "cabeçalho da coluna de resistência do fabricante"},
    {"range": "N16", "text": "ERRO", "reason": "cabeçalho da coluna de erro da resistência"},
    {"range": "G44", "text": "MH º:", "reason": "rótulo do bloco de isolamento com C.A."},
    {"range": "E18:E43", "text": None, "reason": "nomenclatura dos terminais e das ligações do primário que identifica cada linha das tabelas"},
]
