# Histórico de versões

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
