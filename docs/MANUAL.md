# Manual de uso e regras de cálculo

## Fluxo recomendado

1. **Casos** → crie o caso, informe seu nome no topo e, se necessário, cadastre os papéis da equipe (leitor, analista, revisor, administrador).
2. **Remessas** → crie uma remessa por resposta de banco (ex.: "Banco X — ofício 12/2026"). Assim as chaves internas de cada banco nunca se misturam.
3. **Importar** → envie o arquivo. O original é guardado sem alteração em `dados/casos/caso_N/originais/` com SHA-256. Arquivo idêntico ao já recebido é recusado.
4. Na prévia, escolha o **tipo de dado**:
   - *Extrato / movimentação* — gera lançamentos e entra nos totais;
   - *Registros de acesso, IP e geolocalização* — nunca vira transação;
   - *Dados cadastrais / titulares* — nunca vira transação;
   - *RIF* — tabelas próprias, nunca vira transação.
5. Confira o mapeamento de cada coluna (as sugestões vêm do nome da coluna ou de um perfil já aprendido), marque a confirmação e importe. Se tiver os valores de controle do documento do banco (total de créditos/débitos/linhas), informe-os: o relatório de importação diz se conferem.
6. **Pesquisar** → clique em cada filtro e marque as opções. Cada lista mostra todos os valores existentes com a quantidade de lançamentos. Dentro de um filtro vale "qualquer um"; entre filtros, "todos".
7. **Duplicatas** → revise os pares apontados antes de usar totais de várias contas/arquivos.
8. **Relatório** → gere o rascunho com os mesmos filtros. Confira a memória de cálculo.

## Regras de cálculo (determinísticas)

- Valores são guardados em **centavos inteiros**; nada é calculado com ponto flutuante.
- Totais incluem somente registros **aceitos** e não consolidados como duplicata confirmada. Pendentes e rejeitados ficam fora, com o motivo.
- **Natureza**: vem da coluna de natureza (C/D), das colunas separadas de crédito e débito, de uma natureza fixa escolhida pelo usuário ou do sinal do valor, este **somente** com confirmação expressa. Sem isso, a linha fica pendente.
- **Status do banco** (ex.: Mercado Pago): só situações reconhecidas como concluídas/aprovadas entram nos totais. Estorno informado deixa a linha pendente; nada é abatido automaticamente.
- **Parcelas de origem/destino** (SIMBA e similares): o valor do lançamento é contado **uma vez**. Se as parcelas somam o valor do lançamento, os rankings usam cada parcela; se divergem ou faltam, o valor vai para "não distribuído" e não é repartido.
- **Conta conjunta**: com mais de um titular/cotitular, o titular aparece como "CONTA CONJUNTA" com todos os nomes; o valor não é dividido entre eles. Representantes e procuradores aparecem à parte e não são titulares.
- **Datas e horas** mantêm a grafia e o fuso de origem. Nada é convertido automaticamente. No leiaute da IN BCB 636/2025, o horário é UTC por definição da norma.
- **Duplicatas prováveis** (nunca descartadas sem decisão de revisor):
  - *conteúdo idêntico* — mesma data, valor, natureza, conta, documento, descrição e contrapartes;
  - *mesma conta, data e valor em outro arquivo/aba* — típico de abas "movimentos" e "PIX" com a mesma operação;
  - *dois lados* — débito numa conta e crédito noutra, mesma data e valor, contraparte = titular da outra conta. Esses permanecem nas respectivas contas, mas o total geral de várias contas pode repetir a operação: o aviso aparece na pesquisa.
- **Filtro de contraparte**: os totais mostram o valor integral dos lançamentos em que ela aparece; o "valor atribuível" (só parcelas conferidas) é informado à parte.

## Pesquisa geral

Reúne identificadores de todas as fontes: extratos (lançamento e origem/destino), cadastros, registros de acesso, RIF e texto de PDF. Um mesmo CPF, nome, IP ou chave PIX em arquivos diferentes é **coincidência a verificar**, não prova de identidade.

## Grafo e sequências

- Grafo agregado: contas dos extratos (azul) e contrapartes (verde); setas na direção dos registros; espessura proporcional ao valor. Ligação roxa = mesmo CPF/CNPJ do titular; amarela = hipótese só por nome.
- **Filtros na própria aba** (pessoa, conta, valor, período, texto, volume mínimo da seta, quantidade máxima de nós). Opcionalmente reutiliza os filtros da Pesquisa.
- **Mover e zoom:** arraste o fundo para deslocar; role o mouse (ou os botões +/−) para aproximar e afastar; ⊡ volta ao enquadramento. Clique no nó para ver o rótulo.
- Sequências: a partir do CPF/CNPJ de um titular, procura débitos a pessoas que são titulares de outras contas do caso e, nessas contas, débitos posteriores dentro da janela de dias com valor até o recebido (mais a tolerância). Cada elo mostra fonte e linha e indica se existe o crédito correspondente na conta de destino. É sempre **possibilidade**: não demonstra que o mesmo dinheiro foi repassado.

## Análise preliminar e chat (aba IA)

1. Importe extratos normalmente. Importe o **boletim de ocorrência** e o **relatório de investigação** como PDF → Extrair texto, marcando o papel (BO / relatório).
2. Na aba **IA e análise**, informe a hipótese (tráfico, estelionato, lavagem ou detectar no texto), a vítima (nome/CPF) e o investigado.
3. **Gerar análise preliminar** calcula, sem Ollama: valores semelhantes, destino do dinheiro da vítima, saques/cartão vs conta de passagem, débito imediato.
4. **Perguntar** abre um chat. Sem modelo, a resposta vem dessa análise. Com Ollama local, o modelo redige neste computador. Com Gemini da parceria (chave + autorização + modelo Gemini no seletor), a pergunta vai à nuvem Google; o programa avisa isso na resposta. Enter envia; Shift+Enter quebra a linha.

## Desfazer e auditoria

- Revisores podem desfazer uma importação: os registros dela são removidos e o original permanece.
- A aba Auditoria lista quem importou, decidiu duplicatas, abriu originais, gerou relatórios, exportou CSV ou perguntou à IA (com o alcance enviado).
- A identificação do usuário é declarada na tela. O controle de acesso real depende do login no computador e das permissões da pasta `dados/`.
