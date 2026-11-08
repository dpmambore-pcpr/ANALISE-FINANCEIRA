# Histórico de versões

## 3.4.10
- **Grafo em tela cheia:** botão **Tela cheia** no mapa (e acima dele) amplia o gráfico na janela inteira. Esc ou **Sair** volta ao tamanho normal.

## 3.4.9
- **Valores das transferências:** em Movimentações e no grafo, lista visível de cada quantia do extrato com **quantos lançamentos** têm aquele valor (ex.: R$ 50,00 — 12 lançamentos). Marque para filtrar.
- **IA no navegador:** botões Abrir no ChatGPT / Claude / Gemini copiam o caso e abrem o site em que você já entra. Não precisa de chave de API (a assinatura do site é outra coisa). Dá para colar a resposta de volta para a IA local aprender.

## 3.4.8
- **Grafo:** os botões Pirâmide, Circular, Torre e Automático ficam **em cima do desenho**. A caixa de cores no canto recolhe e expande.
- **Filtro de valores:** em Movimentações e no grafo, o programa lista cada valor do extrato para marcar.
- **IA simples:** cole a chave do Gemini, ChatGPT ou Claude e use no chat. Sem jargão de TI nem Vertex. A análise local e o Ollama continuam.
- **IA local aprende:** as respostas da nuvem ficam neste computador e entram nas próximas perguntas da IA local.

## 3.4.7
- **Gemini:** o modelo padrão passa a ser `gemini-3.8-flash`. O Google deixou de aceitar `gemini-2.5-flash` para chaves novas; se o teste ou o chat receberem esse recado, o programa tenta o modelo novo sozinho e grava a troca.

## 3.4.6
- **Importar vários de uma vez:** RIF (comunicações, envolvidos, ocorrências) e quebra de bancos — escolha ou arraste vários arquivos; todos entram no mesmo caso. O programa pergunta o destino uma vez e importa em seguida. Os pedaços do RIF viram **um único relatório**.
- **Grafo:** organização em **pirâmide**, **circular**, **torre** (quem enviou à esquerda, quem recebeu à direita) ou **automático**. Setas retas, deslocadas para não se sobrepor; opção de mostrar o valor em todas, só nas maiores, ou ocultar. Clique na seta abre a caixa com origem, destino, valor e quantidade de lançamentos.

## 3.4.5
- **Casos pelo nome do arquivo SIMBA:** `056-PCPR-000677-20` vira **Caso 677**. Palavras genéricas (extrato detalhado, RIF, ofício) não entram no nome; um apelido (elon musk, casa mambore, gordo) vira **Caso 677 elon musk**.
- Ao importar, o programa pergunta se cria um caso novo ou acrescenta a um caso já existente.
- No Início, clique no caso para analisar; marque dois ou mais e use **Analisar juntos** (movimentações, grafo e análise no mesmo recorte).

## 3.4.4
- **Grafo (estilo Mercure / i2):** setas menores; arraste pessoas e contas; puxe o ponto no meio da ligação para curvar a seta. O fundo continua movendo o mapa.

## 3.4.3
- **Análise / Gemini:** na própria aba dá para anexar boletim de ocorrência, relatório de investigação, RIF ou outro documento (PDF, TXT ou MD). O texto entra na análise preliminar e no rascunho de relatório; só vai ao Google se a chave e a autorização do Gemini estiverem ativas.

## 3.4.2
- Ao abrir, o programa consulta o GitHub **sempre**. Se estiver atrasado, aparece uma faixa vermelha **Este programa está desatualizado** com a versão nova e o botão **Atualizar agora** — para quem recebeu uma cópia antiga ver na hora.

## 3.4.1
- **Grafo:** ao marcar uma caixa nos filtros, o mapa atualiza na hora (não precisa clicar em Aplicar). A lista fica aberta para marcar várias.

## 3.4.0
- Interface mais simples para quem não é de informática: abas numeradas (Importar → Movimentações → Grafo → Análise), o restante em **Mais**.
- **Importar:** escolha o arquivo (ou arraste) e os lançamentos aparecem na lista em seguida. Perfil de banco reconhecido já vem com as colunas preenchidas.
- **Análise:** ao abrir a aba, a análise preliminar monta sozinha neste computador (não precisa clicar antes).
- **Gemini:** passo a passo na tela (pedir a chave à TI ou gerar em aistudio.google.com/apikey), um botão **Salvar e testar**, opções de Vertex escondidas.
- **Grafo:** desenha sozinho ao abrir a aba; setas curvas com valor; fundo escuro; estado vazio explicando o que fazer.

