# IA local e como aprimorá-la com novos documentos

## Princípios

- O programa só conversa com o Ollama em `http://127.0.0.1` (porta 11434, ou `ANALISE_OLLAMA_PORTA`). Proxies do sistema são ignorados. Modelos marcados como nuvem (`:cloud`, `-cloud`, `remote_host`) são recusados.
- A IA recebe os **números já calculados** pelo programa, os filtros, as fontes com SHA-256 e uma amostra limitada de registros. O alcance enviado aparece na tela e na auditoria.
- A resposta é rascunho: confira fonte, página, linha e cálculo.

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
