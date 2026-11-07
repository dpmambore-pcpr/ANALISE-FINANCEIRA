"use strict";
// Interface local. Todas as chamadas vão apenas para o próprio servidor (127.0.0.1).

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const estado = { caso: null, filtros: {}, facetas: [], fontes: [], geralSel: {}, acessosFiltros: {}, previa: null, fonteAtual: null,
  gFiltros: {}, conversaId: null, grafoCtrl: null };

function usuario() { return $("#usuario").value.trim(); }

async function api(metodo, url, corpo, opcoes = {}) {
  const cab = { "X-Requested-With": "analise", "X-Usuario": encodeURIComponent(usuario()) };
  let body;
  if (opcoes.bruto) { body = corpo; Object.assign(cab, opcoes.cabecalhos || {}); }
  else if (corpo !== undefined) { body = JSON.stringify(corpo); cab["Content-Type"] = "application/json"; }
  const r = await fetch(url, { method: metodo, headers: cab, body, credentials: "same-origin" });
  if (opcoes.blob) {
    if (!r.ok) throw new Error((await r.json()).erro || r.statusText);
    return r;
  }
  const tipo = r.headers.get("Content-Type") || "";
  const dados = tipo.includes("json") ? await r.json() : await r.text();
  if (!r.ok) { const e = new Error((dados && dados.erro) || r.statusText); e.dados = dados; throw e; }
  return dados;
}

function msg(el, texto, classe = "erro") { (typeof el === "string" ? $(el) : el).innerHTML = `<div class="${classe}">${esc(texto)}</div>`; }
function exigirCaso() { if (!estado.caso) { alert("Selecione ou crie um caso."); throw new Error("sem caso"); } return estado.caso; }

async function esperarTarefa(id, el) {
  for (;;) {
    const t = await api("GET", `/api/tarefas/${id}`);
    if (el) el.innerHTML = `<span class="nota">Processando: ${esc(t.progresso)}</span>`;
    if (t.estado === "concluida") { if (el) el.innerHTML = ""; return t.resultado; }
    if (t.estado === "erro") { if (el) el.innerHTML = ""; throw new Error(t.erro); }
    await new Promise((ok) => setTimeout(ok, 700));
  }
}

async function baixar(metodo, url, corpo, nomePadrao) {
  const r = await api(metodo, url, corpo, { blob: true });
  const disp = r.headers.get("Content-Disposition") || "";
  const m = disp.match(/filename="([^"]+)"/);
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = m ? m[1] : nomePadrao;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 5000);
}

function modal(html) { $("#modal-corpo").innerHTML = html; $("#modal").classList.remove("oculto"); }
$("#modal-fechar").onclick = () => $("#modal").classList.add("oculto");

// ------------------------------------------------------------------ abas
const ABAS_PRINCIPAIS = new Set(["casos", "importar", "pesquisar", "grafo", "ia", "relatorio"]);
$$("#abas [data-aba]").forEach((b) => (b.onclick = () => abrirAba(b.dataset.aba)));
$("#btn-nav-mais").onclick = (e) => {
  e.stopPropagation();
  const p = $("#nav-mais-painel");
  p.classList.toggle("oculto");
  $("#btn-nav-mais").setAttribute("aria-expanded", p.classList.contains("oculto") ? "false" : "true");
};
function abrirAba(nome) {
  if (!nome) return;
  $$("#abas [data-aba]").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === nome));
  $("#btn-nav-mais").classList.toggle("ativa", !ABAS_PRINCIPAIS.has(nome));
  $("#nav-mais-painel").classList.add("oculto");
  $$(".aba").forEach((s) => s.classList.toggle("ativa", s.id === "aba-" + nome));
  localStorage.setItem("aba", nome);
  const carregar = { fontes: carregarFontes, pesquisar: async () => {
      if (!estado.caso) {
        $("#totais").innerHTML = "";
        $("#resultados").innerHTML = `<div class="vazio"><h3>Selecione um caso no topo</h3><p>Depois importe o extrato — os lançamentos aparecem aqui sozinhos.</p><button type="button" class="primario" data-aba-ir="casos">Ir para o Início</button></div>`;
        return;
      }
      await pesquisar();
    }, duplicatas: carregarDuplicatas,
    rif: carregarRif, documentos: carregarDocs, evidencias: carregarEvidencias, relatorio: carregarRelImagens,
    conhecimento: carregarConhecimento, auditoria: carregarAuditoria, acessos: carregarAcessos, ia: carregarIA,
    grafo: carregarGrafoFiltros, casos: carregarCasos };
  const semCasoOk = nome === "casos" || nome === "conhecimento" || nome === "ia" || nome === "grafo" || nome === "pesquisar";
  if (carregar[nome] && (estado.caso || semCasoOk)) carregar[nome]().catch((e) => console.error(e));
}
document.addEventListener("click", (e) => {
  const ir = e.target.closest("[data-aba-ir]");
  if (ir) { e.preventDefault(); abrirAba(ir.dataset.abaIr); }
  if (!e.target.closest("#nav-mais")) $("#nav-mais-painel")?.classList.add("oculto");
});

// ------------------------------------------------------------------ casos
$("#usuario").value = localStorage.getItem("usuario") || "";
$("#usuario").onchange = () => { localStorage.setItem("usuario", usuario()); carregarCasos(); };
$("#caso").onchange = () => { estado.caso = +$("#caso").value || null; localStorage.setItem("caso", estado.caso || ""); estado.filtros = {}; abrirAba(localStorage.getItem("aba") || "casos"); carregarRemessas(); };

async function carregarCasos() {
  const casos = await api("GET", "/api/casos");
  const sel = $("#caso");
  const salvo = +localStorage.getItem("caso");
  sel.innerHTML = '<option value="">(selecione)</option>' + casos.map((c) => `<option value="${c.id}">${esc(c.nome)}</option>`).join("");
  if (casos.some((c) => c.id === salvo)) { sel.value = salvo; estado.caso = salvo; }
  $("#lista-casos").innerHTML = casos.length ? `<table><tr><th>ID</th><th>Caso</th><th>Criado</th><th>Seu papel</th><th>Fontes</th><th>Lançamentos</th></tr>${
    casos.map((c) => `<tr><td>${c.id}</td><td>${esc(c.nome)}<div class="mini">${esc(c.descricao || "")}</div></td><td>${esc(c.criado_em)} ${esc(c.criado_por || "")}</td><td>${esc(c.papel)}</td><td>${c.n_fontes}</td><td>${c.n_lancamentos}</td></tr>`).join("")}</table>` : '<p class="nota">Nenhum caso ainda. Crie um acima e importe o extrato.</p>';
  const atual = casos.find((c) => c.id === estado.caso);
  const resumo = $("#caso-resumo");
  if (resumo) {
    if (!estado.caso) {
      resumo.innerHTML = `<div class="cartao guia"><h3>Comece por aqui</h3>
        <ol class="passos">
          <li>Escreva seu nome no topo (fica neste computador).</li>
          <li>Crie um caso ou escolha um já existente na lista.</li>
          <li>Vá em <b>1. Importar</b>, escolha o extrato — os lançamentos aparecem em seguida em <b>2. Movimentações</b>.</li>
          <li>Abra <b>3. Grafo</b> e <b>4. Análise</b>: o programa monta sozinho. Gemini é opcional, com passo a passo na própria aba.</li>
        </ol></div>`;
    } else {
      resumo.innerHTML = `<div class="cartao ok"><b>Caso selecionado: ${esc(atual ? atual.nome : "")}</b>
        <p>${atual ? atual.n_fontes : 0} arquivo(s), ${atual ? atual.n_lancamentos : 0} lançamento(s).</p>
        <div class="proximos">
          <button type="button" class="primario" data-aba-ir="importar">Importar extrato</button>
          <button type="button" data-aba-ir="pesquisar">Ver movimentações</button>
          <button type="button" data-aba-ir="grafo">Ver grafo</button>
          <button type="button" data-aba-ir="ia">Ver análise</button>
        </div></div>`;
    }
  }
  $("#perm-lista").innerHTML = atual ? (atual.permissoes.length ? atual.permissoes.map((p) => `<span class="chips"><span>${esc(p.usuario)}: ${esc(p.papel)}</span></span>`).join("") : '<span class="nota">Sem restrição (todos administradores).</span>') : "";
  carregarRemessas();
}
$("#btn-criar-caso").onclick = async () => {
  try {
    const r = await api("POST", "/api/casos", { nome: $("#novo-caso-nome").value, descricao: $("#novo-caso-desc").value });
    localStorage.setItem("caso", r.id); $("#novo-caso-nome").value = ""; await carregarCasos();
  } catch (e) { alert(e.message); }
};
$("#btn-perm").onclick = async () => {
  try { await api("POST", `/api/casos/${exigirCaso()}/permissoes`, { usuario: $("#perm-usuario").value, papel: $("#perm-papel").value }); carregarCasos(); }
  catch (e) { alert(e.message); }
};
async function carregarRemessas() {
  if (!estado.caso) return;
  const rs = await api("GET", `/api/casos/${estado.caso}/remessas`);
  $("#rem-lista").innerHTML = rs.map((r) => `<div>#${r.id} ${esc(r.rotulo)} - ${esc(r.instituicao || "")}</div>`).join("");
  $("#imp-remessa").innerHTML = '<option value="">(sem remessa)</option>' + rs.map((r) => `<option value="${r.id}">${esc(r.rotulo)}</option>`).join("");
}
$("#btn-remessa").onclick = async () => {
  try { await api("POST", `/api/casos/${exigirCaso()}/remessas`, { rotulo: $("#rem-rotulo").value, instituicao: $("#rem-inst").value }); carregarRemessas(); }
  catch (e) { alert(e.message); }
};

// ------------------------------------------------------------------ importar
async function enviarArquivo(arq, remessa) {
  return api("POST", `/api/casos/${exigirCaso()}/upload`, arq, { bruto: true, cabecalhos: { "X-Nome-Arquivo": encodeURIComponent(arq.name), "X-Remessa": remessa || "" } });
}
$("#imp-arquivo").addEventListener("change", () => {
  if ($("#imp-arquivo").files[0]) $("#btn-enviar").click();
});
function ligarSoltar() {
  const zona = $("#imp-soltar");
  if (!zona) return;
  ["dragenter", "dragover"].forEach((ev) => zona.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.add("sobre"); }));
  ["dragleave", "drop"].forEach((ev) => zona.addEventListener(ev, (e) => { e.preventDefault(); zona.classList.remove("sobre"); }));
  zona.addEventListener("drop", (e) => {
    const f = e.dataTransfer.files[0];
    if (!f) return;
    const dt = new DataTransfer();
    dt.items.add(f);
    $("#imp-arquivo").files = dt.files;
    $("#imp-arquivo").dispatchEvent(new Event("change"));
  });
}
$("#btn-enviar").onclick = async () => {
  const arq = $("#imp-arquivo").files[0];
  if (!arq) return alert("Escolha um arquivo.");
  $("#imp-relatorio").innerHTML = "";
  $("#imp-progresso").innerHTML = '<span class="nota">Enviando e calculando SHA-256...</span>';
  try {
    const f = await enviarArquivo(arq, $("#imp-remessa").value);
    $("#imp-progresso").innerHTML = `<div class="ok">Original guardado: ${esc(f.nome_original)} - SHA-256 ${esc(f.sha256)}</div>`;
    await prepararImportacao(f.id);
  } catch (e) {
    if (e.dados && e.dados.fonte) { $("#imp-progresso").innerHTML = `<div class="aviso">${esc(e.message)}</div>`; await prepararImportacao(e.dados.fonte.id); }
    else msg("#imp-progresso", e.message);
  }
};