## 3.3.2
- Depois de atualizar, a chave de sessão é reaproveitada: a aba do navegador deixa de mostrar «Chave de sessão inválida». Se ainda aparecer, a página explica para fechar a aba velha e abrir pelo atalho.

## 3.3.1
- **Atualizar programa** no topo: um clique consulta o GitHub; se houver versão nova, confirma e baixa; em seguida o programa reabre sozinho. Sem janela preta e sem digitar S. Consulta a API do GitHub (evita cache antigo). `ATUALIZAR_WINDOWS.bat` também aplica sem perguntar.

## 3.3.0
- **Gemini opcional** (parceria institucional da Polícia Civil): chave em `dados/gemini.json` ou `ANALISE_GEMINI_CHAVE`, confirmação explícita de envio e modelo `gemini:` no chat. Desligado por padrão; a análise preliminar continua neste computador. O navegador não fala com o Google (CSP `connect-src 'self'`); só o processo local envia, se autorizado. Destino HTTPS em `googleapis.com` (AI Studio ou Vertex).
- **Atualização:** o botão Verificar mostra a versão instalada e a publicada no GitHub (`main`) e deixa claro que só **Atualizar agora** baixa o pacote.

## 3.2.0
- **Grafo:** filtros na própria tela (pessoa, conta, valor, período, volume mínimo, quantidade de nós), pan (arrastar) e zoom (roda do mouse e botões +/−).
- **Análise preliminar automática** (funciona sem Ollama): BO e relatório de investigação como PDF com papel marcado; hipótese de tráfico (valores semelhantes, muitos remetentes), estelionato (destino do dinheiro da vítima após o crédito, saque/PIX/cartão) e lavagem (débito imediato, conta de passagem vs uso efetivo).
- **Chat da IA:** conversa com histórico; se o Ollama não estiver no ar, o programa responde com a análise calculada. Com Ollama local, o modelo redige em cima desses números. Modelos são verificados ao abrir a aba (não é mais preciso clicar antes de perguntar).
- Relatório pode incluir a análise preliminar já gerada.

## 3.1.1
- Importação de PDF **EXTRATO DETALHADO** (texto selecionável): reconhece o layout, importa os lançamentos com página/linha e confere totais de créditos/débitos de cada conta com os do próprio relatório.

## 3.1.0
- Aviso de nova versão dentro do programa (faixa no topo + botão **Atualizar agora**), com opção de desligar a consulta ao abrir.
- Instalador do Windows (`instalador/AnaliseBancaria.iss`, gerado pelo fluxo `instalador.yml`) e `INSTALAR_WINDOWS.bat`.

## Correções de empacotamento
- O Python portátil do Windows (`runtime_windows`, o mesmo do pacote v2) e o `pypdf` (`vendor/`) agora fazem parte do repositório: o ZIP do GitHub abre sem instalar nada.
- Os `.bat` só aceitam um Python que realmente funcione (o atalho da Microsoft Store não é mais usado por engano) e explicam o que fazer.
- O atualizador restaura `runtime_windows` se ele estiver ausente e continua sem alterar `dados/`.
- Pacote v2 original preservado em `legado/`.

## 3.0.0
- Repositório no GitHub com atualizador que preserva `dados/`, runtime e modelos (`ATUALIZAR_WINDOWS.bat`).
- Pesquisa com **filtros de múltipla escolha** listando todas as opções encontradas (CPF/CNPJ, nomes, contas, bancos, PIX, tipos, datas, IP, cidade, arquivo, remessa), com contagens e busca dentro da lista.
- **Pesquisa geral** em todos os documentos: extratos, cadastros, registros de acesso, RIF e texto de PDF.
- Importação de **registros de acesso / IP / geolocalização** e **cadastros** de qualquer banco, separados das transações.
- SIMBA 2010 (validado) e IN BCB 636/2025 (experimental, com hora UTC, IP, MAC, PIX).
- RIF independente, com citação de página.
- Duplicatas prováveis entre abas/arquivos e dois lados de transferências, com revisão por revisor.
- Grafo de relações e sequências de repasses rotuladas como possibilidade.
- OCR local opcional com revisão por caixa; marcação de evidências; relatórios DOCX/PDF/HTML com memória de cálculo.
- IA local: base de conhecimento alimentável (FTS5), respostas revisadas como exemplos, perfis de leiaute aprendidos, Modelfile.
- Desfazer importação, papéis por caso e trilha de auditoria.
