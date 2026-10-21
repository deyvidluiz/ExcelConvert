# Modelo CEMIG — TCA ITMU

Integração do pacote `Pacote_TCA_ITMU` ao ExcelConvert. O pacote de referência
fica fora do Git (`molds/` em `.gitignore`) porque a planilha contém os dados de
um ensaio real; o catálogo, o cadastro e os testes vivem no repositório.

## Compatibilidade conferida antes de implementar

O `LEIA-ME.md` do pacote trazia um `registrar_tca_extraido.py` de exemplo. Ele é
compatível com os modelos atuais (`DocumentTemplate`, `TemplateField`,
`ExcelTemplate`, `ExcelFieldMapping`), mas foi reescrito como comando do projeto
por três motivos: ele registrava a planilha original com os dados do ensaio
anterior, aprovava campos a partir de um JSON sem conferir a planilha, e não
tratava a herança de valores antigos na exportação.

Duas afirmações do `LEIA-ME.md` não se confirmaram na planilha:

- as 437 candidatas **incluem** as âncoras mescladas; nenhum campo do catálogo
  ficou fora da lista original (`fields_outside_candidates: 0`);
- `build_xlsx_from_template` já não impunha `number_format='@'` nem
  `quotePrefix=True`; a imposição global ficou só no exportador de layout, que
  não é usado quando há modelo Excel.

## Como cadastrar

```
python manage.py registrar_tca_itmu --directory molds/Pacote_TCA_ITMU --dry-run
python manage.py registrar_tca_itmu --directory molds/Pacote_TCA_ITMU \
    --template-version 1.0.0 --activate \
    --write-review molds/Pacote_TCA_ITMU/campos_revisados.json
```

O `--dry-run` confere o pacote e imprime o relatório sem gravar nada. Sem
`--activate`, o modelo e a cópia Excel nascem inativos para revisão no admin.
Uma versão já cadastrada nunca é sobrescrita: use outra `--template-version`.
`--save-clean-copy` grava a cópia limpa em um arquivo para inspeção no Excel.

## Catálogo revisado

`modelos/tca_itmu_catalog.py` é a revisão célula por célula das 437 candidatas
da aba `Plan1`. A âncora de cada campo cita o rótulo impresso ao lado, porque o
endereço Excel sozinho não orienta a leitura da foto.

| Seção | Campos confirmados | Destinos |
| --- | --- | --- |
| Identificação | 21 | `R1` a `P10` |
| Instrumentos e condições | 8 | `H12` a `S15` |
| Isolamento com C.C. | 24 | `D14` a `D37` |
| Relação de transformação | 78 | `F18` a `I43` |
| Resistência ôhmica | 44 | `K18` a `M41` |
| Isolamento com C.A. | 6 | `E44` a `K47` |
| Fator de potência do óleo | 2 | `E48` e `K48` |
| Nomenclatura do fabricante | 5 | `M50` a `Q51` |
| Rigidez dielétrica | 5 | `A52` a `I52` |
| Observações | 3 | `C53` a `C55` |
| Assinaturas | 4 | `C56` a `C57` |

Reconciliação das 437 candidatas: 200 viraram campo mapeado, 11 ficaram em
confirmação, 30 são texto fixo digitado em célula desbloqueada, 111 pertencem ao
bloco de derivação em revisão e 85 foram descartadas. Nenhuma das 85 descartadas
tinha valor na referência — são sobras estruturais de linha, não campos.

As colunas `H`, `J`, `L` e `N` das tabelas de relação e resistência, `I47:J48`,
`O47:P48`, `Q47:R48`, `S47:S48` e `K52` são fórmulas da planilha e nunca recebem
escrita. As tabelas auxiliares de correção (`U:V` e `X:Y`) ficam fora da área de
impressão e permanecem intactas.

### Textos fixos preservados em células desbloqueadas

A varredura por permissão de célula não distingue campo de rótulo. Estes textos
parecem campos e não são:

| Célula | Texto | Por quê |
| --- | --- | --- |
| `M14` | `UR %:` | rótulo da umidade relativa digitado em célula livre |
| `M16` | `FABRIC.` | cabeçalho da coluna de resistência do fabricante |
| `N16` | `ERRO` | cabeçalho da coluna de erro |
| `G44` | `MH º:` | rótulo do bloco de isolamento com C.A. |
| `E18:E43` | `v1-v2` … `2S1-2S2` | nomenclatura dos terminais que identifica cada linha |

## Cópia limpa do modelo

