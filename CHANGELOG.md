# Histórico de versões

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