async function prepararImportacao(fonteId, aba, linhaCab) {
  abrirAba("importar");
  estado.fonteAtual = fonteId;
  const p = await api("POST", `/api/fontes/${fonteId}/previa`, { aba, linha_cabecalho: linhaCab });
  estado.previa = p;
  const alvo = $("#imp-previa");
  if (p.tipo_arquivo === "zip") return mostrarZip(fonteId, p.conteudo, alvo);
  if (p.tipo_arquivo === "pdf" && p.extrato_detalhado) {
    const ed = p.extrato_detalhado;
    alvo.innerHTML = `<div class="cartao"><h3>PDF reconhecido: EXTRATO DETALHADO</h3>
      <p>Foram encontradas <b>${ed.contas.length}</b> conta(s) e <b>${ed.lancamentos}</b> lançamento(s)${ed.nao_reconhecidas ? `, além de <b>${ed.nao_reconhecidas}</b> linha(s) com data que não pôde ser interpretada (ficarão pendentes)` : ""}.</p>
      <table><tr><th>Titular</th><th>CPF/CNPJ</th><th>Banco</th><th>Ag.</th><th>Conta</th><th>Tipo</th><th>Lanç.</th><th>Créditos</th><th>Débitos</th></tr>
      ${ed.contas.map((c) => `<tr><td>${esc(c.titular)}</td><td>${esc(c.doc)}</td><td>${esc(c.banco)} ${esc(c.banco_nome)}</td><td>${esc(c.agencia)}</td><td>${esc(c.conta)}</td><td>${esc(c.tipo)}</td><td>${c.lancamentos}</td><td>${esc(c.creditos)}</td><td>${esc(c.debitos)}</td></tr>`).join("")}</table>
      <p class="aviso">Este relatório é gerado por sistema de análise, não é o documento original do banco. Os totais de créditos/débitos de cada conta serão conferidos com os informados no próprio PDF.</p>
      <button class="primario" id="btn-imp-pdf-ext">Importar lançamentos deste extrato</button>
      <label>Se for só texto: papel <select id="pdf-papel"><option value="documento">documento</option><option value="boletim">boletim de ocorrência</option><option value="relatorio_investigacao">relatório de investigação</option></select></label>
      <button id="btn-imp-pdf">Somente extrair o texto (Pesquisa geral)</button></div>`;
    $("#btn-imp-pdf-ext").onclick = () => executarImportacao(fonteId, "pdf_extrato", null, {});
    $("#btn-imp-pdf").onclick = () => executarImportacao(fonteId, "pdf_texto", null, { papel: $("#pdf-papel").value });
    return;
  }
  if (p.tipo_arquivo === "pdf") {
    alvo.innerHTML = `<div class="cartao"><h3>PDF</h3>${p.aviso_leitura ? `<div class="erro">${esc(p.aviso_leitura)}</div>` : ""}<p>O texto selecionável será extraído por página e os identificadores (CPF, PIX, IP...) ficarão disponíveis na Pesquisa geral. Marque o papel do documento para a análise preliminar (BO, relatório de investigação, RIF).</p>
      <p class="nota">OCR local: ${p.ocr.disponivel ? "disponível" : "não instalado (veja ferramentas_ocr/LEIA.txt)"}</p>
      <label>Papel <select id="pdf-papel">
        <option value="documento">Documento (texto)</option>
        <option value="boletim">Boletim de ocorrência</option>
        <option value="relatorio_investigacao">Relatório de investigação</option>
        <option value="rif">RIF em PDF</option>
      </select></label>
      <button class="primario" id="btn-imp-pdf">Extrair texto</button></div>`;
    $("#btn-imp-pdf").onclick = () => {
      const papel = $("#pdf-papel").value;
      executarImportacao(fonteId, "pdf_texto", null, { papel, rif: papel === "rif" });
    };
    return;
  }
  if (!p.cabecalho) { alvo.innerHTML = '<div class="erro">Tipo de arquivo não suportado para importação. O original continua guardado como fonte.</div>'; return; }
  renderMapeamento(fonteId, p, alvo);
}

function mostrarZip(fonteId, c, alvo) {
  let html = `<div class="cartao"><h3>Conteúdo do pacote ZIP</h3><p class="nota">A listagem não significa que os arquivos foram analisados. Prepare cada arquivo individualmente. Dados cadastrais, planilhas de IP e geolocalização devem ser importados como "cadastro" ou "acessos", nunca como transações.</p>`;
  if (c.simba) html += `<div class="ok">Conjunto SIMBA detectado: ${esc(c.simba.descricao)} - arquivos ${esc(Object.values(c.simba.arquivos).join(", "))}</div>
     ${c.simba.leiaute === "2026" ? '<label><input type="checkbox" id="zip-in636"> Conferi as posições do leiaute IN BCB 636/2025 com a norma e com amostra anonimizada (leitura experimental)</label><br>' : ""}
     <label><input type="checkbox" id="zip-semod"> Importar lançamentos sem ORIGEM_DESTINO (a norma prevê ao menos um)</label><br>
     <button class="primario" id="btn-zip-simba">Importar SIMBA deste pacote</button>`;
  else if (c.simba_erro) html += `<div class="aviso">SIMBA: ${esc(c.simba_erro)}</div>`;
  if (c.rif) html += `<div class="ok">Parece um RIF (comunicações/envolvidos). <input id="zip-rif-num" placeholder="nº do RIF"> <input id="zip-rif-valor" placeholder="coluna de valor (ex.: CampoA), se conferida"> <button class="primario" id="btn-zip-rif">Importar como RIF</button></div>`;
  html += `<table><tr><th>Arquivo</th><th>Tipo</th><th>Bytes</th><th></th></tr>${c.itens.map((i) =>
    `<tr><td>${esc(i.nome)}</td><td>${esc(i.tipo)}</td><td class="num">${i.tamanho}</td><td><button data-membro="${esc(i.nome)}">Preparar para importar</button></td></tr>`).join("")}</table></div>`;
  alvo.innerHTML = html;
  if ($("#btn-zip-simba")) $("#btn-zip-simba").onclick = () => executarImportacao(fonteId, "simba", null, { confirmo_leiaute_in636: $("#zip-in636")?.checked, permitir_extrato_sem_od: $("#zip-semod").checked });
  if ($("#btn-zip-rif")) $("#btn-zip-rif").onclick = () => executarImportacao(fonteId, "rif", null, { numero_rif: $("#zip-rif-num").value, coluna_valor: $("#zip-rif-valor").value || null });
  $$("button[data-membro]", alvo).forEach((b) => (b.onclick = async () => {
    try { const f = await api("POST", `/api/fontes/${fonteId}/extrair`, { membro: b.dataset.membro }); await prepararImportacao(f.id); }
    catch (e) { alert(e.message); }
  }));
}

const ROTULO_TIPO = { extrato: "Extrato / movimentação financeira", acessos: "Registros de acesso, IP e geolocalização", cadastro: "Dados cadastrais / titulares", rif: "RIF (comunicações/envolvidos/ocorrências)" };

function renderMapeamento(fonteId, p, alvo) {
  const tipo = p.tipo_sugerido === "rif" ? "rif" : p.tipo_sugerido;
  let html = `<div class="cartao"><h3>Pré-visualização e mapeamento visual</h3>`;
  if (p.abas && p.abas.length) html += `<label>Aba <select id="m-aba">${p.abas.map((a) => `<option ${a === p.aba ? "selected" : ""}>${esc(a)}</option>`).join("")}</select></label> `;
  html += `<label>Linha do cabeçalho <input id="m-cab" size="3" value="${p.linha_cabecalho ?? ""}"></label> <button id="m-recarregar">Recarregar</button>
    <label>Tipo de dado <select id="m-tipo">${Object.entries(ROTULO_TIPO).map(([k, v]) => `<option value="${k}" ${k === tipo ? "selected" : ""}>${v}</option>`).join("")}</select></label>`;
  if (p.perfil) html += `<div class="ok">Perfil reconhecido: ${esc(p.perfil.nome)} (${esc(p.perfil.origem)}).${(p.perfil.observacoes || []).map((o) => `<br>• ${esc(o)}`).join("")}</div>`;
  html += `<div id="m-tabela"></div><div id="m-opcoes"></div></div>`;
  alvo.innerHTML = html;
  const desenhar = () => {
    const t = $("#m-tipo").value;
    if (t === "rif") {
      $("#m-tabela").innerHTML = tabelaAmostra(p, null);
      $("#m-opcoes").innerHTML = `<p>RIF: as colunas são reconhecidas pelo nome (idComunicacao, cpfCnpjEnvolvido...). Comunicações não viram lançamentos.</p>
        <input id="rif-num" placeholder="nº do RIF"> <label>Coluna de valor (se conferida) <select id="rif-valor"><option value="">(nenhuma)</option>${p.cabecalho.map((h) => `<option>${esc(h)}</option>`).join("")}</select></label>
        <button class="primario" id="m-importar">Importar RIF</button>`;
      $("#m-importar").onclick = () => executarImportacao(fonteId, "rif", null, { numero_rif: $("#rif-num").value, coluna_valor: $("#rif-valor").value || null });
      return;
    }
    const campos = p.campos[t];
    const sug = p.sugestoes[t] || {};
    const porColuna = {};
    Object.entries(sug).forEach(([campo, col]) => (porColuna[col] = campo));
    $("#m-tabela").innerHTML = tabelaAmostra(p, (h) => `<select data-col="${esc(h)}"><option value="">(ignorar)</option>${campos.map((c) => `<option value="${c.campo}" ${porColuna[h] === c.campo ? "selected" : ""}>${esc(c.rotulo)}</option>`).join("")}</select>`);
    let op = "";
    if (t === "extrato") op += `<div class="cartao"><b>Natureza</b><br>
      <label>Natureza fixa <select id="o-natfixa"><option value="">(usar coluna Natureza ou Crédito/Débito)</option><option value="C">CRÉDITO para todas as linhas</option><option value="D">DÉBITO para todas as linhas</option></select></label><br>
      <label><input type="checkbox" id="o-sinal"> Confirmo que neste arquivo valor positivo = crédito e negativo = débito</label>
      <p class="nota">Sem essa confirmação, o sinal não é usado e a linha fica pendente. Situações (status) só entram nos totais se reconhecidas como concluídas/aprovadas. Valores de estorno ficam pendentes para revisão.</p>
      <b>Valores de controle (do documento do banco, opcional)</b><br>
      <label>Créditos <input id="o-cc" size="10"></label> <label>Débitos <input id="o-cd" size="10"></label> <label>Qtde. de linhas <input id="o-cq" size="5"></label></div>`;
    op += `<label>Instituição (se não houver coluna) <input id="o-inst"></label>
      <label><input type="checkbox" id="o-perfil" checked> Lembrar este mapeamento para arquivos com o mesmo cabeçalho</label> <input id="o-perfil-nome" placeholder="nome do perfil (ex.: Banco X - extrato)">
      ${t === "extrato" ? `<br><label><input type="checkbox" id="o-conf" ${p.perfil ? "checked" : ""}> Confirmo que conferi as colunas e que este arquivo contém movimentações</label>` : ""}
      <br><button class="primario" id="m-importar">${p.perfil ? "Importar agora" : "Confirmar e importar"}</button>`;
    $("#m-opcoes").innerHTML = op;
    if (p.perfil && t === "extrato") {
      $("#m-opcoes").insertAdjacentHTML("afterbegin", '<div class="ok">O programa já reconheceu este banco e preencheu as colunas. Confira a tabela e clique em <b>Importar agora</b> — os lançamentos aparecem em seguida.</div>');
    }
    $("#m-importar").onclick = () => {
      if (t === "extrato" && !$("#o-conf").checked) return alert("Marque a confirmação de conferência das colunas.");
      const mapeamento = {};
      $$("#m-tabela select[data-col]").forEach((s) => { if (s.value) mapeamento[s.value] = s.dataset.col; });
      const opcoes = { aba: $("#m-aba")?.value, linha_cabecalho: +$("#m-cab").value || null, instituicao: $("#o-inst").value || null,
        salvar_perfil: $("#o-perfil").checked, nome_perfil: $("#o-perfil-nome").value || null };
      if (t === "extrato") Object.assign(opcoes, { natureza_fixa: $("#o-natfixa").value || null, sinal_credito: $("#o-sinal").checked,
        controle: { creditos: $("#o-cc").value, debitos: $("#o-cd").value, quantidade: $("#o-cq").value } });
      executarImportacao(fonteId, t, mapeamento, opcoes);
    };
  };
  $("#m-tipo").onchange = desenhar;
  $("#m-recarregar").onclick = () => prepararImportacao(fonteId, $("#m-aba")?.value, +$("#m-cab").value || null);
  if ($("#m-aba")) $("#m-aba").onchange = () => prepararImportacao(fonteId, $("#m-aba").value, null);
  desenhar();
}

function tabelaAmostra(p, seletor) {
  return `<div style="overflow:auto"><table><tr><th>Linha</th>${p.cabecalho.map((h) => `<th class="mapa-col">${esc(h)}${seletor ? "<br>" + seletor(h) : ""}</th>`).join("")}</tr>${
    p.amostra.map((a) => `<tr><td>${a.linha}</td>${p.cabecalho.map((_, i) => `<td>${esc(a.campos[i] ?? "")}</td>`).join("")}</tr>`).join("")}</table></div>`;
}

async function executarImportacao(fonteId, adaptador, mapeamento, opcoes) {
  const el = $("#imp-relatorio");
  el.innerHTML = '<span class="nota">Importando...</span>';
  try {
    const r = await api("POST", `/api/fontes/${fonteId}/importar`, { adaptador, mapeamento, opcoes });
    const rel = await esperarTarefa(r.tarefa, el);
    el.innerHTML = htmlRelatorioImportacao(rel) + htmlProximosPassos(rel);
    estado.facetas = [];
    if ((rel.aceitos || 0) > 0) {
      try {
        await pesquisar();
        abrirAba("pesquisar");
        const t = $("#totais");
        if (t) t.insertAdjacentHTML("afterbegin", `<div class="ok">Arquivo importado: <b>${rel.aceitos}</b> lançamento(s) já estão na lista abaixo. O grafo e a análise montam sozinhos nas etapas 3 e 4.</div>`);
      } catch (e) { console.error(e); }
    }
  } catch (e) { msg(el, e.message); }
}
function htmlProximosPassos(rel) {
  const n = rel.aceitos || 0;
  return `<div class="cartao"><h3>Pronto</h3>
    <p>${n ? n + " lançamento(s) já estão no caso." : "O arquivo foi guardado. Se for PDF de texto, use a Pesquisa geral ou a Análise depois de marcar o papel."}</p>
    <div class="proximos">
      ${n ? '<button type="button" class="primario" data-aba-ir="pesquisar">Ver movimentações</button><button type="button" data-aba-ir="grafo">Ver grafo</button><button type="button" data-aba-ir="ia">Gerar análise</button>' : '<button type="button" class="primario" data-aba-ir="fontes">Ver fontes</button>'}
    </div></div>`;
}

