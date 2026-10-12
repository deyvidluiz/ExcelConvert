"""Catálogo inicial da ficha CEMIG; regiões exatas permanecem calibráveis pelo admin."""

DEFAULT_TEMPLATE_CODE = "cemig-tc-comissionamento"
DEFAULT_TEMPLATE_NAME = "Ensaios de Comissionamento — Transformador de Corrente"

# As páginas e âncoras são metadados compactos para o Gemini. A região normalizada
# permanece nula até a calibração manual da imagem de referência.
DEFAULT_FIELDS = [
    ("instalacao", "Instalação", "Identificação da instalação e do equipamento", 1, "text", True, "cabeçalho de identificação"),
    ("equipamento", "Equipamento", "Identificação da instalação e do equipamento", 1, "text", True, "cabeçalho de identificação"),
    ("fabricante", "Fabricante", "Identificação da instalação e do equipamento", 1, "text", False, "cabeçalho de identificação"),
    ("numero_serie", "Número de série", "Identificação da instalação e do equipamento", 1, "text", False, "cabeçalho de identificação"),
    ("tensao_nominal", "Tensão nominal", "Identificação da instalação e do equipamento", 1, "text", False, "cabeçalho de identificação"),
    ("corrente_nominal", "Corrente nominal", "Identificação da instalação e do equipamento", 1, "text", False, "cabeçalho de identificação"),
    ("isolamento_cc_ensaio", "Ensaio", "Isolamento com C.C.", 1, "text", False, "tabela de isolamento com corrente contínua"),
    ("isolamento_cc_valor", "Valor", "Isolamento com C.C.", 1, "decimal", False, "tabela de isolamento com corrente contínua", "preservar vírgula e unidade"),
    ("isolamento_cc_unidade", "Unidade", "Isolamento com C.C.", 1, "text", False, "tabela de isolamento com corrente contínua"),
    ("terminais_secundarios", "Terminais", "Terminais secundários", 1, "text", False, "tabela de terminais secundários"),
    ("terminais_secundarios_valores", "Valores", "Terminais secundários", 1, "text", False, "tabela de terminais secundários"),
    ("relacao_transformacao_terminal", "Terminal", "Relação de transformação", 1, "text", False, "tabela de relação de transformação"),
    ("relacao_transformacao_valor", "Relação medida", "Relação de transformação", 1, "decimal", False, "tabela de relação de transformação", "preservar casas decimais"),
    ("relacao_transformacao_desvio", "Desvio", "Relação de transformação", 1, "decimal", False, "tabela de relação de transformação"),
    ("resistencia_ohmica_terminal", "Terminal", "Resistência ôhmica", 1, "text", False, "tabela de resistência ôhmica"),
    ("resistencia_ohmica_valor", "Resistência", "Resistência ôhmica", 1, "decimal", False, "tabela de resistência ôhmica", "preservar unidade"),
    ("resistencia_ohmica_unidade", "Unidade", "Resistência ôhmica", 1, "text", False, "tabela de resistência ôhmica"),
    ("polaridade_terminal", "Terminal", "Terminais de mesma polaridade", 1, "text", False, "tabela de polaridade"),
    ("polaridade_resultado", "Resultado", "Terminais de mesma polaridade", 1, "text", False, "tabela de polaridade"),
    ("saturacao_ponto", "Ponto de saturação", "Saturação de proteção", 1, "text", False, "tabela ou curva de saturação"),
    ("saturacao_tensao", "Tensão", "Saturação de proteção", 1, "decimal", False, "tabela ou curva de saturação", "preservar unidade"),
    ("saturacao_corrente", "Corrente", "Saturação de proteção", 1, "decimal", False, "tabela ou curva de saturação", "preservar unidade"),
    ("isolamento_ca_ensaio", "Ensaio", "Isolamento com C.A.", 1, "text", False, "tabela de isolamento com corrente alternada"),
    ("isolamento_ca_valor", "Valor", "Isolamento com C.A.", 1, "decimal", False, "tabela de isolamento com corrente alternada", "preservar vírgula e unidade"),
    ("isolamento_ca_unidade", "Unidade", "Isolamento com C.A.", 1, "text", False, "tabela de isolamento com corrente alternada"),
    ("fator_potencia_oleo_tanque", "Tanque", "Fator de potência do óleo", 1, "text", False, "tabela de fator de potência do óleo"),
    ("fator_potencia_oleo_valor", "Fator de potência", "Fator de potência do óleo", 1, "decimal", False, "tabela de fator de potência do óleo"),
    ("rigidez_dieletica_amostra", "Amostra", "Rigidez dielétrica", 1, "text", False, "tabela de rigidez dielétrica"),
    ("rigidez_dieletica_valor", "Rigidez", "Rigidez dielétrica", 1, "decimal", False, "tabela de rigidez dielétrica", "preservar unidade"),
    ("observacoes", "Observações", "Observações", 1, "text", False, "campo livre de observações"),
    ("responsavel_ensaio", "Responsável pelo ensaio", "Assinaturas e validação", 1, "text", False, "rodapé da ficha"),
    ("data_ensaio", "Data do ensaio", "Assinaturas e validação", 1, "date", False, "rodapé da ficha", "não converter formato sem confirmação"),
]
