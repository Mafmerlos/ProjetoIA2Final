const URL_BASE = "http://localhost:5000/api";
const TIPOS_REFEICAO = ["Almoco/Jantar", "Cafe da Manha", "Lanche", "Sobremesa"];

const textoStatus = document.getElementById("textoStatus");
const alertaErro = document.getElementById("alertaErro");
const abaGerador = document.getElementById("abaGerador");
const abaSalvas = document.getElementById("abaSalvas");
const formulario = document.getElementById("formulario");
const campoIngrediente = document.getElementById("campoIngrediente");
const botaoAdicionar = document.getElementById("botaoAdicionar");
const blocoTags = document.getElementById("blocoTags");
const opcoesRefeicao = document.getElementById("opcoesRefeicao");
const querBebida = document.getElementById("querBebida");
const erroFormulario = document.getElementById("erroFormulario");
const botaoCriar = document.getElementById("botaoCriar");
const cartaoReceita = document.getElementById("cartaoReceita");

let listaIngredientes = ["Ovos", "Tomate", "Queijo"];
let tipoRefeicao = TIPOS_REFEICAO[0];
let receitaAtual = null;
let carregando = false;
let receitasSalvas = [];
let idsVistos = [];
let chaveBusca = "";

// ---------- utilidades ----------
// Cria elementos HTML usando textContent (nunca innerHTML) para impedir ataques XSS
function el(tag, classe, texto) {
  const e = document.createElement(tag);
  if (classe) e.className = classe;
  if (texto !== undefined && texto !== null) e.textContent = texto;
  return e;
}

function mostrarErro(texto) {
  alertaErro.textContent = texto;
  alertaErro.classList.toggle("oculto", !texto);
}

// ---------- status do servidor ----------
async function checarStatus() {
  try {
    const resposta = await fetch(`${URL_BASE}/status`);
    if (!resposta.ok) throw new Error();
    const dados = await resposta.json();
    if (dados.status !== "online") throw new Error();
    if (dados.temChaveConfigurada) {
      textoStatus.textContent = "Servidor online";
      textoStatus.className = "texto-status online";
    } else {
      textoStatus.textContent = "Servidor online, sem chave do Gemini";
      textoStatus.className = "texto-status sem-chave";
    }
  } catch (e) {
    textoStatus.textContent = "Servidor offline";
    textoStatus.className = "texto-status offline";
  }
}

// ---------- abas ----------
function mudarAba(aba) {
  mostrarErro("");
  document.querySelectorAll(".botao-aba").forEach((b) => {
    b.classList.toggle("ativa", b.dataset.aba === aba);
  });
  abaGerador.classList.toggle("oculto", aba !== "gerador");
  abaSalvas.classList.toggle("oculto", aba !== "salvas");
  if (aba === "salvas") renderizarSalvas();
}

document.querySelectorAll(".botao-aba").forEach((b) => {
  b.addEventListener("click", () => mudarAba(b.dataset.aba));
});

// ---------- formulario ----------
function renderizarTags() {
  blocoTags.replaceChildren();
  if (listaIngredientes.length === 0) {
    blocoTags.appendChild(el("span", "texto-vazio", "Nenhum item adicionado."));
    return;
  }
  listaIngredientes.forEach((item, indice) => {
    const tag = el("span", "tag");
    tag.appendChild(el("span", null, item));
    const remover = el("button", null, "x");
    remover.type = "button";
    remover.addEventListener("click", () => {
      listaIngredientes.splice(indice, 1);
      renderizarTags();
    });
    tag.appendChild(remover);
    blocoTags.appendChild(tag);
  });
}

function renderizarOpcoes() {
  opcoesRefeicao.replaceChildren();
  TIPOS_REFEICAO.forEach((tipo) => {
    const botao = el("button", "opcao" + (tipo === tipoRefeicao ? " ativa" : ""), tipo);
    botao.type = "button";
    botao.addEventListener("click", () => {
      tipoRefeicao = tipo;
      renderizarOpcoes();
    });
    opcoesRefeicao.appendChild(botao);
  });
}

function mostrarErroFormulario(texto, ms) {
  erroFormulario.textContent = texto;
  erroFormulario.classList.toggle("oculto", !texto);
  if (texto && ms) setTimeout(() => erroFormulario.classList.add("oculto"), ms);
}