function htmlRelatorioImportacao(rel) {
  const brl = (c) => (c / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  let h = `<div class="cartao"><h3>Relatório de importação #${rel.importacao_id}</h3><div class="totais">
    <div>Aceitos<b>${rel.aceitos}</b></div><div>Pendentes (fora dos totais)<b>${rel.pendentes}</b>${rel.totais_pendentes ? brl(rel.totais_pendentes) : ""}</div>
    <div>Rejeitados<b>${rel.rejeitados}</b></div><div>Duplicatas prováveis<b>${rel.duplicatas}</b></div>
    <div>Créditos aceitos<b>${brl(rel.totais_aceitos.C)}</b></div><div>Débitos aceitos<b>${brl(rel.totais_aceitos.D)}</b></div>
    ${rel.acessos ? `<div>Registros de acesso<b>${rel.acessos}</b></div>` : ""}${rel.titulares ? `<div>Cadastros/titulares<b>${rel.titulares}</b></div>` : ""}
    ${rel.paginas ? `<div>Páginas de PDF<b>${rel.paginas}</b></div>` : ""}</div>`;
  const pc = rel.parcelas || {};
  if (pc.conferidas || pc.divergentes || pc.incompletas) h += `<p class="nota">Parcelas de origem/destino: ${pc.conferidas || 0} conferidas, ${pc.divergentes || 0} divergentes, ${pc.incompletas || 0} sem valor por parcela, ${pc.unica || 0} contraparte única.</p>`;
  if (rel.controle) h += `<div class="${rel.controle.ok ? "ok" : "erro"}"><b>Valores de controle: ${rel.controle.ok ? "CONFEREM" : "DIVERGEM"}</b>${rel.controle.itens.map((i) => `<br>${esc(i.item)}: esperado ${esc(i.esperado)}, obtido ${esc(i.obtido)} ${i.ok ? "✓" : "✗"}`).join("")}</div>`;
  (rel.avisos || []).forEach((a) => (h += `<div class="aviso">${esc(a)}</div>`));
  const motivos = Object.entries(rel.motivos || {});
  if (motivos.length) h += `<h3>Motivos de pendência/rejeição</h3><table><tr><th>Motivo</th><th>Linhas</th></tr>${motivos.map(([m, n]) => `<tr><td>${esc(m)}</td><td>${n}</td></tr>`).join("")}</table>`;
  if ((rel.linhas_problema || []).length) h += `<details><summary>Linhas com problema (${rel.linhas_problema.length})</summary><table><tr><th>Local</th><th>Linha</th><th>Situação</th><th>Motivo</th></tr>${rel.linhas_problema.map((l) => `<tr><td>${esc(l.local || "")}</td><td>${l.linha}</td><td>${esc(l.situacao)}</td><td>${esc(l.motivo)}</td></tr>`).join("")}</table></details>`;
  return h + "</div>";
}

// ------------------------------------------------------------------ fontes
async function carregarFontes() {
  const fs = await api("GET", `/api/casos/${exigirCaso()}/fontes`);
  estado.fontes = fs;
  $("#fontes-lista").innerHTML = `<table><tr><th>ID</th><th>Arquivo</th><th>Tipo</th><th>SHA-256</th><th>Remessa</th><th>Importações</th><th></th></tr>${fs.map((f) => `<tr>
    <td>${f.id}</td><td>${esc(f.caminho_no_pacote || f.nome_original)}${f.pai_id ? `<div class="mini">dentro da fonte ${f.pai_id}</div>` : ""}<div class="mini">${esc(f.criado_em)} ${esc(f.criado_por || "")}</div></td>
    <td>${esc(f.tipo)}</td><td class="mini" style="font-family:monospace">${esc(f.sha256)}</td><td>${esc(f.remessa || "")}</td>
    <td>${f.importacoes.map((i) => `<div>#${i.id} ${esc(i.adaptador)}${i.leiaute ? " " + esc(i.leiaute) : ""} ${esc(i.local || "")}: ${i.aceitos} aceitos, ${i.pendentes} pend., ${i.rejeitados} rej., ${i.duplicatas} dup. <b>${esc(i.estado)}</b>
      <button data-rel="${i.id}">relatório</button>${i.estado === "concluida" ? `<button data-desf="${i.id}">desfazer</button>` : ""}</div>`).join("")}</td>
    <td><button data-prep="${f.id}">${f.tipo === "zip" ? "Ver conteúdo" : "Preparar para importar"}</button> <button data-orig="${f.id}">original</button></td></tr>`).join("")}</table>`;
  $$("button[data-prep]").forEach((b) => (b.onclick = () => prepararImportacao(+b.dataset.prep)));
  $$("button[data-orig]").forEach((b) => (b.onclick = () => window.open(`/api/fontes/${b.dataset.orig}/original`, "_blank")));
  $$("button[data-rel]").forEach((b) => (b.onclick = async () => { const r = await api("GET", `/api/importacoes/${b.dataset.rel}`); modal(htmlRelatorioImportacao(Object.assign(r.relatorio, { importacao_id: r.id }))); }));
  $$("button[data-desf]").forEach((b) => (b.onclick = async () => {
    if (!confirm("Desfazer a importação? Os registros dela serão removidos (o original permanece). Exige papel revisor.")) return;
    try { await api("POST", `/api/importacoes/${b.dataset.desf}/desfazer`); carregarFontes(); } catch (e) { alert(e.message); }
  }));
}
$("#btn-integridade").onclick = async () => {
  const r = await api("GET", `/api/casos/${exigirCaso()}/integridade`);
  modal(`<h3>Integridade dos originais</h3>${r.map((x) => `<div class="${x.ok ? "ok" : "erro"}">${esc(x.nome)}: ${x.ok ? "SHA-256 confere" : "NÃO CONFERE ou arquivo ausente"}</div>`).join("")}`);
};

// ------------------------------------------------------------------ componente de faceta (lista para marcar)
function criarFaceta(container, faceta, selecionados, aoMudar, opcoes) {
  const aoVivo = !!(opcoes && opcoes.aoVivo);
  const div = document.createElement("div");
  div.className = "faceta";
  const sel = new Set(selecionados || []);
  const botao = document.createElement("button");
  const atualizarBotao = () => {
    botao.textContent = `${faceta.rotulo} (${faceta.valores.length}${faceta.truncado ? "+" : ""})${sel.size ? " • " + sel.size + " marcado(s)" : ""} ▾`;
    botao.classList.toggle("com-selecao", sel.size > 0);
  };
  const avisar = () => { atualizarBotao(); if (aoVivo) aoMudar([...sel]); };
  atualizarBotao();
  div.appendChild(botao);
  let painel = null;
  botao.onclick = (ev) => {
    ev.stopPropagation();
    if (painel) { painel.remove(); painel = null; return; }
    $$(".faceta-painel").forEach((p) => p.remove());
    painel = document.createElement("div");
    painel.className = "faceta-painel";
    painel.onclick = (e) => e.stopPropagation();
    painel.innerHTML = `<div class="topo"><input placeholder="digite para filtrar a lista"><button data-a="todos">Marcar visíveis</button><button data-a="nenhum">Limpar</button><button data-a="ok" class="primario">${aoVivo ? "Fechar" : "Aplicar"}</button></div>
      ${aoVivo ? '<p class="nota faceta-dica">Pode marcar várias. Cada caixa já aplica.</p>' : ""}
      <div class="lista"></div>`;
    const lista = $(".lista", painel);
    const busca = $("input", painel);
    const desenhar = () => {
      const t = busca.value.toLowerCase();
      const vis = faceta.valores.filter((v) => !t || String(v.rotulo).toLowerCase().includes(t) || String(v.valor).toLowerCase().includes(t));
      const max = 1500;
      lista.innerHTML = vis.slice(0, max).map((v, i) => `<label><input type="checkbox" data-i="${faceta.valores.indexOf(v)}" ${sel.has(v.valor) ? "checked" : ""}> <span>${esc(v.rotulo)}${v.origens ? `<div class="mini">${esc(v.origens.join(", "))}</div>` : ""}</span><span class="n">${v.n}${v.soma != null ? " · " + (v.soma / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) : ""}</span></label>`).join("")
        + (vis.length > max ? `<div class="nota">Mostrando ${max} de ${vis.length}. Digite para filtrar.</div>` : "")
        + (!vis.length ? '<div class="nota">Nenhum valor.</div>' : "");
      $$("input[type=checkbox]", lista).forEach((cb) => (cb.onchange = () => {
        const v = faceta.valores[+cb.dataset.i].valor;
        cb.checked ? sel.add(v) : sel.delete(v);
        avisar();
      }));
      return vis;
    };
    let visiveis = desenhar();
    busca.oninput = () => (visiveis = desenhar());
    painel.querySelector('[data-a="todos"]').onclick = () => { visiveis.forEach((v) => sel.add(v.valor)); visiveis = desenhar(); avisar(); };
    painel.querySelector('[data-a="nenhum"]').onclick = () => { sel.clear(); visiveis = desenhar(); avisar(); };
    painel.querySelector('[data-a="ok"]').onclick = () => { painel.remove(); painel = null; if (!aoVivo) aoMudar([...sel]); };
    div.appendChild(painel);
    busca.focus();
  };
  container.appendChild(div);
}
document.addEventListener("click", () => $$(".faceta-painel").forEach((p) => p.remove()));

// ------------------------------------------------------------------ pesquisar
function lerFiltrosSimples() {
  const f = estado.filtros;
  f.data_ini = $("#f-data-ini").value || null; f.data_fim = $("#f-data-fim").value || null;
  f.valor_min = $("#f-vmin").value || null; f.valor_max = $("#f-vmax").value || null; f.texto = $("#f-texto").value || null;
  return f;
}
async function carregarFacetas() {
  const facs = await api("POST", `/api/casos/${exigirCaso()}/facetas`, { filtros: lerFiltrosSimples() });
  estado.facetas = facs;
  const cont = $("#facetas");
  cont.innerHTML = "";
  facs.forEach((f) => criarFaceta(cont, f, estado.filtros[f.chave], (vals) => { estado.filtros[f.chave] = vals; pesquisar(); }));
}
async function pesquisar(deslocamento = 0) {
  const caso = exigirCaso();
  const r = await api("POST", `/api/casos/${caso}/pesquisa`, { filtros: lerFiltrosSimples(), deslocamento, limite: 500 });
  $("#filtros-ativos").innerHTML = r.filtros_descricao.map((d) => `<span>${esc(d)}</span>`).join("");
  const t = r.totais;
  let h = `<div class="totais"><div>Créditos aceitos<b>${t.creditos_fmt}</b>${t.n_creditos} lançamentos</div><div>Débitos aceitos<b>${t.debitos_fmt}</b>${t.n_debitos} lançamentos</div>
    <div>Pendentes (fora dos totais)<b>${t.pendentes_fmt}</b>${t.n_pendentes} registros</div><div>Rejeitados<b>${t.n_rejeitados}</b></div>
    <div>Período<b style="font-size:14px">${esc(t.periodo[0] || "-")} a ${esc(t.periodo[1] || "-")}</b>${t.n_fontes} arquivo(s)</div></div>`;
  t.avisos.forEach((a) => (h += `<div class="aviso">${esc(a)}</div>`));
  const rk = (titulo, x) => `<div><h3>${titulo}</h3><table><tr><th>Contraparte</th><th>CPF/CNPJ</th><th>Lanç.</th><th>Valor</th></tr>${x.itens.map((i) => `<tr><td>${esc(i.nome || "?")}</td><td>${esc(i.doc || "")}</td><td>${i.n}</td><td class="num">${i.soma_fmt}</td></tr>`).join("")}
    <tr><td colspan="3" class="mini">Não distribuído (parcelas divergentes/incompletas)</td><td class="num">${x.nao_distribuido.soma_fmt}</td></tr><tr><td colspan="3" class="mini">Sem contraparte identificada</td><td class="num">${x.sem_contraparte.soma_fmt}</td></tr></table></div>`;
  h += `<div class="duas">${rk("Principais origens (créditos)", t.origens)}${rk("Principais destinos (débitos)", t.destinos)}</div>`;
  if (t.por_conta.length > 1) h += `<details><summary>Totais por conta (${t.por_conta.length})</summary><table><tr><th>Conta</th><th>Titular</th><th>Créditos</th><th>Débitos</th><th>Registros</th></tr>${t.por_conta.map((c) => `<tr><td>${esc(c.conta)}</td><td>${esc(c.titular || "")}</td><td class="num">${c.c_fmt}</td><td class="num">${c.d_fmt}</td><td>${c.n}</td></tr>`).join("")}</table></details>`;
  $("#totais").innerHTML = h;
  let tab = `<p class="nota">${r.total} registro(s); mostrando ${r.deslocamento + 1}-${r.deslocamento + r.linhas.length}. ${r.total > r.deslocamento + r.linhas.length ? '<button id="btn-mais">Próximos 500</button>' : ""} ${r.deslocamento ? '<button id="btn-menos">Anteriores</button>' : ""}</p>
    <table><tr><th>Data</th><th>Nat.</th><th>Valor</th><th>Titular / conta</th><th>Descrição</th><th>Origem/destino</th><th>Fonte / linha</th><th>Situação</th><th></th></tr>`;
  tab += r.linhas.map((l) => `<tr class="${l.situacao}"><td>${esc(l.data || "")} ${esc(l.hora || "")}${l.fuso ? `<div class="mini">${esc(l.fuso)}</div>` : ""}</td><td>${esc(l.natureza || "?")}</td><td class="num">${l.valor_fmt}</td>
    <td>${esc(l.titular_nome || "")}<div class="mini">${esc(l.banco || "")} ${esc(l.agencia || "")} ${esc(l.conta || "")}</div></td><td>${esc(l.descricao || "")}<div class="mini">${esc(l.tipo_operacao || "")} ${esc(l.status_origem || "")}</div></td>
    <td>${l.partes.map((p) => `<div>${esc(p.papel)}: ${esc(p.nome || "?")} <span class="mini">${esc(p.doc || "")}${p.valor_centavos != null ? " · " + (p.valor_centavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) : ""}</span></div>`).join("")}${l.parcelas_estado === "divergentes" || l.parcelas_estado === "incompletas" ? `<div class="mini" style="color:#a60">parcelas ${l.parcelas_estado}</div>` : ""}</td>
    <td class="mini">${esc(l.fonte_nome)}<br>${esc(l.local || "")} linha ${l.linha}</td><td>${esc(l.situacao)}<div class="mini">${esc(l.motivo || "")}</div></td><td><button data-det="${l.id}">Detalhes</button></td></tr>`).join("");
  $("#resultados").innerHTML = tab + "</table>";
  if ($("#btn-mais")) $("#btn-mais").onclick = () => pesquisar(r.deslocamento + 500);
  if ($("#btn-menos")) $("#btn-menos").onclick = () => pesquisar(Math.max(0, r.deslocamento - 500));
  $$("button[data-det]").forEach((b) => (b.onclick = () => detalhes(+b.dataset.det)));
  await carregarFacetas();
}
async function detalhes(id) {
  const d = await api("GET", `/api/lancamentos/${id}`);
  modal(`<h3>Lançamento ${d.id}</h3><p><b>${esc(d.data)} ${esc(d.hora || "")} ${esc(d.fuso || "")}</b> - ${esc(d.natureza || "?")} ${d.valor_fmt} - situação <b>${esc(d.situacao)}</b> ${esc(d.motivo || "")}</p>
    <p>Fonte: <b>${esc(d.fonte_nome)}</b>${d.caminho_no_pacote ? " (" + esc(d.caminho_no_pacote) + ")" : ""}, ${esc(d.local || "")}, linha ${d.linha}; remessa ${esc(d.remessa || "-")}<br>SHA-256: <code>${esc(d.sha256)}</code><br>Chave local (válida só neste arquivo): ${esc(d.chave_local || "-")}</p>
    ${d.titular_obs ? `<div class="aviso">${esc(d.titular_obs)}</div>` : ""}
    <h3>Origens/destinos (estado das parcelas: ${esc(d.parcelas_estado)})</h3><table><tr><th>Papel</th><th>Nome</th><th>CPF/CNPJ</th><th>Banco/ag/conta</th><th>PIX</th><th>Parcela</th><th>Fonte/linha</th></tr>${d.partes.map((p) => `<tr><td>${esc(p.papel)}</td><td>${esc(p.nome || "")}</td><td>${esc(p.doc || "")} <span class="mini">${esc(p.doc_tipo || "")}</span></td><td>${esc(p.banco || "")} ${esc(p.agencia || "")} ${esc(p.conta || "")}</td><td>${esc(p.pix_chave || "")} ${esc(p.pix_id || "")}</td><td class="num">${p.valor_fmt}</td><td class="mini">${esc(p.local || "")} linha ${p.linha}</td></tr>`).join("")}</table>
    ${d.duplicatas.length ? `<div class="aviso">Duplicatas prováveis: ${d.duplicatas.map((x) => `${esc(x.criterio)} (${esc(x.estado)}) com ${x.lanc_a === d.id ? x.lanc_b : x.lanc_a}`).join("; ")}</div>` : ""}
    <h3>Dados originais</h3><pre>${esc(JSON.stringify(JSON.parse(d.bruto_json), null, 2))}</pre>`);
}
$("#btn-pesquisar").onclick = () => pesquisar().catch((e) => alert(e.message));
$("#btn-limpar").onclick = () => { estado.filtros = {}; ["#f-data-ini", "#f-data-fim", "#f-vmin", "#f-vmax", "#f-texto"].forEach((s) => ($(s).value = "")); pesquisar(); };
$("#btn-exportar").onclick = () => baixar("POST", `/api/casos/${exigirCaso()}/exportar`, { filtros: lerFiltrosSimples() }, "pesquisa.csv").catch((e) => alert(e.message));

// ------------------------------------------------------------------ pesquisa geral
$("#btn-geral").onclick = async () => {
  const facs = await api("POST", `/api/casos/${exigirCaso()}/identificadores`, { busca: $("#g-busca").value || null });
  const cont = $("#g-facetas");
  cont.innerHTML = facs.length ? "" : '<p class="nota">Nada encontrado. Importe arquivos primeiro.</p>';
  facs.forEach((f) => criarFaceta(cont, { rotulo: f.rotulo, truncado: f.truncado, valores: f.valores.map((v) => ({ valor: v.v, rotulo: `${v.r} (${v.nf} arquivo(s))`, n: v.n, origens: v.origens })) },
    estado.geralSel[f.tipo], (vals) => { estado.geralSel[f.tipo] = vals; mostrarOcorrencias(); }));
};
async function mostrarOcorrencias() {
  const sel = [];
  Object.entries(estado.geralSel).forEach(([tipo, vals]) => (vals || []).forEach((v) => sel.push({ tipo, valor: v })));
  if (!sel.length) { $("#g-ocorrencias").innerHTML = '<p class="nota">Marque valores nas listas acima.</p>'; return; }
  const r = await api("POST", `/api/casos/${exigirCaso()}/ocorrencias`, { selecionados: sel });
  $("#g-ocorrencias").innerHTML = `<p class="nota">${r.length} ocorrência(s).</p><table><tr><th>Tipo</th><th>Valor (grafia original)</th><th>Onde</th><th>Papel</th><th>Contexto</th><th>Fonte / local / linha</th></tr>${r.map((o) => `<tr><td>${esc(o.tipo)}</td><td>${esc(o.valor_original)}</td><td>${esc(o.origem)}</td><td>${esc(o.papel || "")}</td><td>${esc(o.contexto)}</td><td class="mini">${esc(o.fonte_nome)}<br>${esc(o.local || "")} ${o.linha ? "linha " + o.linha : ""}</td></tr>`).join("")}</table>`;
}
$("#btn-ocorrencias").onclick = () => mostrarOcorrencias().catch((e) => alert(e.message));

// ------------------------------------------------------------------ acessos / geo
async function carregarAcessos() {
  const r = await api("POST", `/api/casos/${exigirCaso()}/acessos`, { filtros: estado.acessosFiltros });
  const cont = $("#a-facetas");
  cont.innerHTML = "";
  r.facetas.forEach((f) => criarFaceta(cont, f, estado.acessosFiltros[f.chave], (vals) => { estado.acessosFiltros[f.chave] = vals; carregarAcessos(); }));
  const pts = r.linhas.filter((l) => l.latitude && l.longitude).map((l) => ({ lat: parseFloat(String(l.latitude).replace(",", ".")), lon: parseFloat(String(l.longitude).replace(",", ".")), l })).filter((p) => isFinite(p.lat) && isFinite(p.lon));
  if (pts.length) {
    const minLat = Math.min(...pts.map((p) => p.lat)), maxLat = Math.max(...pts.map((p) => p.lat)), minLon = Math.min(...pts.map((p) => p.lon)), maxLon = Math.max(...pts.map((p) => p.lon));
    const W = 700, H = 360, m = 30, dx = maxLon - minLon || 0.01, dy = maxLat - minLat || 0.01;
    const svg = pts.map((p) => { const x = m + ((p.lon - minLon) / dx) * (W - 2 * m), y = H - m - ((p.lat - minLat) / dy) * (H - 2 * m); return `<circle cx="${x}" cy="${y}" r="6" fill="#c62828" opacity=".7"><title>${esc(p.l.data)} ${esc(p.l.hora || "")} ${esc(p.l.ip || "")} ${p.lat},${p.lon} ${esc(p.l.cidade || "")}</title></circle>`; }).join("");
    $("#a-mapa").innerHTML = `<div class="cartao"><b>Dispersão das coordenadas (${pts.length})</b> <span class="mini">lat ${minLat.toFixed(4)} a ${maxLat.toFixed(4)}; long ${minLon.toFixed(4)} a ${maxLon.toFixed(4)} - sem mapa de fundo (offline)</span><br><svg width="${W}" height="${H}" style="background:#f4f7fb;border:1px solid #ccd">${svg}</svg></div>`;
  } else $("#a-mapa").innerHTML = "";
  $("#a-tabela").innerHTML = `<p class="nota">${r.total} registro(s).</p><table><tr><th>Data/hora</th><th>Fuso</th><th>IP:porta</th><th>Lat, long</th><th>Cidade/UF</th><th>Dispositivo</th><th>Evento</th><th>Pessoa</th><th>Fonte / linha</th></tr>${r.linhas.map((l) => `<tr><td>${esc(l.data || "")} ${esc(l.hora || "")}<div class="mini">${esc(l.data_original || "")}</div></td><td>${esc(l.fuso || "")}</td><td>${esc(l.ip || "")}${l.porta ? ":" + esc(l.porta) : ""}</td><td>${esc(l.latitude || "")}${l.latitude ? ", " : ""}${esc(l.longitude || "")}</td><td>${esc(l.cidade || "")} ${esc(l.uf || "")}</td><td>${esc(l.dispositivo || "")} ${esc(l.sistema || "")}</td><td>${esc(l.evento || "")}</td><td>${esc(l.nome || "")} ${esc(l.doc || "")}</td><td class="mini">${esc(l.fonte_nome)} ${esc(l.local || "")} linha ${l.linha}</td></tr>`).join("")}</table>`;
}
$("#btn-acessos").onclick = () => carregarAcessos().catch((e) => alert(e.message));

// ------------------------------------------------------------------ grafo
function lerFiltrosGrafo() {
  if ($("#g-usar-pesquisa").checked) return lerFiltrosSimples();
  const f = Object.assign({}, estado.gFiltros);
  f.data_ini = $("#gf-data-ini").value || null; f.data_fim = $("#gf-data-fim").value || null;
  f.valor_min = $("#gf-vmin").value || null; f.valor_max = $("#gf-vmax").value || null; f.texto = $("#gf-texto").value || null;
  return f;
}
function minVolumeCentavos() {
  const c = ($("#gf-minvol").value || "").trim();
  if (!c) return 0;
  const n = Number(c.replace(/\./g, "").replace(",", "."));
  return Number.isFinite(n) ? Math.round(n * 100) : 0;
}
function htmlVazioGrafo(titulo, texto, aba) {
  return `<div class="vazio-grafo"><div class="vazio-ico">◎</div><h3>${esc(titulo)}</h3><p>${texto}</p>
    ${aba ? `<button type="button" class="primario" data-aba-ir="${esc(aba)}">${aba === "importar" ? "Ir para Importar" : "Ir para o Início"}</button>` : ""}</div>`;
}
async function carregarGrafoFiltros() {
  if (!estado.caso) {
    $("#grafo-area").innerHTML = htmlVazioGrafo("Selecione um caso no topo", "Depois importe o extrato. O mapa de transferências aparece sozinho.", "casos");
    return;
  }
  try {
    const facs = await api("POST", `/api/casos/${exigirCaso()}/facetas`, { filtros: lerFiltrosGrafo() });
    const cont = $("#grafo-facetas");
    cont.innerHTML = "";
    facs.forEach((f) => criarFaceta(cont, f, estado.gFiltros[f.chave], (vals) => {
      estado.gFiltros[f.chave] = vals;
      agendarGrafo();
    }, { aoVivo: true }));
  } catch (e) { console.error(e); }
  await gerarGrafo();
}
function agendarGrafo() {
  clearTimeout(estado.grafoTimer);
  estado.grafoTimer = setTimeout(() => gerarGrafo().catch((e) => {
    $("#grafo-area").innerHTML = `<div class="erro">${esc(e.message)}</div>`;
  }), 180);
}
$("#btn-grafo-limpar").onclick = () => {
  estado.gFiltros = {};
  ["#gf-data-ini", "#gf-data-fim", "#gf-vmin", "#gf-vmax", "#gf-texto", "#gf-busca", "#gf-minvol"].forEach((s) => { if ($(s)) $(s).value = ""; });
  $("#gf-maxnos").value = 80; $("#g-usar-pesquisa").checked = false;
  carregarGrafoFiltros().catch((e) => console.error(e));
};
["#gf-data-ini", "#gf-data-fim", "#gf-vmin", "#gf-vmax", "#gf-texto", "#gf-maxnos", "#gf-minvol"].forEach((s) => {
  if ($(s)) $(s).addEventListener("change", () => agendarGrafo());
});
$("#g-usar-pesquisa").addEventListener("change", () => agendarGrafo());
function ligarPanZoom(svg) {
  const cena = svg.querySelector("#grafo-cena");
  let x = 0, y = 0, s = 1, arr = false, lx = 0, ly = 0;
  const aplicar = () => cena.setAttribute("transform", `translate(${x} ${y}) scale(${s})`);
  const zoomEm = (mx, my, fator) => {
    const ns = Math.min(8, Math.max(0.12, s * fator));
    x = mx - (mx - x) * ns / s; y = my - (my - y) * ns / s; s = ns; aplicar();
  };
  const ponto = (e) => {
    const r = svg.getBoundingClientRect();
    const vb = svg.viewBox.baseVal;
    return [(e.clientX - r.left) * vb.width / r.width, (e.clientY - r.top) * vb.height / r.height];
  };
  svg.addEventListener("wheel", (e) => { e.preventDefault(); const [mx, my] = ponto(e); zoomEm(mx, my, e.deltaY < 0 ? 1.18 : 1 / 1.18); }, { passive: false });
  svg.addEventListener("mousedown", (e) => { if (e.button !== 0) return; arr = true; lx = e.clientX; ly = e.clientY; });
  window.addEventListener("mousemove", (e) => {
    if (!arr) return;
    const r = svg.getBoundingClientRect(); const vb = svg.viewBox.baseVal;
    x += (e.clientX - lx) * vb.width / r.width; y += (e.clientY - ly) * vb.height / r.height;
    lx = e.clientX; ly = e.clientY; aplicar();
  });
  window.addEventListener("mouseup", () => { arr = false; });
  return {
    mais: () => zoomEm(svg.viewBox.baseVal.width / 2, svg.viewBox.baseVal.height / 2, 1.25),
    menos: () => zoomEm(svg.viewBox.baseVal.width / 2, svg.viewBox.baseVal.height / 2, 0.8),
    reset: () => { x = 0; y = 0; s = 1; aplicar(); },
  };
}
function destacarGrafo(termo) {
  const t = (termo || "").toLowerCase();
  $$("#svg-grafo .no-grafo").forEach((g) => {
    const ok = !t || (g.dataset.rotulo || "").toLowerCase().includes(t);
    g.style.opacity = ok ? "1" : ".18";
    const c = g.querySelector(".no-nucleo");
    if (c) {
      c.setAttribute("stroke", ok && t ? "#fff4c2" : "#0b1424");
      c.setAttribute("stroke-width", ok && t ? "4" : "2.5");
    }
  });
}
function raioNo(n, maxVol) {
  if (n.tipo === "conta") return 24;
  if (n.tipo === "nao_distribuido") return 12;
  return 11 + 12 * Math.sqrt((n.volume || 0) / Math.max(1, maxVol));
}
function posicionarNos(nos, W, H) {
  const contas = nos.filter((n) => n.tipo === "conta");
  const outros = nos.filter((n) => n.tipo !== "conta").sort((a, b) => (b.volume || 0) - (a.volume || 0));
  const cx = W * 0.56, cy = H * 0.50;
  contas.forEach((n, i) => {
    const a = (i / Math.max(contas.length, 1)) * Math.PI * 2 - Math.PI / 2;
    n.x = cx + Math.cos(a) * Math.min(280, W * 0.20);
    n.y = cy + Math.sin(a) * Math.min(200, H * 0.20);
    n.vx = 0; n.vy = 0;
  });
  outros.forEach((n, i) => {
    const a = (i / Math.max(outros.length, 1)) * Math.PI * 2 - Math.PI / 2 + 0.2;
    n.x = cx + Math.cos(a) * Math.min(520, W * 0.40);
    n.y = cy + Math.sin(a) * Math.min(360, H * 0.38);
    n.vx = 0; n.vy = 0;
  });
  if (nos.length === 1) { nos[0].x = cx; nos[0].y = cy; }
}
async function gerarGrafo() {
  const area = $("#grafo-area");
  if (!estado.caso) {
    area.innerHTML = htmlVazioGrafo("Selecione um caso no topo", "Depois importe o extrato. O mapa de transferências aparece sozinho.", "casos");
    return;
  }
  estado.grafoSeq = (estado.grafoSeq || 0) + 1;
  const seq = estado.grafoSeq;
  area.innerHTML = '<div class="grafo-carregando"><div class="spinner"></div><p>Montando o mapa de transferências…</p></div>';
  let g;
  try {
    g = await api("POST", `/api/casos/${exigirCaso()}/grafo`, {
      filtros: lerFiltrosGrafo(), max_nos: +$("#gf-maxnos").value || 80, min_volume: minVolumeCentavos(),
    });
  } catch (e) {
    if (seq !== estado.grafoSeq) return;
    area.innerHTML = `<div class="erro">${esc(e.message)}</div>`;
    return;
  }
  if (seq !== estado.grafoSeq) return;
  $("#grafo-filtros-ativos").innerHTML = (g.filtros || []).map((d) => `<span>${esc(d)}</span>`).join("");
  if (!g.nos.length) {
    area.innerHTML = htmlVazioGrafo("Ainda não há transferências para desenhar",
      "Importe um extrato na etapa 1. Contas e quem enviou ou recebeu aparecem aqui automaticamente.", "importar");
    return;
  }
  const W = 1600, H = 980;
  const nos = g.nos.map((n) => Object.assign({}, n));
  const maxVol = Math.max(1, ...nos.map((n) => n.volume || 0));
  posicionarNos(nos, W, H);
  const id = Object.fromEntries(nos.map((n) => [n.id, n]));
  const ars = g.arestas.filter((a) => id[a.de] && id[a.para]);
  const rai = Object.fromEntries(nos.map((n) => [n.id, raioNo(n, maxVol)]));
  for (let it = 0; it < 280; it++) {
    for (const a of nos) for (const b of nos) {
      if (a === b) continue;
      const dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy + 0.01;
      const d = Math.sqrt(d2);
      const minD = rai[a.id] + rai[b.id] + 64;
      const f = d < minD ? (minD - d) * 0.22 : 6200 / d2;
      a.vx += (dx / d) * f; a.vy += (dy / d) * f;
    }
    for (const e of ars) {
      const a = id[e.de], b = id[e.para], dx = b.x - a.x, dy = b.y - a.y;
      a.vx += dx * 0.003; a.vy += dy * 0.003; b.vx -= dx * 0.003; b.vy -= dy * 0.003;
    }
    for (const n of nos) {
      n.vx += (W * 0.56 - n.x) * 0.0007; n.vy += (H * 0.5 - n.y) * 0.0007;
      const pad = 110;
      n.x = Math.max(pad, Math.min(W - pad, n.x + n.vx));
      n.y = Math.max(pad, Math.min(H - pad, n.y + n.vy));
      n.vx *= 0.55; n.vy *= 0.55;
    }
  }
  const maxA = Math.max(1, ...ars.map((a) => a.valor || 0));
  const corNo = { conta: "#e0b14a", contraparte: "#3ecfbf", nao_distribuido: "#8b95a7" };
  const defs = `<defs>
    <marker id="seta" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,1 L12,6 L0,11 z" fill="#d7e3f5"/></marker>
    <marker id="seta-nd" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,1 L12,6 L0,11 z" fill="#7a8494"/></marker>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  </defs>`;
  let svg = `<svg id="svg-grafo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">${defs}<g id="grafo-cena">`;
  const pontas = (p, q) => {
    const dx = q.x - p.x, dy = q.y - p.y, d = Math.hypot(dx, dy) || 1;
    return { x1: p.x + dx / d * (rai[p.id] + 2), y1: p.y + dy / d * (rai[p.id] + 2),
      x2: q.x - dx / d * (rai[q.id] + 10), y2: q.y - dy / d * (rai[q.id] + 10),
      mx: (p.x + q.x) / 2, my: (p.y + q.y) / 2, nx: -dy / d, ny: dx / d };
  };
  for (const a of ars) {
    const p = id[a.de], q = id[a.para], t = pontas(p, q);
    const curv = 26 + (String(p.id).length + String(q.id).length) % 18;
    const cx = t.mx + t.nx * curv, cy = t.my + t.ny * curv;
    const w = 1.4 + 7 * (a.valor || 0) / maxA;
    const op = 0.45 + 0.4 * (a.valor || 0) / maxA;
    svg += `<path d="M ${t.x1} ${t.y1} Q ${cx} ${cy} ${t.x2} ${t.y2}" fill="none" stroke="${a.nd ? "#7a8494" : "#9fb4d1"}" stroke-width="${w}" stroke-dasharray="${a.nd ? "5,4" : ""}" opacity="${op}" marker-end="url(#${a.nd ? "seta-nd" : "seta"})"><title>${esc(a.valor_fmt)} em ${a.n} lançamento(s)</title></path>`;
  }
  ars.slice().sort((a, b) => (b.valor || 0) - (a.valor || 0)).slice(0, 14).forEach((a) => {
    if (a.nd) return;
    const p = id[a.de], q = id[a.para], t = pontas(p, q);
    const curv = 26 + (String(p.id).length + String(q.id).length) % 18;
    svg += `<text x="${t.mx + t.nx * (curv + 8)}" y="${t.my + t.ny * (curv + 8)}" text-anchor="middle" font-size="11" fill="#f0e2b6" font-family="Segoe UI, Arial">${esc(a.valor_fmt)}</text>`;
  });
  for (const l of g.ligacoes) {
    const p = id[l.de], q = id[l.para];
    if (!p || !q) continue;
    svg += `<line x1="${p.x}" y1="${p.y}" x2="${q.x}" y2="${q.y}" stroke="${l.hipotese ? "#e0b14a" : "#c084fc"}" stroke-dasharray="3,5" stroke-width="2" opacity=".75"><title>${esc(l.tipo)}</title></line>`;
  }
  for (const n of nos) {
    const r = rai[n.id], fill = corNo[n.tipo] || "#8b95a7";
    svg += `<g class="no-grafo" data-id="${esc(n.id)}" data-rotulo="${esc(n.rotulo)} ${esc(n.detalhe || "")}" style="cursor:pointer">
      <circle cx="${n.x}" cy="${n.y}" r="${r + 6}" fill="${fill}" opacity=".18" filter="url(#glow)"></circle>
      <circle class="no-nucleo" cx="${n.x}" cy="${n.y}" r="${r}" fill="${fill}" stroke="#0b1424" stroke-width="2.5"></circle>
      <text x="${n.x}" y="${n.y + r + 18}" text-anchor="middle" font-size="${n.tipo === "conta" ? 13 : 12}" font-weight="${n.tipo === "conta" ? 600 : 400}" fill="#f4f1e8" stroke="#0b1424" stroke-width="4" paint-order="stroke" font-family="Segoe UI, Arial">${esc(String(n.rotulo || "").slice(0, 36))}</text></g>`;
  }
  svg += "</g></svg>";
  area.innerHTML = `<div class="grafo-viewport" id="grafo-viewport">
      <div class="grafo-legenda">
        <div><i style="background:#e0b14a"></i>Conta do extrato</div>
        <div><i style="background:#3ecfbf"></i>Quem enviou ou recebeu</div>
        <div><i style="background:#c084fc"></i>Mesmo CPF/CNPJ</div>
        <div><i style="background:#e0b14a"></i>Hipótese só por nome</div>
        <p class="mini">Setas = direção do registro, não prova de origem do dinheiro. Arraste para mover · role para zoom.</p>
        ${g.omitidos ? `<p class="mini">${g.omitidos} nós menores foram omitidos.</p>` : ""}
      </div>
      <div class="grafo-ferramentas"><button type="button" id="gz-mais" title="Aproximar">+</button><button type="button" id="gz-menos" title="Afastar">−</button><button type="button" id="gz-reset" title="Ajustar">⊡</button><button type="button" id="gz-png" title="Baixar PNG">PNG</button></div>
      <div class="grafo-detalhe" id="grafo-detalhe">Clique em um círculo para ver os valores.</div>
      ${svg}
    </div>
    <p class="aviso">${esc(g.aviso)}</p>`;
  estado.grafoCtrl = ligarPanZoom($("#svg-grafo"));
  $("#gz-mais").onclick = () => estado.grafoCtrl.mais();
  $("#gz-menos").onclick = () => estado.grafoCtrl.menos();
  $("#gz-reset").onclick = () => estado.grafoCtrl.reset();
  if ($("#gz-png")) $("#gz-png").onclick = baixarGrafoPng;
  $$("#svg-grafo .no-grafo").forEach((el) => (el.onclick = (e) => {
    e.stopPropagation();
    const n = id[el.dataset.id];
    if (!n) return;
    const lig = ars.filter((a) => a.de === n.id || a.para === n.id);
    $("#grafo-detalhe").innerHTML = `<b>${esc(n.rotulo)}</b> <span class="mini">${esc(n.tipo)} ${esc(n.detalhe || "")} ${esc(n.identificacao || "")}</span><br>${lig.slice(0, 8).map((a) => `${esc(a.valor_fmt)} · ${a.n} lanç.`).join("<br>") || "sem setas visíveis"}`;
  }));
  destacarGrafo($("#gf-busca").value);
}
$("#gf-busca").addEventListener("input", () => destacarGrafo($("#gf-busca").value));
$("#btn-grafo").onclick = () => gerarGrafo().catch((e) => { $("#grafo-area").innerHTML = `<div class="erro">${esc(e.message)}</div>`; });
function baixarGrafoPng() {
  const svg = $("#svg-grafo"); if (!svg) return alert("Aguarde o grafo aparecer (ou importe um extrato).");
  const img = new Image();
  img.onload = () => {
    const c = document.createElement("canvas");
    c.width = svg.viewBox.baseVal.width; c.height = svg.viewBox.baseVal.height;
    const x = c.getContext("2d"); x.fillStyle = "#0b1424"; x.fillRect(0, 0, c.width, c.height); x.drawImage(img, 0, 0);
    const a = document.createElement("a"); a.href = c.toDataURL("image/png"); a.download = "grafo.png"; a.click();
  };
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(svg));
}
$("#btn-grafo-png").onclick = baixarGrafoPng;
$("#btn-seq").onclick = async () => {
  try {
    const r = await api("POST", `/api/casos/${exigirCaso()}/sequencias`, { inicio: $("#s-inicio").value, janela_dias: $("#s-janela").value, tolerancia_pct: $("#s-tol").value, profundidade: $("#s-prof").value, por_nome: $("#s-nome").checked });
    $("#seq-res").innerHTML = `<div class="aviso">${esc(r.aviso)}</div>${r.mensagem ? `<p>${esc(r.mensagem)}</p>` : ""}<p class="nota">${r.cadeias.length} sequência(s)${r.truncado ? " (limite atingido)" : ""}.</p>` + r.cadeias.map((c) => `<div class="cadeia"><div class="qual">${esc(c.qualificacao)}</div>${c.elos.map((e, i) => `<div>${i + 1}. ${esc(e.data)} ${esc(e.hora || "")} - ${esc(e.titular_origem || "?")} (${esc(e.conta_origem)}) → ${esc(e.destino || "?")} ${esc(e.destino_doc || "")}: <b>${esc(e.valor_fmt)}</b> <span class="mini">[${esc(e.identificacao)}${e.conta_destino ? "; conta " + esc(e.conta_destino) : ""}${e.registro_espelho_na_conta_destino ? "; crédito correspondente na conta destino: lanç. " + e.registro_espelho_na_conta_destino.lancamento_id : ""}] fonte ${esc(e.fonte)} linha ${e.linha}</span></div>`).join("")}</div>`).join("");
  } catch (e) { msg("#seq-res", e.message); }
};

