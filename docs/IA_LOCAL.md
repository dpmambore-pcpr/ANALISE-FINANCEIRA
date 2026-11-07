# IA local e como aprimorá-la com novos documentos

## Princípios

- A **análise preliminar** é feita pelo próprio programa (sem modelo e sem internet): cruza extratos, RIF, boletim de ocorrência e relatório de investigação. Na aba **4. Análise** há um campo para anexar BO, relatório, ofício ou outro PDF/TXT e dizer o tipo. Informe vítima e investigado para o estelionato.
- O **chat** funciona mesmo sem Ollama: responde com os achados já calculados (valores semelhantes, destino do dinheiro da vítima, saques/cartão, débito imediato).
- Com Ollama em `http://127.0.0.1` (porta 11434, ou `ANALISE_OLLAMA_PORTA`), o modelo generativo redige em cima desses números, no estilo de um ChatGPT/Claude local. Proxies do sistema são ignorados. Modelos marcados como nuvem (`:cloud`, `-cloud`, `remote_host`) são recusados.
- **Gemini (parceria institucional da Polícia Civil)** é opcional e desligado por padrão. Na aba **4. Análise** há um passo a passo: peça a chave à TI ou, se a TI pedir, gere em [aistudio.google.com/apikey](https://aistudio.google.com/apikey) com a conta institucional; cole, marque a autorização e clique em **Salvar e testar**. Depois escolha um modelo «Gemini · …» no chat. Aí sim trechos do caso (totais, amostra de lançamentos, texto de BO/relatório) saem deste computador para `generativelanguage.googleapis.com` (ou o endpoint Vertex da unidade). A chave fica em `dados/gemini.json` (fora do Git) ou em `ANALISE_GEMINI_CHAVE`. Sem chave, sem autorização ou sem escolher Gemini, nada é enviado ao Google. Falha do Gemini **não** cai em silêncio na análise local: o erro aparece na tela.
- A IA recebe os **números já calculados** pelo programa, a análise preliminar, os filtros, as fontes com SHA-256 e uma amostra limitada de registros. O alcance enviado aparece na tela e na auditoria.
- A resposta é rascunho: confira fonte, página, linha e cálculo.

## O que a análise automática procura

- **Tráfico:** muitos créditos de valores iguais ou próximos (ex.: R$ 50, 100, 150, 200) vindos de várias pessoas; saque ou PIX de saída em seguida.
- **Estelionato:** créditos em que a contraparte é a vítima (informada ou extraída do BO) e, nos dias seguintes na mesma conta, se o valor foi sacado, transferido a terceiro ou gasto no cartão/compras — e se a conta tem uso efetivo (saque, cartão, contas) ou só passa dinheiro.
- **Lavagem / passagem:** crédito com débito imediato (até 24 h, mesmo valor ou próximo); proporção alta de PIX/TED e baixa de gasto pessoal.

Tudo isso é **hipótese de trabalho**, com fonte e linha, não conclusão.

## Gemini da parceria (nuvem, opt-in)

1. Peça a chave à TI da unidade (parceria Gemini da Polícia Civil). Se a TI pediu para gerar no Google AI Studio: abra [aistudio.google.com/apikey](https://aistudio.google.com/apikey), entre com a **conta institucional**, clique em **Create API key** e copie (em geral começa com `AIza`).
2. Na aba **4. Análise**, cole a chave, marque **Autorizo o envio** e clique em **Salvar e testar**. O teste manda só a palavra «ok», sem dados do caso. Endpoint Vertex fica em *Opções avançadas*, só se a TI pedir.
3. Anexe o boletim, o relatório e outros documentos no campo da própria aba (antes de perguntar). Sem eles, o Gemini trabalha só com o extrato e a análise local.
4. No seletor do chat, deixe `Gemini · gemini-2.5-flash` (ou outro). A pergunta então vai à nuvem; o aviso na resposta deixa isso explícito.
5. **Remover chave** apaga `dados/gemini.json` deste computador.

Variáveis (para instalação da unidade, se preferir não colar na tela): `ANALISE_GEMINI_CHAVE`, `ANALISE_GEMINI_ENDPOINT`, `ANALISE_GEMINI_MODELO`. Com a variável da chave definida, o envio já conta como autorizado pelo administrador.

O navegador **não** chama o Google: a política CSP é `connect-src 'self'`. Só o processo Python local, em `127.0.0.1`, faz o HTTPS.

## Preparar o Ollama sem nuvem

Windows: feche o Ollama da bandeja e use `INICIAR_OLLAMA_WINDOWS.bat`, que define `OLLAMA_HOST=127.0.0.1:11434`, `OLLAMA_NO_CLOUD=1` e guarda os modelos em `modelos_ollama/`. Linux: `INICIAR_OLLAMA_LINUX_PORTATIL.sh`. Em outro terminal, com internet só para o download: `ollama pull qwen3:4b-instruct`. Depois, teste com a internet desconectada.

## "Alimentar" a IA com o tempo (sem treinar e sem nuvem)

O modelo não é re-treinado (isso exigiria GPU, muito tempo e cuidados com dados). O programa usa três mecanismos locais e cumulativos:

1. **Base de conhecimento** (aba *Aprimorar a IA*): adicione TXT, MD, CSV ou PDF com texto, como manuais de leiaute dos bancos, normas (Carta-Circular 3.454, IN BCB 636/2025), glossários de históricos bancários, modelos de relatório da unidade e **exemplos anonimizados** de análises. O texto é dividido em trechos e indexado (SQLite FTS5). A cada pergunta, os trechos mais relevantes vão junto ao modelo, com o título do documento. Documentos marcados "somente deste caso" não aparecem em outros casos.
2. **Respostas revisadas**: quando a IA errar, corrija a resposta na própria tela e salve. Nas próximas perguntas parecidas, a correção vai como exemplo do estilo e dos cuidados esperados.
3. **Perfis de leiaute aprendidos**: ao importar um extrato de um banco novo e confirmar o mapeamento, o programa lembra as colunas. No próximo arquivo com o mesmo cabeçalho, o mapeamento já vem preenchido.

Opcional: em *Aprimorar a IA → Baixar Modelfile* você gera um arquivo com as regras do `PROMPT_ANALISE_FINANCEIRA.txt`. Com `ollama create analise-pcpr -f Modelfile`, o Ollama cria localmente um modelo com essas instruções fixas.

## O que NÃO colocar na base geral

Dados reais de pessoas, extratos e RIF de outros casos. Para usar um documento real como referência, deixe-o restrito ao caso ou anonimize-o antes (troque nomes, CPFs, contas e chaves PIX).
