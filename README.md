# Análise Bancária Local — v3

Programa para organizar, pesquisar e conferir extratos bancários, dados SIMBA, RIF, cadastros e registros de acesso/IP/geolocalização **no próprio computador**. A tela abre no navegador, mas o servidor escuta só em `127.0.0.1`. Fluxo principal: **Importar → Movimentações → Grafo → Análise**. A IA pode ser local (análise automática e Ollama) ou, se a unidade configurar, o Gemini da parceria institucional.

> **ATENÇÃO — este repositório é PÚBLICO.** Nunca envie para o GitHub extratos, RIF, ofícios, planilhas de caso, prints ou qualquer dado real. Os dados ficam somente na pasta `dados/` do computador, que é ignorada pelo Git. Os arquivos de `exemplos/` são fictícios.

## Primeira instalação (Windows)

1. Em **Code → Download ZIP** (ou na página *Releases*), baixe o programa e extraia.
2. O Python portátil (3.14.10, oficial, o mesmo da versão anterior) **já vai junto** na pasta `runtime_windows`: não é preciso instalar Python nem copiar nada. Extraia tudo (botão direito → *Extrair tudo*) e dê dois cliques em `INICIAR_WINDOWS.bat`.
3. Dê dois cliques em `INICIAR_WINDOWS.bat`. O navegador abre sozinho; o endereço com a chave da sessão aparece na janela preta.
4. Problemas? Rode `VERIFICAR_WINDOWS.bat` e envie o resultado (ele usa só dados fictícios).

Linux: `chmod +x *.sh && ./INICIAR_LINUX.sh` (usa `runtime_linux/` ou o `python3` do sistema, versão 3.9+).

## Instalar como aplicativo e receber aviso de nova versão

- **Instalador (recomendado):** em *Actions → instalador → Run workflow* (ou na página *Releases*, quando houver uma versão publicada) baixe `AnaliseBancariaLocal-Instalador-<versão>.exe`. Instala em `%LOCALAPPDATA%\AnaliseBancariaLocal` (sem precisar de administrador), cria atalho na área de trabalho e no Menu Iniciar. O Windows pode mostrar o aviso do SmartScreen porque o instalador não é assinado digitalmente: confira o SHA-256 informado na página e use *Mais informações → Executar assim mesmo*.
- **Sem instalador:** extraia o ZIP e execute `INSTALAR_WINDOWS.bat` (faz o mesmo, usando só recursos do Windows).
- **Atualizar o programa:** ao abrir, se o GitHub tiver versão nova, aparece sozinha a faixa **Este programa está desatualizado** com **Atualizar agora**. Os casos em `dados/` ficam; o programa tenta reabrir sozinho. Nenhum dado de caso é enviado.

## Atualizar sem baixar tudo de novo

Dê dois cliques em **`ATUALIZAR_WINDOWS.bat`** (Linux: `./ATUALIZAR_LINUX.sh`). Ele:

- baixa somente o código mais recente deste repositório (ramo `main`, configurável em `atualizacao.json`);
- guarda uma cópia da versão anterior em `backup_versoes/`;
- **não altera** `dados/`, `runtime_windows/`, `runtime_linux/`, `ollama/`, `modelos_ollama/` nem `ferramentas_ocr/`;
- roda os testes no final e avisa se algo falhar.

Sem internet no computador da delegacia: baixe o ZIP em outro computador autorizado e rode `runtime_windows\python.exe atualizar.py --zip CAMINHO\DO\ARQUIVO.zip`.

Por padrão o programa **não envia dados de caso à internet**. O atualizador consulta só o GitHub (número da versão / pacote). O **Gemini**, se a unidade colar a chave da parceria e o analista escolher um modelo Gemini, envia trechos do caso aos servidores do Google — sempre com a caixa de autorização marcada. Sem isso, nada sai da máquina.

## O que o programa faz