// ------------------------------------------------------------------ duplicatas
async function carregarDuplicatas() {
  const ds = await api("GET", `/api/casos/${exigirCaso()}/duplicatas${$("#dup-estado").value ? "?estado=" + $("#dup-estado").value : ""}`);
  const lin = (l) => l ? `${esc(l.data)} ${esc(l.natureza || "?")} ${l.valor_fmt} - ${esc(l.titular_nome || "")} ${esc(l.conta || "")} - ${esc(l.descricao || "")}<div class="mini">${esc(l.nome_original)} ${esc(l.local || "")} linha ${l.linha} [id ${l.id}]${l.consolidado_em ? " - consolidado em " + l.consolidado_em : ""}</div>` : "";
  $("#dups").innerHTML = ds.length ? `<table><tr><th>Critério</th><th>Registro A</th><th>Registro B</th><th>Estado</th><th>Decisão</th></tr>${ds.map((d) => `<tr><td>${esc(d.criterio)}<div class="mini">${esc(d.detalhe || "")}</div></td><td>${lin(d.a)}</td><td>${lin(d.b)}</td><td>${esc(d.estado)}<div class="mini">${esc(d.decidido_por || "")} ${esc(d.decidido_em || "")} ${esc(d.justificativa || "")}</div></td>
    <td><select data-dup="${d.id}"><option value="mesma_operacao">mesma operação</option><option value="distintas">distintas</option><option value="dois_lados_confirmado">dois lados da transferência</option><option value="pendente">voltar a pendente</option></select><input data-just="${d.id}" placeholder="justificativa" size="18"><button data-dec="${d.id}">Registrar</button></td></tr>`).join("")}</table>` : '<p class="nota">Nenhuma duplicata provável neste filtro.</p>';
  $$("button[data-dec]").forEach((b) => (b.onclick = async () => {
    try { await api("POST", `/api/duplicatas/${b.dataset.dec}/decidir`, { estado: $(`select[data-dup="${b.dataset.dec}"]`).value, justificativa: $(`input[data-just="${b.dataset.dec}"]`).value }); carregarDuplicatas(); }
    catch (e) { alert(e.message); }
  }));
}
$("#btn-dups").onclick = () => carregarDuplicatas().catch((e) => alert(e.message));

