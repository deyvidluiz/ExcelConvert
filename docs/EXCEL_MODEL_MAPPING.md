# Mapeamento do modelo Excel CEMIG

## Fonte analisada

O arquivo local `TCA VÃO 217F - ITMU.xlsx` foi aberto somente para leitura após
descriptografia temporária em memória. A senha não faz parte deste relatório,
do código ou do Git.

O arquivo contém 17 abas. `Plan1` é a ficha principal, com dimensão `A1:Y63`,
área de impressão `A1:S57`, 59 células mescladas, 105 fórmulas, uma imagem
incorporada e proteção de planilha. `Plan17` e `Plan3` a `Plan16` estão vazias;
`Plan2` contém apenas dimensões auxiliares. O modelo também contém configurações
de impressora e cadeia de cálculo. Não há macros, gráficos ou controles VBA no
pacote analisado.

O modelo original não é sobrescrito. O arquivo cifrado deve permanecer em
armazenamento privado; a senha deve ser fornecida por variável de ambiente no
ambiente que gerar os arquivos.

## Mapeamento verificado

As referências abaixo são da aba `Plan1`. Intervalos indicam que o campo não é
uma célula única e exige uma representação de lista/linhas na extração. Células
com fórmulas não são destinos de escrita.

| field_id | destino observado | tipo | situação |
| --- | --- | --- | --- |
| `instalacao` | `Plan1!C5` | texto | confirmado |
| `equipamento` | nenhum destino editável; `A2` é título protegido | texto | revisão necessária |
| `fabricante` | `Plan1!I4` | texto | confirmado |
| `numero_serie` | `Plan1!I6` | identificador/texto | confirmado; preservar zeros e grafia |
| `tensao_nominal` | `Plan1!P4` | texto/medida | confirmado |
| `corrente_nominal` | `Plan1!I7:I8` | texto/medida repetida | confirmado como intervalo |
| `isolamento_cc_ensaio` | `Plan1!B12` | texto | confirmado |
| `isolamento_cc_valor` | `Plan1!D12` | decimal/texto técnico | confirmado |
| `isolamento_cc_unidade` | `Plan1!D13` | texto | confirmado |
| `terminais_secundarios` | `Plan1!B14:B37` | lista de terminais | confirmado como intervalo |
| `terminais_secundarios_valores` | `Plan1!D14:D37` | lista de medições | confirmado como intervalo |
| `relacao_transformacao_terminal` | `Plan1!E38:E43` | lista de terminais | confirmado como intervalo |
| `relacao_transformacao_valor` | não há destino de entrada equivalente; `H38:H43` são fórmulas | decimal | revisão necessária |
| `relacao_transformacao_desvio` | `Plan1!J38:J43` são fórmulas | decimal | não escrever |
| `resistencia_ohmica_terminal` | `Plan1!E18:E37` | lista de terminais | confirmado como intervalo |
| `resistencia_ohmica_valor` | `Plan1!K18:K37` | lista de medições | confirmado como intervalo |
| `resistencia_ohmica_unidade` | `Plan1!K12` é rótulo impresso | texto | revisão necessária |
| `polaridade_terminal` | nenhum bloco identificável na aba principal | texto | revisão necessária |
| `polaridade_resultado` | nenhum bloco identificável na aba principal | texto | revisão necessária |
| `saturacao_ponto` | `Plan1!O41:O43` | lista de pontos | confirmado como intervalo |
| `saturacao_tensao` | `Plan1!P41:P43` e `Plan1!R41:R43` | duas séries de medidas | revisão de schema |
| `saturacao_corrente` | `Plan1!Q41:Q43` e `Plan1!S41:S43` | duas séries de medidas | revisão de schema |
| `isolamento_ca_ensaio` | `Plan1!E44` contém o número do MEU | texto técnico | confirmar semântica |
| `isolamento_ca_valor` | tabela `Plan1!E47:M48` possui entradas e fórmulas | medidas múltiplas | revisão de schema |
| `isolamento_ca_unidade` | rótulos fixos em `D45:D46`, `I45:I46`, `O45:O46` | texto | não é campo único |
| `fator_potencia_oleo_tanque` | não há célula única identificável | texto | revisão necessária |
| `fator_potencia_oleo_valor` | `Plan1!Q47:Q48` são fórmulas | decimal | não escrever |
| `rigidez_dieletica_amostra` | não há rótulo/célula única identificável | texto | revisão necessária |
| `rigidez_dieletica_valor` | entradas alternadas em `Plan1!A52,C52,E52,G52,I52` | lista de medidas | revisão de schema |
| `observacoes` | `Plan1!C53:C55` | texto livre | confirmado como intervalo |
| `responsavel_ensaio` | `Plan1!C56` | texto | confirmado |
| `data_ensaio` | `Plan1!R56` | data/texto | confirmado; não normalizar sem validação |

## Campos editáveis do modelo que não estão nos 32 campos

A ficha também possui entradas editáveis para fase (`B4`), ampliação (`C6`),
tipo (`H5`), classe de isolamento (`P5`), classes de exatidão (`P6:P10`),
número do manual (`D8`), fator térmico (`C9`), nível básico de impulso (`J9`),
corrente térmica (`J10`), instrumentos e condições ambientais. Esses campos
precisam ser adicionados ao catálogo ou explicitamente mantidos para revisão;
não devem receber valores presumidos durante a exportação.

## Limitações e próximo passo

O exportador preserva as relações de printerSettings, a imagem, as propriedades
customizadas e o metadata adicional do pacote. A calcChain.xml não é copiada,
pois fica inválida quando entradas são alteradas e deve ser reconstruída pelo
Excel; sharedStrings.xml pode ser normalizada para strings inline sem alteração
visual ou de edição.

O catálogo atual usa `value: string`, mas parte do modelo exige listas e séries
de medições. A exportação deve aceitar intervalos somente quando a extração
fornecer uma lista estruturada com o mesmo número de posições. Até essa
ampliação, os campos marcados como revisão não serão escritos em células de
fórmula nem convertidos heurísticamente.