A cópia registrada é gerada no cadastro, nunca copiada do pacote. São esvaziadas
apenas as células desbloqueadas, sem fórmula e fora da lista de textos fixos,
dentro da área de impressão `A1:S57` — 78 células com dados do ensaio anterior na
referência atual. O round-trip foi conferido contra a planilha original: 105
fórmulas, 59 mesclagens, a área de impressão `A1:S57`, a proteção da aba, a
imagem incorporada, estilos, larguras e alturas seguem idênticos. `calcChain.xml`
e `sharedStrings.xml` não são copiados: o Excel reconstrói o primeiro e o
openpyxl grava strings inline, sem efeito visual ou de edição.

## Exportação

Com o modelo selecionado no envio, a exportação XLSX preenche a cópia limpa pelo
mapeamento, em vez de reconstruir a planilha. As cores, bordas, mesclagens e
dimensões vêm do próprio arquivo e não dependem da foto: uma ficha fotografada em
preto e branco produz a mesma planilha que a colorida, porque nenhuma cor é lida
do documento.

Campo que não aparece na extração tem a célula esvaziada antes de salvar
(`_clear_unextracted_mappings`): nenhum valor do arquivo-base sobrevive a uma
extração parcial. Toda exportação ainda valida que estrutura, mesclagens,
impressão, dimensões e as 105 fórmulas continuam iguais às do modelo.

Campo de tipo `number` ou `decimal` é gravado como número quando o texto lido é
inequivocamente numérico (`31,6`, `238.7`, `10`, `1.234,56`). Isso não é
cosmético: as fórmulas da ficha comparam e procuram valores numéricos, e um
`"10"` gravado como texto faz `K44=10` dar falso e o `VLOOKUP` da correção de
temperatura cair na última faixa sem avisar. Tudo o mais é gravado exatamente
como foi lido: `>5000000`, `300x600 - 5A`, `13,8 kV` e as datas seguem texto. As
24 medições de isolamento com C.C. são do tipo texto de propósito, para preservar
o sinal `>`; nenhuma fórmula da planilha lê a coluna `D`.

## Pontos que precisam de revisão humana

Os campos abaixo estão cadastrados como `TemplateField` para revisão, **sem**
destino no Excel e **sem** mapeamento: enquanto não forem confirmados, a
exportação não tem por onde escrever neles. Depois de confirmar, preencha
`excel_sheet`/`excel_cell` e crie o `ExcelFieldMapping` pelo admin.

| Campo | Célula provável | Dúvida |
| --- | --- | --- |
| `isolamento_cc_instrumento` | `B12` | sem rótulo adjacente; o valor da referência tem forma de número de megôhmetro, mas isso não está impresso |
| `isolamento_cc_temperatura` | `D12` | sem rótulo; o valor coincide com a temperatura ambiente das outras seções, mas a célula fica no topo da coluna em MΩ |
| `isolamento_ca_mh_numero` | `H44` | o rótulo `MH º:` está digitado em `G44`, célula desbloqueada; confirmar a sigla e o destino |
| `isolamento_ca_multiplicador_corrente` | `G47` | a fórmula `I47=E47*G47` indica multiplicador; confirmar se vem da posição da chave `LV` |
| `isolamento_ca_multiplicador_potencia` | `M47` | mesma dúvida, pela fórmula `O47=K47*M47` |
| `oleo_multiplicador_corrente` | `G48` | mesma dúvida da linha de isolamento C.A. |
| `oleo_multiplicador_potencia` | `M48` | mesma dúvida da linha de isolamento C.A. |
| `rigidez_instrumento` | `I50` | rótulo em `G50` e três células livres à direita, todas vazias na referência |
| `rigidez_temperatura_ambiente` | `C51` | rótulo em `A51`; `C51` e `D51` estão livres e vazias |
| `rigidez_umidade_relativa` | `I51` | rótulo em `H51`; `I51` e `J51` estão livres e vazias |
| `visto_data` | `R57` | `R57:S57` não é mesclada como na linha do executante e `L57` está protegida |

O bloco **Derivação Inicial/Final** (`O18:S43`, 111 células) não gerou campo
algum: `O18:O21`, `O22:O25`, `O26:O29`, `O30:O33` e `O34:O37` são mescladas de
quatro em quatro linhas e, da linha 38 em diante, são células soltas, então a
correspondência entre cada linha e a derivação não está impressa na ficha. A
referência só traz dados nas linhas 41 a 43. As células são esvaziadas na cópia
limpa, mas nada é escrito nelas na exportação.

Também seguem em aberto, por dependerem da ficha física e não do arquivo:

- a `region` de cada campo continua nula (`calibration_status: pending`); o
  recorte por região só funciona depois de calibrar com `calibrate_template_field`;
- `executante_data` e `visto_data` são texto, não data: a referência traz
  `02/0626` e nada é normalizado automaticamente;
- a nomenclatura dos terminais (`E18:E43`) é tratada como fixa; se variar entre
  fichas, ela precisa virar campo;
- a conferência visual final da cópia limpa aberta no Excel, antes de usar o
  modelo em produção.