// ------------------------------------------------------------------ RIF
async function carregarRif() {
  const rifs = await api("GET", `/api/casos/${exigirCaso()}/rif`);
  $("#rif-area").innerHTML = rifs.length ? rifs.map((r) => `<div class="cartao"><h3>RIF ${esc(r.numero || "#" + r.id)} - ${esc(r.nome_original)}</h3><div class="aviso">${esc(r.restricao)}</div><p class="mini">SHA-256 ${esc(r.sha256)}</p>
    <h3>Comunicações (${r.comunicacoes.length})</h3><table><tr><th>ID</th><th>Recebida</th><th>Operação</th><th>Comunicante</th><th>Valor informado</th><th>Informações</th><th>Linha</th></tr>${r.comunicacoes.map((c) => `<tr><td>${esc(c.id_comunicacao)}</td><td>${esc(c.data_recebimento || "")}</td><td>${esc(c.data_operacao || "")} a ${esc(c.data_fim || "")}</td><td>${esc(c.comunicante_nome || "")} ${esc(c.comunicante_doc || "")}</td><td>${c.valor_centavos != null ? (c.valor_centavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }) : "-"}</td><td>${esc(c.informacoes || "")}</td><td class="mini">${esc(c.local)} ${c.linha}</td></tr>`).join("")}</table>
    <h3>Envolvidos (${r.envolvidos.length})</h3><table><tr><th>Comunicação</th><th>Nome</th><th>CPF/CNPJ</th><th>Tipo</th><th>Ag/conta</th><th>Linha</th></tr>${r.envolvidos.map((e) => `<tr><td>${esc(e.id_comunicacao)}</td><td>${esc(e.nome || "")}</td><td>${esc(e.doc || "")}</td><td>${esc(e.tipo_envolvido || "")}</td><td>${esc(e.agencia || "")} ${esc(e.conta || "")}</td><td class="mini">${esc(e.local)} ${e.linha}</td></tr>`).join("")}</table>
    ${r.envolvidos_com_movimentacao.length ? `<div class="nota">Documentos de envolvidos que também aparecem em extratos do caso (coincidência a verificar): ${r.envolvidos_com_movimentacao.map((x) => `${esc(x.doc)} (${x.ocorrencias_em_extratos})`).join(", ")}</div>` : ""}
    <h3>Ocorrências (${r.ocorrencias.length})</h3>${r.ocorrencias.map((o) => `<div>${esc(o.id_comunicacao)}: ${esc(o.ocorrencia)}</div>`).join("")}
    <h3>Citações de página (${r.citacoes.length})</h3>${r.citacoes.map((c) => `<div>Fonte ${c.fonte_id} p. ${c.pagina}: "${esc(c.trecho)}" <span class="mini">${esc(c.criado_por)} ${esc(c.criado_em)}</span></div>`).join("")}
    <div><input data-cit-fonte="${r.id}" placeholder="ID da fonte (PDF)" size="8"> <input data-cit-pag="${r.id}" placeholder="página" size="4"> <input data-cit-com="${r.id}" placeholder="comunicação" size="8"> <input data-cit-txt="${r.id}" placeholder="trecho citado" size="40"> <button data-cit="${r.id}">Registrar citação</button></div></div>`).join("") : '<p class="nota">Nenhum RIF importado. Importe o ZIP/CSV do RIF na aba Importar.</p>';
  $$("button[data-cit]").forEach((b) => (b.onclick = async () => {
    const i = b.dataset.cit;
    try { await api("POST", `/api/casos/${estado.caso}/rif/${i}/citacao`, { fonte_id: +$(`[data-cit-fonte="${i}"]`).value || null, pagina: +$(`[data-cit-pag="${i}"]`).value || null, id_comunicacao: $(`[data-cit-com="${i}"]`).value, trecho: $(`[data-cit-txt="${i}"]`).value }); carregarRif(); }
    catch (e) { alert(e.message); }
  }));
}
$("#btn-rif").onclick = () => carregarRif().catch((e) => alert(e.message));