| Aba | Para quê |
|---|---|
| Início | Cria ou escolhe o caso. Quatro passos na tela. |
| 1. Importar | Envia CSV/TXT, XLSX, ZIP, PDF (arquivo ou arrastar). Guarda o original com SHA-256; se for extrato, **os lançamentos já aparecem** em Movimentações. |
| 2. Movimentações | Lista e totais com **filtros de múltipla escolha**: CPF/CNPJ, nomes, contas, bancos, PIX, tipo, descrição, mês, data, IP, cidade, status, arquivo e remessa. |
| Pesquisa geral | Lista **tudo** o que foi encontrado em todos os documentos (extratos, cadastros, acessos, RIF, texto de PDF): CPF, CNPJ, nomes, bancos, contas, PIX, ID PIX, e-mails, telefones, IPs, coordenadas, cidades, dispositivos e datas. Marque valores e veja onde cada um aparece (arquivo, página/linha). |
| IP / Geolocalização | Registros de acesso de qualquer banco: IP, porta, data/hora com fuso original, latitude/longitude, cidade, dispositivo; gráfico de dispersão das coordenadas sem mapa da internet. |
| 3. Grafo | Mapa de transferências **monta sozinho** (contas e quem enviou/recebeu). Arraste pessoas, contas e setas (como no Mercure e no i2); pan e zoom; sequências de repasses rotuladas como **possibilidade**. |
| Duplicatas | Revisão humana de registros repetidos entre abas/arquivos e dos dois lados de transferências. |
| RIF | Comunicações, envolvidos e ocorrências, **separados** dos extratos e fora dos totais. |
| PDF / OCR | Texto por página, OCR local opcional (Tesseract/Poppler) e revisão por caixa delimitadora. |
| Marcar evidências | Retângulo, círculo e seta sobre página/imagem/captura colada (Ctrl+V); a imagem marcada vai para o relatório. |
| Relatório | DOCX, PDF ou HTML com filtros, alcance, totais, fontes com SHA-256, memória de cálculo com arquivo/linha e ressalvas. |
| 4. Análise | Análise preliminar automática ao abrir a aba (tráfico, estelionato, lavagem); campo para anexar **boletim, relatório e outros documentos**; chat local, Ollama em `127.0.0.1`, ou Gemini da parceria (nuvem, opt-in, passo a passo da chave na tela). Veja [docs/IA_LOCAL.md](docs/IA_LOCAL.md). |

Regras de cálculo, leiautes e limitações: [docs/MANUAL.md](docs/MANUAL.md) e [docs/LEIAUTES.md](docs/LEIAUTES.md). Segurança: [docs/SEGURANCA.md](docs/SEGURANCA.md).

## Organização das pastas

```
financeira/            código do programa (Python, só biblioteca padrão)
  web/                 interface (HTML/CSS/JS sem bibliotecas externas)
  perfis_bancos/       perfis de leiaute conhecidos (ex.: Mercado Pago)
ferramentas/           utilitários (gerar exemplos fictícios)
testes/                testes automatizados com dados fictícios
exemplos/              arquivos FICTÍCIOS para treinar o uso
docs/                  manual, leiautes, IA local, segurança, diretrizes da v2
runtime_windows/       Python portátil do Windows (vai junto; origem em ORIGEM_PYTHON_PORTATIL.txt)
vendor/                pypdf (Python puro, opcional) para ler PDFs
legado/                pacote anterior (v2) enviado ao repositório, preservado
ollama/, modelos_ollama/, ferramentas_ocr/   componentes locais opcionais (NÃO vão para o Git)
dados/                 casos, originais e banco SQLite (NUNCA vai para o Git)
```

## Para quem desenvolve

```
python verificar.py                 # ambiente + todos os testes
python ferramentas/gerar_exemplos.py
python iniciar.py --dados /tmp/dados_teste --porta 8765
```

O GitHub Actions roda os testes em Windows e Linux a cada envio (`.github/workflows/testes.yml`).