// Palavras fora do tema (perguntas, matematica, programacao, objetos) bloqueadas ja no front-end
const PALAVRAS_BLOQUEADAS = new Set([
  "quanto", "quantos", "qual", "quais", "quem", "como", "onde", "quando", "porque",
  "calcule", "calcular", "soma", "somar", "menos", "vezes", "dividido", "igual",
  "piada", "conte", "historia", "poema", "musica", "codigo", "programa", "python",
  "javascript", "java", "html", "css", "sql", "ignore", "instrucoes", "prompt",
  "sistema", "system", "futebol", "politica", "presidente", "capital", "pais",
  "carro", "computador", "celular", "tijolo", "cimento", "cadeira", "mesa", "pedra",
  "sapato", "roupa", "dinheiro", "banco", "jogo", "filme", "serie",
]);

// Valida se o item tem apenas letras, ate 4 palavras e nao contem termos fora do tema
function ingredienteValido(item) {
  if (item.length < 2 || item.length > 35 || !/^[A-Za-zÀ-ÿ\s\-]+$/.test(item)) return false;
  const palavras = item.trim().split(/\s+/);
  if (palavras.length > 4) return false;
  return !palavras.some((p) => {
    const limpa = p.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z]/g, "");
    return (
      PALAVRAS_BLOQUEADAS.has(limpa) ||
      /(.)\1{2,}/i.test(limpa) ||
      (limpa.length >= 2 && !/[aeiouy]/i.test(limpa))
    );
  });
}

function adicionarIngrediente() {
  // aceita varios de uma vez separados por virgula
  const itens = campoIngrediente.value.split(",").map((i) => i.trim()).filter(Boolean);
  if (itens.length === 0) return true;

  const invalidos = [];
  const repetidos = [];
  itens.forEach((item) => {
    if (!ingredienteValido(item)) {
      invalidos.push(item);
    } else if (listaIngredientes.some((i) => i.toLowerCase() === item.toLowerCase())) {
      repetidos.push(item);
    } else {
      listaIngredientes.push(item);
    }
  });

  campoIngrediente.value = "";
  renderizarTags();

  if (invalidos.length) {
    mostrarErroFormulario(`Item(ns) invalido(s): "${invalidos.join(", ")}". Digite apenas nomes de alimentos (sem numeros ou frases).`, 4000);
    return false;
  }
  mostrarErroFormulario(repetidos.length ? `"${repetidos.join(", ")}" ja foi adicionado.` : "", 2500);
  return true;
}

botaoAdicionar.addEventListener("click", adicionarIngrediente);
campoIngrediente.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    adicionarIngrediente();
  }
});