// ------------------------------------------------------------------ documentos / OCR
async function carregarDocs() {
  const est = await api("GET", "/api/estado");
  $("#ocr-status").textContent = est.ocr.disponivel ? `OCR local disponível (idiomas: ${est.ocr.idiomas.join(", ") || "?"}).` : "OCR local não instalado: veja ferramentas_ocr/LEIA.txt. A extração de texto selecionável funciona sem OCR.";
  const fs = await api("GET", `/api/casos/${exigirCaso()}/fontes`);
  estado.fontes = fs;
  $("#doc-fonte").innerHTML = fs.filter((f) => f.tipo === "pdf").map((f) => `<option value="${f.id}">${esc(f.nome_original)}</option>`).join("");
}
$("#btn-doc-original").onclick = () => $("#doc-fonte").value && window.open(`/api/fontes/${$("#doc-fonte").value}/original`, "_blank");
$("#btn-doc").onclick = async () => {
  const fid = $("#doc-fonte").value; if (!fid) return;
  const pags = await api("GET", `/api/fontes/${fid}/paginas`);
  $("#doc-area").innerHTML = (pags.length ? "" : '<p class="nota">Texto ainda não extraído: prepare o PDF na aba Fontes/Importar.</p>') + pags.map((p) => `<div class="cartao"><b>Página ${p.pagina}</b> (${esc(p.metodo)}) ${p.revisado ? `<span class="ok">revisada por ${esc(p.revisado_por)} em ${esc(p.revisado_em)}</span>` : '<span class="aviso">não revisada</span>'}
    <textarea rows="6" data-pg="${p.id}">${esc(p.texto || "")}</textarea><button data-rev="${p.id}">Salvar revisão</button> <button data-ocr="${p.pagina}">OCR local desta página</button> ${p.metodo === "ocr" ? `<button data-cx="${p.id}">Revisar caixas do OCR</button>` : ""}</div>`).join("");
  $$("button[data-rev]").forEach((b) => (b.onclick = async () => { try { await api("POST", `/api/paginas/${b.dataset.rev}/revisar`, { texto: $(`textarea[data-pg="${b.dataset.rev}"]`).value }); $("#btn-doc").click(); } catch (e) { alert(e.message); } }));
  $$("button[data-ocr]").forEach((b) => (b.onclick = async () => { try { const r = await api("POST", `/api/fontes/${fid}/ocr`, { pagina: +b.dataset.ocr }); await esperarTarefa(r.tarefa, $("#ocr-status")); $("#btn-doc").click(); } catch (e) { alert(e.message); } }));
  $$("button[data-cx]").forEach((b) => (b.onclick = () => revisarCaixas(+b.dataset.cx, fid)));
};
async function revisarCaixas(pid, fid) {
  const r = await api("GET", `/api/paginas/${pid}/palavras`);
  modal(`<h3>Revisão por caixa delimitadora - página ${r.pagina.pagina}</h3><p class="nota">Palavras com confiança abaixo de 70% aparecem em vermelho. Clique numa caixa para corrigir.</p><div style="position:relative;display:inline-block"><img id="cx-img" src="/api/fontes/${fid}/pagina_imagem/${r.pagina.pagina}" style="max-width:100%"><div id="cx-sobre"></div></div><div id="cx-lista"></div><button id="cx-salvar" class="primario">Salvar correções e marcar página como revisada</button>`);
  const correcoes = {};
  $("#cx-img").onload = () => {
    const img = $("#cx-img");
    // OCR é feito a 300 dpi e a imagem exibida é gerada a 150 dpi.
    const fator = img.clientWidth / (img.naturalWidth * 2);
    $("#cx-sobre").innerHTML = r.palavras.map((w) => `<div data-w="${w.id}" title="${esc(w.texto)} (${Math.round(w.confianca)}%)" style="position:absolute;left:${w.x * fator}px;top:${w.y * fator}px;width:${w.w * fator}px;height:${w.h * fator}px;border:1px solid ${w.confianca < 70 ? "#e00" : "rgba(0,120,0,.4)"};cursor:pointer"></div>`).join("");
    $$("#cx-sobre div").forEach((d) => (d.onclick = () => { const w = r.palavras.find((x) => x.id === +d.dataset.w); const novo = prompt(`Texto reconhecido: "${w.texto}" (${Math.round(w.confianca)}%). Correção:`, w.texto_corrigido || w.texto); if (novo != null) { correcoes[w.id] = novo; d.style.background = "rgba(255,230,0,.3)"; } }));
  };
  $("#cx-salvar").onclick = async () => { await api("POST", `/api/paginas/${pid}/revisar`, { correcoes: Object.entries(correcoes).map(([id, texto]) => ({ id, texto })) }); $("#modal").classList.add("oculto"); $("#btn-doc").click(); };
}

