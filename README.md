# Análise Bancária Local — v3

Programa para organizar, pesquisar e conferir extratos bancários, dados SIMBA, RIF, cadastros e registros de acesso/IP/geolocalização **no próprio computador**. A tela abre no navegador, mas tudo roda localmente em `127.0.0.1`. A IA opcional (Ollama) também é local.

> **ATENÇÃO — este repositório é PÚBLICO.** Nunca envie para o GitHub extratos, RIF, ofícios, planilhas de caso, prints ou qualquer dado real. Os dados ficam somente na pasta `dados/` do computador, que é ignorada pelo Git. Os arquivos de `exemplos/` são fictícios.

## Primeira instalação (Windows)

1. Em **Code → Download ZIP** (ou na página *Releases*), baixe o programa e extraia.
2. Se você já tem a pasta `IA_Bancaria_Windows` da versão anterior, **copie a pasta `runtime_windows`** dela para dentro da pasta extraída. Senão, siga `runtime_windows/LEIA.txt` para obter o Python portátil oficial.
3. Dê dois cliques em `INICIAR_WINDOWS.bat`. O navegador abre sozinho; o endereço com a chave da sessão aparece na janela preta.
4. Problemas? Rode `VERIFICAR_WINDOWS.bat` e envie o resultado (ele usa só dados fictícios).

Linux: `chmod +x *.sh && ./INICIAR_LINUX.sh` (usa `runtime_linux/` ou o `python3` do sistema, versão 3.9+).

## Atualizar sem baixar tudo de novo

Dê dois cliques em **`ATUALIZAR_WINDOWS.bat`** (Linux: `./ATUALIZAR_LINUX.sh`). Ele:

- baixa somente o código mais recente deste repositório (ramo `main`, configurável em `atualizacao.json`);
- guarda uma cópia da versão anterior em `backup_versoes/`;
- **não altera** `dados/`, `runtime_windows/`, `runtime_linux/`, `ollama/`, `modelos_ollama/` nem `ferramentas_ocr/`;
- roda os testes no final e avisa se algo falhar.

Sem internet no computador da delegacia: baixe o ZIP em outro computador autorizado e rode `runtime_windows\python.exe atualizar.py --zip CAMINHO\DO\ARQUIVO.zip`.

O atualizador é o único componente que acessa a internet, e só quando você o executa. O programa em si não faz conexões externas.

## O que o programa faz

| Aba | Para quê |
|---|---|
| Importar | Envia CSV/TXT, XLSX, ZIP, PDF. Guarda o original com SHA-256, mostra prévia e **mapeamento visual** de colunas; lembra o mapeamento de cada banco. |
| Pesquisar | **Filtros com lista de todas as opções para marcar**: CPF/CNPJ, nomes (titular e contraparte), contas, bancos, chaves PIX, tipo de operação, descrição, mês, data, IP, cidade, status, arquivo e remessa. Totais, principais origens/destinos, totais por conta, exportação CSV. |
| Pesquisa geral | Lista **tudo** o que foi encontrado em todos os documentos (extratos, cadastros, acessos, RIF, texto de PDF): CPF, CNPJ, nomes, bancos, contas, PIX, ID PIX, e-mails, telefones, IPs, coordenadas, cidades, dispositivos e datas. Marque valores e veja onde cada um aparece (arquivo, página/linha). |
| IP / Geolocalização | Registros de acesso de qualquer banco: IP, porta, data/hora com fuso original, latitude/longitude, cidade, dispositivo; gráfico de dispersão das coordenadas sem mapa da internet. |
| Grafo e repasses | Grafo de relações e sequências de repasses por coincidência de identificador, data e valor, sempre rotuladas como **possibilidade**. |
| Duplicatas | Revisão humana de registros repetidos entre abas/arquivos e dos dois lados de transferências. |
| RIF | Comunicações, envolvidos e ocorrências, **separados** dos extratos e fora dos totais. |
| PDF / OCR | Texto por página, OCR local opcional (Tesseract/Poppler) e revisão por caixa delimitadora. |
| Marcar evidências | Retângulo, círculo e seta sobre página/imagem/captura colada (Ctrl+V); a imagem marcada vai para o relatório. |
| Relatório | DOCX, PDF ou HTML com filtros, alcance, totais, fontes com SHA-256, memória de cálculo com arquivo/linha e ressalvas. |
| Perguntar à IA / Aprimorar a IA | Ollama somente em `127.0.0.1`; base de conhecimento local alimentada com novos documentos e respostas revisadas. Veja [docs/IA_LOCAL.md](docs/IA_LOCAL.md). |

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
runtime_windows/       Python portátil (NÃO vai para o Git)
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