// ---------- gerar receita ----------
formulario.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (carregando) return;

  // se o usuario digitou algo e nao clicou em Adicionar, considera o texto
  if (campoIngrediente.value.trim()) {
    if (!adicionarIngrediente()) return;
  }

  if (listaIngredientes.length === 0) {
    mostrarErroFormulario("Adicione ao menos um ingrediente.");
    return;
  }

  mostrarErroFormulario("");
  mostrarErro("");

  // pedir de novo com os mesmos dados devolve outra receita; mudou algo, zera a lista
  const chave = JSON.stringify([listaIngredientes.map((i) => i.toLowerCase()).sort(), tipoRefeicao]);
  if (chave !== chaveBusca) {
    chaveBusca = chave;
    idsVistos = [];
  }

  carregando = true;
  botaoCriar.disabled = true;
  botaoCriar.textContent = "Buscando receita...";

  const controle = new AbortController();
  const limite = setTimeout(() => controle.abort(), 150000);

  try {
    const resposta = await fetch(`${URL_BASE}/receitas/gerar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controle.signal,
      body: JSON.stringify({
        ingredientes: listaIngredientes,
        tipoRefeicao: tipoRefeicao,
        bebida: querBebida.checked,
        evitar: idsVistos,
      }),
    });
    const json = await resposta.json().catch(() => ({}));

    if (!resposta.ok || !json.sucesso || !json.dados) {
      throw new Error(json.mensagem || json.erro || "Nao foi possivel gerar a receita.");
    }

    receitaAtual = json.dados;
    receitaAtual.funcoes = json.funcoes || [];
    if (receitaAtual.idReceita) idsVistos.push(String(receitaAtual.idReceita));
    renderizarReceita();
  } catch (erro) {
    receitaAtual = null;
    cartaoReceita.classList.add("oculto");
    chaveBusca = ""; // proximo pedido recomeca a lista de receitas ja vistas
    if (erro.name === "AbortError") {
      mostrarErro("A busca demorou demais. Tente novamente.");
    } else if (erro instanceof TypeError) {
      mostrarErro("Erro ao conectar ao servidor. O backend esta rodando?");
    } else {
      mostrarErro(erro.message);
    }
  } finally {
    clearTimeout(limite);
    carregando = false;
    botaoCriar.disabled = false;
    botaoCriar.textContent = "Criar Receita";
  }
});

// ---------- cartao da receita ----------
function jaSalva(receita) {
  return receitasSalvas.some((r) => r.titulo === receita.titulo);
}

function textoParaCopiar(r) {
  const ingredientes = (r.ingredientes || []).map((i) => `- ${i}`).join("\n");
  const passos = (r.modoPreparo || []).map((p, i) => `${i + 1}. ${p}`).join("\n");
  return `${r.titulo}\n\n${r.descricao}\n\nTempo: ${r.tempoPreparo} | Rendimento: ${r.rendimento}\n\nIngredientes:\n${ingredientes}\n\nModo de Preparo:\n${passos}\n\nDica: ${r.dica || ""}`;
}

function renderizarReceita() {
  const r = receitaAtual;
  cartaoReceita.replaceChildren();
  if (!r) {
    cartaoReceita.classList.add("oculto");
    return;
  }

  // titulo e botoes
  const cabecalho = el("div", "receita-cabecalho");
  cabecalho.appendChild(el("h2", "titulo-secao", r.titulo));
  const acoes = el("div", "acoes-topo");

  const botaoSalvar = el("button", "botao-salvar" + (jaSalva(r) ? " salva" : ""), jaSalva(r) ? "Salva" : "Salvar");
  botaoSalvar.type = "button";
  botaoSalvar.addEventListener("click", () => {
    alternarSalva(r);
    renderizarReceita();
  });
  acoes.appendChild(botaoSalvar);

  const botaoCopiar = el("button", "botao-copiar", "Copiar");
  botaoCopiar.type = "button";
  botaoCopiar.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(textoParaCopiar(r));
      botaoCopiar.textContent = "Copiado";
      setTimeout(() => (botaoCopiar.textContent = "Copiar"), 2000);
    } catch (e) {
      botaoCopiar.textContent = "Nao foi possivel";
    }
  });
  acoes.appendChild(botaoCopiar);
  cabecalho.appendChild(acoes);
  cartaoReceita.appendChild(cabecalho);

  if (r.tituloOriginal && r.tituloOriginal !== r.titulo) {
    cartaoReceita.appendChild(el("p", "receita-original", `Nome original: ${r.tituloOriginal}`));
  }

  if (r.foto) {
    const foto = el("img", "receita-foto");
    foto.src = r.foto;
    foto.alt = r.titulo;
    foto.addEventListener("error", () => foto.remove());
    cartaoReceita.appendChild(foto);
  }

  cartaoReceita.appendChild(el("p", "descricao", r.descricao));

  // tempo / rendimento / dificuldade
  const info = el("div", "linha-info");
  [["Tempo:", r.tempoPreparo || "30 min"], ["Rendimento:", r.rendimento || "2 porcoes"], ["Dificuldade:", r.dificuldade || "Facil"]]
    .forEach(([rotulo, valor]) => {
      const item = el("div", "item-info");
      item.appendChild(el("span", "rotulo-info", rotulo));
      item.appendChild(el("span", "valor-info", valor));
      info.appendChild(item);
    });
  cartaoReceita.appendChild(info);

  // ingredientes
  const blocoIng = el("div", "bloco");
  blocoIng.appendChild(el("h3", "titulo-bloco-receita", "Ingredientes"));
  (r.ingredientes || []).forEach((ing) => blocoIng.appendChild(el("p", "item-ingrediente", ing)));
  if (r.ingredientesQueVoceTem && r.ingredientesQueVoceTem.length > 0) {
    blocoIng.appendChild(el("p", "texto-opcionais", `Voce ja tem: ${r.ingredientesQueVoceTem.join(", ")}`));
  }
  cartaoReceita.appendChild(blocoIng);

  // modo de preparo
  const blocoPassos = el("div", "bloco");
  blocoPassos.appendChild(el("h3", "titulo-bloco-receita", "Modo de Preparo"));
  (r.modoPreparo || []).forEach((passo, i) => {
    const linha = el("div", "linha-passo");
    linha.appendChild(el("span", "numero-passo", `${i + 1}.`));
    linha.appendChild(el("span", "texto-passo", passo));
    blocoPassos.appendChild(linha);
  });
  cartaoReceita.appendChild(blocoPassos);

  // dica
  if (r.dica) {
    const dica = el("div", "caixa-dica");
    dica.appendChild(el("p", "titulo-dica", "Dica do Chef:"));
    dica.appendChild(el("p", "texto-dica", r.dica));
    cartaoReceita.appendChild(dica);
  }

  // bebida (TheCocktailDB)
  if (r.bebida) {
    const b = r.bebida;
    const caixa = el("div", "caixa-bebida");
    if (b.foto) {
      const imagem = el("img", "bebida-foto");
      imagem.src = b.foto;
      imagem.alt = b.nome;
      imagem.addEventListener("error", () => imagem.remove());
      caixa.appendChild(imagem);
    }
    caixa.appendChild(el("p", "titulo-dica", "Bebida sugerida:"));
    const tipo = b.alcoolica === true || /^alco/i.test(String(b.alcoolica)) ? "com alcool" : "sem alcool";
    caixa.appendChild(el("p", "texto-dica", `${b.nome} (${tipo})`));
    if (b.ingredientes && b.ingredientes.length) {
      caixa.appendChild(el("p", "texto-dica", `Ingredientes: ${b.ingredientes.join(", ")}`));
    }
    if (b.preparo) caixa.appendChild(el("p", "texto-dica", b.preparo));
    cartaoReceita.appendChild(caixa);
  }

  const fonte = r.fonte ? `Receita real: ${r.fonte}` : "";
  const funcoes = r.funcoes && r.funcoes.length ? ` | Funcoes chamadas pelo Gemini: ${r.funcoes.join(", ")}` : "";
  if (fonte || funcoes) cartaoReceita.appendChild(el("p", "rodape-fonte", fonte + funcoes));

  const outra = el("button", "botao-nova botao-outra", "Outra receita com esses ingredientes");
  outra.type = "button";
  outra.addEventListener("click", () => formulario.requestSubmit());
  cartaoReceita.appendChild(outra);

  const voltar = el("button", "botao-nova", "Voltar para o formulario");
  voltar.type = "button";
  voltar.addEventListener("click", () => {
    receitaAtual = null;
    renderizarReceita();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });
  cartaoReceita.appendChild(voltar);

  cartaoReceita.classList.remove("oculto");
}

// ---------- receitas salvas (localStorage) ----------
function carregarSalvas() {
  try {
    const salvas = localStorage.getItem("receitas_salvas");
    if (salvas) receitasSalvas = JSON.parse(salvas);
  } catch (e) {
    console.warn("Erro ao carregar dados salvos:", e);
  }
}

function gravarSalvas() {
  try {
    localStorage.setItem("receitas_salvas", JSON.stringify(receitasSalvas));
  } catch (e) {
    console.warn("Erro ao salvar:", e);
  }
}

function alternarSalva(receita) {
  if (jaSalva(receita)) {
    receitasSalvas = receitasSalvas.filter((r) => r.titulo !== receita.titulo);
  } else {
    receitasSalvas = [receita, ...receitasSalvas];
  }
  gravarSalvas();
}

function renderizarSalvas() {
  abaSalvas.replaceChildren();

  if (receitasSalvas.length === 0) {
    const vazio = el("div", "vazio");
    vazio.appendChild(el("h3", null, "Nenhuma receita salva"));
    vazio.appendChild(el("p", null, "As receitas que voce salvar durante o uso aparecerao listadas aqui."));
    abaSalvas.appendChild(vazio);
    return;
  }

  abaSalvas.appendChild(el("h2", "titulo-lista", "Minhas Receitas Salvas"));
  receitasSalvas.forEach((receita, indice) => {
    const item = el("div", "item-salvo");
    const info = el("div", "info");
    info.appendChild(el("p", "nome-salvo", receita.titulo));
    info.appendChild(el("p", "detalhes-salvo", `Tempo: ${receita.tempoPreparo} | Rendimento: ${receita.rendimento}`));
    item.appendChild(info);

    const botoes = el("div", "botoes-acao");
    const abrir = el("button", "botao-abrir", "Abrir");
    abrir.type = "button";
    abrir.addEventListener("click", () => {
      receitaAtual = receita;
      renderizarReceita();
      mudarAba("gerador");
    });
    const excluir = el("button", "botao-excluir", "Excluir");
    excluir.type = "button";
    excluir.addEventListener("click", () => {
      receitasSalvas = receitasSalvas.filter((_, i) => i !== indice);
      gravarSalvas();
      renderizarSalvas();
    });
    botoes.appendChild(abrir);
    botoes.appendChild(excluir);
    item.appendChild(botoes);
    abaSalvas.appendChild(item);
  });
}

// ---------- inicio ----------
carregarSalvas();
renderizarTags();
renderizarOpcoes();
checarStatus();
