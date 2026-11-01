# Leiautes suportados

## SIMBA bruto — Carta-Circular BCB 3.454/2010 (suportado)

Envie um ZIP **por banco/remessa** com `EXTRATO.txt`, `ORIGEM_DESTINO.txt` e, se houver, `TITULARES.txt` (os arquivos `CONTAS`/`AGENCIAS` são guardados e listados). TXT sem cabeçalho, separador TAB, datas `ddmmaaaa`, valores em centavos sem separador.

| Arquivo | Campos | Uso |
|---|---|---|
| EXTRATO | 14 | lançamento (valor, natureza C/D/\*, data, conta, descrição, tipo) |
| ORIGEM_DESTINO | 18 | parcelas de origem/destino ligadas por `CODIGO_CHAVE_EXTRATO` |
| TITULARES | 21 | titulares (T), cotitulares (1, 2, ...), representantes (R/L/P/O) |

Regras aplicadas:
- quantidade de campos diferente da norma bloqueia a importação (sem inferir posições);
- `CODIGO_CHAVE_EXTRATO` repetido, origem/destino sem lançamento ou lançamento sem origem/destino bloqueiam (este último pode ser liberado por opção);
- natureza `*` (bloqueios, provisões etc.) fica pendente, fora dos totais;
- mais de um `EXTRATO.txt` no mesmo ZIP é recusado: um pacote por remessa;
- as chaves só valem dentro da mesma remessa e arquivo.

## SIMBA — IN BCB 636/2025, Anexo I (EXPERIMENTAL)

A norma revoga a Carta-Circular 3.454/2010 e prevê vigência a partir de 01/12/2026. Os campos foram transcritos da norma (EXTRATO 27, ORIGEM_DESTINO 28, TITULARES 28), incluindo `HORARIO_LANCAMENTO` (UTC), `IP_TRANSACAO`, porta, MAC, cidade/UF, interface, tipo e chave PIX, ID PIX (E2E), comentário PIX e dados de boleto. IP e MAC da transação também aparecem na aba IP/Geolocalização.

**Antes de usar em caso real:** confira as posições com o texto da norma e com uma amostra anonimizada vinda de um banco. A importação exige marcar essa confirmação e o relatório registra o aviso "EXPERIMENTAL".

## Planilhas e CSV de bancos (genérico)

Qualquer CSV/TXT (`;` `,` TAB `|`, UTF-8/UTF-16/CP1252) ou XLSX. Na prévia, cada coluna recebe um campo. O programa sugere campos pelo nome da coluna (centenas de sinônimos), e perfis aprendidos têm prioridade.

Perfis embutidos (`financeira/perfis_bancos/`): **Mercado Pago — PIX recebidos/realizados** (`PYN_STATUS`/`PAYOUT_STATUS`, `PAYOUT_TYPE`). Para adicionar um perfil fixo de outro banco, crie um JSON no mesmo formato e envie ao repositório (sem dados reais).

## Registros de acesso, IP e geolocalização

Campos: data/hora, fuso, IP (v4/v6), porta, latitude, longitude ou "lat,long", precisão, cidade, UF, país, endereço, dispositivo/modelo/MAC, sistema/app, evento, nome, CPF/CNPJ, telefone, e-mail, banco, conta. Nada disso vira transação ou entra em totais.

## RIF

CSV/XLSX ou ZIP com as tabelas *Comunicações* (`idComunicacao`, `Data_do_Recebimento`, `nomeComunicante`, `informacoesAdicionais`...), *Envolvidos* (`cpfCnpjEnvolvido`, `nomeEnvolvido`, `tipoEnvolvido`...) e *Ocorrências*. O valor da comunicação só é lido se você indicar a coluna (ex.: `CampoA`) depois de conferir seu significado. PDFs do RIF entram como documento (texto por página), e trechos podem ser registrados como citação com página.

## PDF

Texto selecionável é extraído por página (leitor próprio, sem bibliotecas externas). PDFs digitalizados precisam de OCR local (`ferramentas_ocr/LEIA.txt`). Tabelas em PDF **não** viram lançamentos automaticamente: os identificadores (CPF, PIX, IP, coordenadas etc.) ficam disponíveis na Pesquisa geral com a página.