// ------------------------------------------------------------------ evidências (marcação)
const ev = { img: null, formas: [], desenhando: null };
const cv = $("#ev-canvas"), ctx = cv.getContext("2d");
function redesenhar() {
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (ev.img) ctx.drawImage(ev.img, 0, 0, cv.width, cv.height); else { ctx.fillStyle = "#f4f6f9"; ctx.fillRect(0, 0, cv.width, cv.height); ctx.fillStyle = "#777"; ctx.fillText("Carregue uma página/imagem ou cole uma captura (Ctrl+V).", 20, 30); }
  for (const f of ev.formas.concat(ev.desenhando ? [ev.desenhando] : [])) {
    ctx.strokeStyle = f.cor; ctx.lineWidth = Math.max(3, cv.width / 400);
    ctx.beginPath();
    if (f.tipo === "ret") ctx.strokeRect(f.x1, f.y1, f.x2 - f.x1, f.y2 - f.y1);
    else if (f.tipo === "circ") { ctx.ellipse((f.x1 + f.x2) / 2, (f.y1 + f.y2) / 2, Math.abs(f.x2 - f.x1) / 2, Math.abs(f.y2 - f.y1) / 2, 0, 0, Math.PI * 2); ctx.stroke(); }
    else { const ang = Math.atan2(f.y2 - f.y1, f.x2 - f.x1), t = ctx.lineWidth * 5; ctx.moveTo(f.x1, f.y1); ctx.lineTo(f.x2, f.y2); ctx.lineTo(f.x2 - t * Math.cos(ang - 0.4), f.y2 - t * Math.sin(ang - 0.4)); ctx.moveTo(f.x2, f.y2); ctx.lineTo(f.x2 - t * Math.cos(ang + 0.4), f.y2 - t * Math.sin(ang + 0.4)); ctx.stroke(); }
  }
}
function pos(e) { const r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * cv.width / r.width, (e.clientY - r.top) * cv.height / r.height]; }
cv.onmousedown = (e) => { const [x, y] = pos(e); ev.desenhando = { tipo: $("#ev-forma").value, cor: $("#ev-cor").value, x1: x, y1: y, x2: x, y2: y }; };
cv.onmousemove = (e) => { if (!ev.desenhando) return; [ev.desenhando.x2, ev.desenhando.y2] = pos(e); redesenhar(); };
cv.onmouseup = () => { if (ev.desenhando) { ev.formas.push(ev.desenhando); ev.desenhando = null; redesenhar(); } };
$("#btn-ev-desfazer").onclick = () => { ev.formas.pop(); redesenhar(); };
$("#btn-ev-limpar").onclick = () => { ev.formas = []; redesenhar(); };
function usarImagem(src) { const img = new Image(); img.onload = () => { ev.img = img; cv.width = img.naturalWidth; cv.height = img.naturalHeight; ev.formas = []; redesenhar(); }; img.src = src; }
$("#ev-arquivo").onchange = () => { const f = $("#ev-arquivo").files[0]; if (f) usarImagem(URL.createObjectURL(f)); };
document.addEventListener("paste", (e) => { if (!$("#aba-evidencias").classList.contains("ativa")) return; const it = [...e.clipboardData.items].find((i) => i.type.startsWith("image/")); if (it) usarImagem(URL.createObjectURL(it.getAsFile())); });
$("#btn-ev-carregar").onclick = () => {
  const fid = $("#ev-fonte").value; if (!fid) return alert("Escolha a fonte ou cole uma captura.");
  const f = estado.fontes.find((x) => x.id === +fid);
  usarImagem(f && f.tipo === "imagem" ? `/api/fontes/${fid}/original` : `/api/fontes/${fid}/pagina_imagem/${+$("#ev-pagina").value || 1}`);
};
$("#btn-ev-salvar").onclick = async () => {
  if (!ev.img) return alert("Nada para salvar.");
  try {
    await api("POST", `/api/casos/${exigirCaso()}/evidencias`, { fonte_id: +$("#ev-fonte").value || null, pagina: +$("#ev-pagina").value || null, descricao: $("#ev-desc").value, png: cv.toDataURL("image/png"), jpg: cv.toDataURL("image/jpeg", 0.92) });
    carregarEvidencias();
  } catch (e) { alert(e.message); }
};
async function carregarEvidencias() {
  const fs = await api("GET", `/api/casos/${exigirCaso()}/fontes`);
  estado.fontes = fs;
  $("#ev-fonte").innerHTML = '<option value="">(captura colada / sem fonte)</option>' + fs.filter((f) => f.tipo === "pdf" || f.tipo === "imagem").map((f) => `<option value="${f.id}">${esc(f.nome_original)}</option>`).join("");
  const evs = await api("GET", `/api/casos/${estado.caso}/evidencias`);
  $("#ev-lista").innerHTML = evs.map((e) => `<div class="cartao">#${e.id} ${esc(e.descricao || "")} - ${esc(e.nome_original || "captura")} p. ${e.pagina || "-"} <span class="mini">SHA-256 imagem ${esc(e.sha256_png)}</span><br><img src="/api/evidencias/${e.id}/imagem" style="max-width:300px"></div>`).join("");
  redesenhar();
}

// ------------------------------------------------------------------ relatório
async function carregarRelImagens() {
  const evs = await api("GET", `/api/casos/${exigirCaso()}/evidencias`);
  $("#rel-imagens").innerHTML = evs.length ? "<b>Imagens marcadas:</b><br>" + evs.map((e) => `<label><input type="checkbox" value="${e.id}"> #${e.id} ${esc(e.descricao || "")}</label><br>`).join("") : "";
}
$$("#aba-relatorio button[data-formato]").forEach((b) => (b.onclick = () => baixar("POST", `/api/casos/${exigirCaso()}/relatorio`, {
  formato: b.dataset.formato, filtros: lerFiltrosSimples(), observacoes: $("#rel-obs").value,
  evidencias: $$("#rel-imagens input:checked").map((i) => +i.value), incluir_analise: $("#rel-analise").checked,
}, "relatorio." + b.dataset.formato).catch((e) => alert(e.message))));

// ------------------------------------------------------------------ IA
function corpoIA() {
  const alvo = $$("input[name=ia-alvo]").find((i) => i.checked);
  return {
    modelo: $("#ia-modelo").value || null,
    pergunta: $("#ia-pergunta").value,
    filtros: lerFiltrosSimples(),
    fonte_id: alvo && alvo.value === "doc" ? +$("#ia-doc").value : null,
    usar_conhecimento: $("#ia-conh").checked,
    gerar_analise: $("#ia-gerar").checked,
    conversa_id: estado.conversaId,
    hipotese_crime: $("#ia-hipotese").value,
    vitimas: $("#ia-vitimas").value,
    investigados: $("#ia-investigados").value,
    janela_vitima_dias: +$("#ia-janela").value || 7,
  };
}
function pintarChat(msgs) {
  const el = $("#ia-chat");
  if (!msgs || !msgs.length) { el.innerHTML = '<div class="msg sistema">Nenhuma mensagem nesta conversa. Gere a análise ou pergunte — funciona sem Ollama e sem Gemini.</div>'; return; }
  el.innerHTML = msgs.map((m) => `<div class="msg ${esc(m.papel)}">${esc(m.texto)}</div>`).join("");
  el.scrollTop = el.scrollHeight;
}
function pintarAnalise(a) {
  const alvo = $("#ia-analise");
  if (!a) {
    alvo.innerHTML = `<div class="vazio"><h3>Ainda não há análise neste caso</h3>
      <p>Importe o extrato e clique em <b>Gerar / atualizar análise</b>. O cálculo é feito neste computador.</p>
      <button type="button" class="primario" data-aba-ir="importar">Ir para Importar</button></div>`;
    return;
  }
  const ach = (a.achados || []).filter((x) => x.tipo !== "alcance");
  alvo.innerHTML = `<div class="aviso">${esc(a.aviso || "")}</div>
    <p class="nota">Hipótese: <b>${esc(a.hipotese_crime)}</b>${(a.hipoteses_detectadas || []).length ? " (detectada: " + esc(a.hipoteses_detectadas.join(", ")) + ")" : ""} · ${esc((a.gerado_em || "") + " " + (a.gerado_por || ""))}</p>
    <pre>${esc(a.narrativa || "")}</pre>
    ${ach.map((x) => `<details class="achado ${esc(x.qualificacao)}"><summary>[${esc(x.id)}] ${esc(x.titulo)}</summary><p>${esc(x.texto)}</p>
      ${(x.evidencias || []).slice(0, 12).map((e) => {
        if (e && e.lancamento_id) return `<div class="mini">lanç. ${e.lancamento_id} ${esc(e.data || "")} ${esc(e.natureza || "")} ${esc(e.valor_fmt || "")} ${esc(e.contraparte || e.descricao || "")} · ${esc(e.fonte || "")} linha ${e.linha || ""}</div>`;
        if (e && e.saida) return `<div class="mini">${esc(e.categoria || "")} ${esc(e.valor_atribuido_fmt || "")} após crédito ${e.entrada && e.entrada.lancamento_id} → lanç. ${e.saida.lancamento_id} ${esc(e.saida.valor_fmt || "")} ${esc(e.saida.contraparte || e.saida.descricao || "")} (${e.horas_depois} h)</div>`;
        return e && e.fonte ? `<div class="mini">${esc(e.fonte)} ${esc(e.numero || "")}</div>` : "";
      }).join("")}</details>`).join("")}`;
}
async function carregarIA() {
  await verificarModelos();
  if (!estado.caso) {
    $("#ia-analise").innerHTML = `<div class="vazio"><h3>Selecione um caso no topo</h3>
      <p>Depois importe o extrato. Esta tela monta a análise sozinha, neste computador.</p>
      <button type="button" class="primario" data-aba-ir="casos">Ir para o Início</button></div>`;
    return;
  }
  const fs = await api("GET", `/api/casos/${exigirCaso()}/fontes`);
  $("#ia-doc").innerHTML = fs.filter((f) => f.tipo === "pdf").map((f) => `<option value="${f.id}">${esc(f.nome_original)}</option>`).join("");
  const papeis = { boletim: "BO", relatorio_investigacao: "relatório", rif: "RIF", documento: "PDF", extrato: "extrato" };
  $("#ia-docs").innerHTML = fs.length ? "Fontes: " + fs.map((f) => {
    const sel = `<select data-papel="${f.id}">${["", "boletim", "relatorio_investigacao", "rif", "documento", "extrato"].map((p) => `<option value="${p}" ${(f.papel || "") === p ? "selected" : ""}>${papeis[p] || "(papel)"}</option>`).join("")}</select>`;
    return `${esc(f.nome_original)} ${sel}`;
  }).join(" · ") : "Nenhuma fonte neste caso. Importe extratos e o BO na etapa 1. Importar.";
  $$("select[data-papel]").forEach((s) => (s.onchange = async () => {
    try { await api("POST", `/api/fontes/${s.dataset.papel}/papel`, { papel: s.value || null }); }
    catch (e) { alert(e.message); }
  }));
  if (!fs.length) {
    pintarAnalise(null);
    const alvo = $("#ia-analise");
    alvo.innerHTML = `<div class="vazio"><h3>Ainda não há extrato neste caso</h3>
      <p>Importe o arquivo na etapa 1. Depois esta tela monta a análise sozinha.</p>
      <button type="button" class="primario" data-aba-ir="importar">Ir para Importar</button></div>`;
    return;
  }
  try {
    const ctx = await api("GET", `/api/casos/${estado.caso}/contexto`);
    if (ctx.hipotese_crime) $("#ia-hipotese").value = ctx.hipotese_crime;
    if (ctx.vitimas && ctx.vitimas.length) $("#ia-vitimas").value = ctx.vitimas.map((v) => [v.nome, v.doc].filter(Boolean).join(" ")).join("\n");
    if (ctx.investigados && ctx.investigados.length) $("#ia-investigados").value = ctx.investigados.map((v) => [v.nome, v.doc].filter(Boolean).join(" ")).join("\n");
    if (ctx.analise) pintarAnalise(ctx.analise);
    else await gerarAnalise();
  } catch (e) { $("#ia-analise").innerHTML = `<div class="erro">${esc(e.message)}</div>`; }
}
function pintarGemini(g) {
  const st = $("#gemini-status");
  if (!st) return;
  st.classList.remove("ok", "alerta");
  if (g && g.configurado) {
    st.textContent = "Gemini configurado (" + (g.origem || "arquivo") + ", chave " + (g.chave_mascarada || "definida") + "). "
      + (g.confirmado ? "Envio autorizado — no chat, deixe Gemini selecionado." : "Falta marcar a autorização de envio.");
    st.classList.add(g.confirmado ? "ok" : "alerta");
    if (g.modelo) $("#gemini-modelo").value = g.modelo;
    if (g.endpoint) $("#gemini-endpoint").placeholder = g.endpoint;
  } else {
    st.textContent = "Gemini desligado. Sem chave, nada é enviado à nuvem. Siga os passos abaixo se a unidade usar a parceria.";
  }
}
function opcoesModelo(r) {
  const g = r.gemini || {};
  const gem = (g.configurado && g.confirmado && g.modelos) ? g.modelos : [];
  let html = '<option value="">(análise local — sem nuvem)</option>';
  gem.forEach((m) => { html += `<option value="gemini:${esc(m)}">Gemini · ${esc(m)} (nuvem da parceria)</option>`; });
  (r.modelos || []).forEach((m) => { html += `<option value="${esc(m)}">${esc(m)} (Ollama local)</option>`; });
  return { html, gem, g };
}
async function verificarModelos() {
  try {
    const r = await api("GET", "/api/ia/modelos");
    const atual = $("#ia-modelo").value;
    const { html, gem, g } = opcoesModelo(r);
    pintarGemini(g);
    $("#ia-modelo").innerHTML = html;
    const valores = Array.from($("#ia-modelo").options).map((o) => o.value);
    if (atual && valores.includes(atual)) $("#ia-modelo").value = atual;
    else if (gem.length && g.modelo && valores.includes("gemini:" + g.modelo)) $("#ia-modelo").value = "gemini:" + g.modelo;
    else if (gem.length) $("#ia-modelo").value = "gemini:" + gem[0];
    else if (r.modelos && r.modelos.length) $("#ia-modelo").value = r.modelos[0];
    const partes = [];
    if (g.configurado && g.confirmado) partes.push("Gemini autorizado (" + (g.chave_mascarada || "") + ").");
    else if (g.configurado) partes.push("Gemini com chave, sem autorização de envio.");
    if (r.disponivel === false) {
      partes.push((r.erro || "Ollama indisponível") + " — análise local funciona sem Ollama.");
    } else if (r.modelos && r.modelos.length) {
      partes.push(`Ollama ${r.versao || "?"} em ${r.endereco}: ${r.modelos.length} modelo(s).`);
      if (r.bloqueados_nuvem && r.bloqueados_nuvem.length) partes.push("Bloqueados (nuvem Ollama): " + r.bloqueados_nuvem.join(", "));
    } else {
      partes.push(`Ollama em ${r.endereco}, nenhum modelo local.`);
    }
    $("#ia-info").textContent = partes.join(" ");
  } catch (e) {
    $("#ia-modelo").innerHTML = '<option value="">(análise local — sem nuvem)</option>';
    $("#ia-info").textContent = e.message + " — você ainda pode gerar a análise preliminar; as respostas virão dos cálculos do programa.";
  }
}
$("#btn-modelos").onclick = () => verificarModelos();
$("#btn-gemini-salvar").onclick = async () => {
  if (!$("#gemini-ok").checked) return alert("Marque a autorização: os dados do caso saem deste computador para o Google.");
  const corpo = { confirmado: true };
  const chave = $("#gemini-chave").value.trim();
  const modelo = $("#gemini-modelo").value.trim();
  const endpoint = $("#gemini-endpoint").value.trim();
  if (chave) corpo.chave = chave;
  if (modelo) corpo.modelo = modelo;
  if (endpoint) corpo.endpoint = endpoint;
  try {
    const r = await api("POST", "/api/ia/gemini", corpo);
    $("#gemini-chave").value = "";
    pintarGemini(r);
    await verificarModelos();
    $("#gemini-info").textContent = "Chave salva. Testando a conexão (sem enviar dados do caso)…";
    try {
      const t = await api("POST", "/api/ia/gemini/teste", {});
      $("#gemini-info").textContent = "Pronto. Conexão ok. No chat, deixe Gemini selecionado e pergunte. " + (t.resposta || "").slice(0, 60);
    } catch (e) {
      $("#gemini-info").textContent = "Chave salva, mas o teste falhou: " + e.message;
    }
  } catch (e) { alert(e.message); }
};
$("#btn-gemini-teste").onclick = async () => {
  $("#gemini-info").textContent = "Testando o Gemini (sem dados do caso)...";
  try {
    const r = await api("POST", "/api/ia/gemini/teste", {});
    $("#gemini-info").textContent = "Conexão ok: " + (r.resposta || "").slice(0, 80);
  } catch (e) { $("#gemini-info").textContent = e.message; }
};
$("#btn-gemini-remover").onclick = async () => {
  if (!confirm("Remover a chave do Gemini deste computador? O chat volta a ser só local.")) return;
  try {
    await api("POST", "/api/ia/gemini", { remover: true });
    $("#gemini-chave").value = "";
    $("#gemini-ok").checked = false;
    $("#gemini-info").textContent = "Chave removida.";
    await verificarModelos();
  } catch (e) { alert(e.message); }
};
$("#btn-contexto").onclick = async () => {
  try {
    await api("POST", `/api/casos/${exigirCaso()}/contexto`, {
      hipotese_crime: $("#ia-hipotese").value, vitimas: $("#ia-vitimas").value, investigados: $("#ia-investigados").value,
    });
    alert("Contexto salvo.");
  } catch (e) { alert(e.message); }
};
async function gerarAnalise() {
  const el = $("#ia-analise");
  el.innerHTML = '<div class="analise-carregando"><div class="spinner"></div><p>Lendo os lançamentos e montando a análise preliminar neste computador…</p></div>';
  try {
    const r = await api("POST", `/api/casos/${exigirCaso()}/analise`, {
      filtros: lerFiltrosSimples(), hipotese_crime: $("#ia-hipotese").value, vitimas: $("#ia-vitimas").value,
      investigados: $("#ia-investigados").value, janela_vitima_dias: +$("#ia-janela").value || 7,
    });
    const a = await esperarTarefa(r.tarefa, el);
    pintarAnalise(a);
  } catch (e) { msg(el, e.message); }
}
$("#btn-analise").onclick = () => gerarAnalise();
$("#btn-ia-nova").onclick = () => { estado.conversaId = null; pintarChat([]); $("#ia-resposta").innerHTML = ""; };
$("#btn-ia").onclick = async () => {
  const el = $("#ia-resposta");
  const pergunta = $("#ia-pergunta").value.trim();
  if (!pergunta) return alert("Escreva a pergunta (ou clique em Gerar análise preliminar).");
  try {
    const r = await api("POST", `/api/casos/${exigirCaso()}/ia`, corpoIA());
    const res = await esperarTarefa(r.tarefa, el);
    estado.conversaId = res.conversa_id;
    pintarChat(res.historico);
    $("#ia-pergunta").value = "";
    el.innerHTML = `<div class="aviso">${esc(res.aviso)}</div><p class="nota">Modo: ${esc(res.modo)}${res.modelo ? " · modelo " + esc(res.modelo) : ""}${res.referencias && res.referencias.length ? " · base: " + esc(res.referencias.map((x) => x.titulo).join("; ")) : ""}</p>
      <details><summary>Corrigir esta resposta (vira exemplo para as próximas)</summary><textarea id="ia-corr" rows="6">${esc(res.resposta)}</textarea><button id="btn-ia-corr">Salvar resposta revisada</button></details>`;
    $("#btn-ia-corr").onclick = async () => { await api("POST", "/api/ia/correcoes", { caso_id: estado.caso, pergunta, resposta_revisada: $("#ia-corr").value }); alert("Correção salva."); };
    if ($("#ia-gerar").checked) {
      const ctx = await api("GET", `/api/casos/${estado.caso}/analise`);
      if (ctx.analise) pintarAnalise(ctx.analise);
    }
  } catch (e) { msg(el, e.message); }
};
$("#ia-pergunta").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#btn-ia").click(); }
});

// ------------------------------------------------------------------ base de conhecimento
async function carregarConhecimento() {
  const r = await api("GET", `/api/conhecimento${estado.caso ? "?caso=" + estado.caso : ""}`);
  $("#k-lista").innerHTML = `<table><tr><th>ID</th><th>Título</th><th>Categoria</th><th>Escopo</th><th>Trechos</th><th>Incluído</th><th></th></tr>${r.documentos.map((d) => `<tr><td>${d.id}</td><td>${esc(d.titulo)}</td><td>${esc(d.categoria)}</td><td>${d.caso_id ? "caso " + d.caso_id : "geral"}</td><td>${d.trechos}</td><td class="mini">${esc(d.criado_em)} ${esc(d.criado_por || "")}</td><td><button data-krem="${d.id}">desativar</button></td></tr>`).join("")}</table>`;
  $("#k-corr").innerHTML = r.correcoes.map((c) => `<div class="cartao"><b>${esc(c.pergunta)}</b><pre>${esc(c.resposta_revisada)}</pre><span class="mini">${esc(c.criado_por || "")} ${esc(c.criado_em)}</span></div>`).join("");
  $$("button[data-krem]").forEach((b) => (b.onclick = async () => { await api("POST", `/api/conhecimento/${b.dataset.krem}/remover`); carregarConhecimento(); }));
  const p = await api("GET", "/api/perfis");
  $("#k-perfis").innerHTML = `<table><tr><th>Perfil</th><th>Instituição</th><th>Tipo</th><th>Usos</th><th>Colunas mapeadas</th><th></th></tr>${p.aprendidos.map((x) => `<tr><td>${esc(x.nome)}</td><td>${esc(x.instituicao || "")}</td><td>${esc(x.adaptador)}</td><td>${x.usos}</td><td class="mini">${esc(x.mapeamento_json)}</td><td><button data-prem="${x.id}">remover</button></td></tr>`).join("")}${p.embutidos.map((x) => `<tr><td>${esc(x.nome)}</td><td>${esc(x.instituicao || "")}</td><td>${esc(x.adaptador)}</td><td>embutido</td><td class="mini">${esc((x.observacoes || []).join(" "))}</td><td></td></tr>`).join("")}</table>`;
  $$("button[data-prem]").forEach((b) => (b.onclick = async () => { await api("POST", `/api/perfis/${b.dataset.prem}/remover`); carregarConhecimento(); }));
}
$("#btn-k-enviar").onclick = async () => {
  const f = $("#k-arquivo").files[0]; if (!f) return alert("Escolha um arquivo.");
  if (!confirm("Confirme que o documento é de referência ou está ANONIMIZADO, ou que deve ficar restrito a este caso.")) return;
  try { await api("POST", "/api/conhecimento/upload", f, { bruto: true, cabecalhos: { "X-Nome-Arquivo": encodeURIComponent(f.name), "X-Categoria": $("#k-cat").value, "X-Caso": $("#k-caso").checked && estado.caso ? String(estado.caso) : "" } }); carregarConhecimento(); }
  catch (e) { alert(e.message); }
};
$("#btn-k-corr").onclick = async () => { try { await api("POST", "/api/ia/correcoes", { caso_id: estado.caso, pergunta: $("#k-pergunta").value, resposta_revisada: $("#k-resposta").value }); carregarConhecimento(); } catch (e) { alert(e.message); } };
$("#btn-k-modelfile").onclick = () => baixar("POST", "/api/ia/modelfile", { modelo_base: $("#k-base").value }, "Modelfile").catch((e) => alert(e.message));

// ------------------------------------------------------------------ auditoria
async function carregarAuditoria() {
  const r = await api("GET", `/api/casos/${exigirCaso()}/auditoria`);
  $("#auditoria").innerHTML = `<table><tr><th>Quando</th><th>Usuário</th><th>Ação</th><th>Detalhes</th></tr>${r.map((a) => `<tr><td class="mini">${esc(a.em)}</td><td>${esc(a.usuario)}</td><td>${esc(a.acao)}</td><td class="mini">${esc(a.detalhes_json)}</td></tr>`).join("")}</table>`;
}
$("#btn-auditoria").onclick = () => carregarAuditoria();

// ------------------------------------------------------------------ atualização do programa
async function aplicarAtualizacao(r) {
  const b = $("#banner-atu");
  b.innerHTML = `<div class="aviso">Baixando v${esc(r.disponivel)} do GitHub. Seus casos não são alterados. <span id="atu-status"></span></div>`;
  try {
    const t = await api("POST", "/api/atualizacao/aplicar", {});
    const res = await esperarTarefa(t.tarefa, $("#atu-status"));
    if (res.codigo !== 0) {
      b.innerHTML = `<div class="erro">A atualização foi baixada, mas a verificação automática falhou. A versão anterior está em backup_versoes.<pre>${esc(res.texto)}</pre></div>`;
      return;
    }
    b.innerHTML = `<div class="ok"><b>Atualizado para v${esc(r.disponivel)}.</b> Reabrindo o programa…</div>`;
    try { await api("POST", "/api/atualizacao/reiniciar", {}); }
    catch (e) {
      b.innerHTML = `<div class="ok"><b>Atualizado para v${esc(r.disponivel)}.</b> Feche a janela preta e abra de novo pelo atalho para usar a versão nova.</div>`;
    }
  } catch (e) { b.innerHTML = `<div class="erro">Falha ao atualizar: ${esc(e.message)}</div>`; }
}
function faixaNovaVersao(r) {
  const b = $("#banner-atu");
  const selo = $("#selo-atu");
  if (selo) selo.classList.remove("oculto");
  b.innerHTML = `<div class="faixa-desatualizado">
    <div><b>Este programa está desatualizado</b>
      <p>Você está na v${esc(r.instalada)}. Já existe a <b>v${esc(r.disponivel)}</b>. Atualize neste computador — os casos em dados/ não são apagados.</p></div>
    <button type="button" id="btn-atu-aplicar" class="primario">Atualizar agora</button>
  </div>`;
  $("#btn-atu-aplicar").onclick = () => aplicarAtualizacao(r);
}
async function verificarAtualizacao(manual) {
  const b = $("#banner-atu");
  if (manual) b.innerHTML = '<div class="nota" style="padding:6px 16px">Consultando o GitHub…</div>';
  let r;
  try { r = await api("GET", "/api/atualizacao/verificar"); } catch (e) { r = { erro: e.message }; }
  if (r.erro) { b.innerHTML = manual ? `<div class="aviso">${esc(r.erro)}</div>` : ""; return r; }
  if (!r.ha_nova) {
    const selo = $("#selo-atu");
    if (selo) selo.classList.add("oculto");
    if (manual) b.innerHTML = `<div class="ok">Você já está na versão mais recente: <b>v${esc(r.instalada)}</b> (igual ao GitHub).</div>`;
    return r;
  }
  faixaNovaVersao(r);
  return r;
}
$("#btn-atu").onclick = () => verificarAtualizacao(true);

// ------------------------------------------------------------------ início
(async () => {
  const e = await api("GET", "/api/estado");
  $("#versao").textContent = "v" + e.versao;
  verificarAtualizacao(false);
  if (!usuario()) $("#usuario").focus();
  ligarSoltar();
  await carregarCasos();
  abrirAba(localStorage.getItem("aba") || "casos");
})().catch((e) => document.body.insertAdjacentHTML("afterbegin", `<div class="erro">${esc(e.message)}</div>`));
