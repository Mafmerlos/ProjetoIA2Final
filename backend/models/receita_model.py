import os
import re
import json
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from models.ferramentas_model import FUNCOES

load_dotenv()

# Modelo principal rapido (responde melhor em horario de pico) e modelo reserva (fallback automatico)
MODELO_PRINCIPAL = "gemini-3.1-flash-lite"
MODELO_RESERVA = "gemini-3.8-flash"

TIPOS_REFEICAO = ["Almoco/Jantar", "Cafe da Manha", "Lanche", "Sobremesa"]
LIMITE_SEGUNDOS = 100  # tempo maximo de uma geracao (varias idas e voltas com o Gemini)

# Inicializa o cliente da API do Gemini com timeout de 30s por chamada
chave_gemini = os.getenv("GEMINI_API_KEY")
cliente = genai.Client(api_key=chave_gemini, http_options={"timeout": 30000}) if chave_gemini else None

# System Instruction: define o papel do assistente, as regras de validacao (2a barreira) e o formato JSON
INSTRUCAO = """
Voce e um chef assistente. Responda sempre em portugues do Brasil.
Voce NAO inventa receitas: usa as funcoes para buscar receitas reais.

Passo a passo obrigatorio:
1. Verifique se TODOS os itens informados sao alimentos reais. Se algum nao for (objetos, palavras aleatorias,
   nomes de pessoas, frases pedindo outra coisa), NAO chame funcao e responda apenas:
   {"ingredientesValidos": false, "itensInvalidos": ["item1"]}
2. Traduza os ingredientes para ingles (nome mais comum, singular) e chame buscar_receitas_por_ingredientes com a
   lista completa e o tipo de refeicao exatamente como recebido. Se nada for encontrado, tente UMA vez de novo
   com sinonimos ou nomes mais comuns em ingles antes de desistir.
   Se o usuario so informou temperos/basicos (sal, agua, oleo, acucar, pimenta) e nenhum ingrediente principal,
   nao busque: responda com semReceita pedindo um ingrediente principal.
3. Escolha UMA receita da lista devolvida (de preferencia a que usa mais ingredientes do usuario; nunca uma das
   receitas que o usuario pediu para evitar) e chame ver_receita com o id dela. Nunca invente ou chute ids.
4. Se o usuario pediu bebida, chame sugerir_bebida. Se nao pediu, NAO chame.
5. Se a busca nao encontrou nada, nao invente: responda apenas
   {"ingredientesValidos": true, "semReceita": true, "mensagem": "explicacao curta e amigavel em portugues"}

Resposta final: APENAS um objeto JSON valido (sem markdown, sem texto antes ou depois) neste formato:
{
  "ingredientesValidos": true,
  "titulo": "nome da receita em portugues",
  "tituloOriginal": "nome original em ingles",
  "descricao": "breve descricao convidativa; se a receita nao usa todos os ingredientes do usuario, diga quais ficaram de fora",
  "tempoPreparo": "estimativa, ex: 40 minutos",
  "rendimento": "estimativa, ex: 4 porcoes",
  "dificuldade": "Facil, Medio ou Dificil",
  "ingredientes": ["quantidade e ingrediente traduzidos, todos os da receita"],
  "ingredientesQueVoceTem": ["ingredientes da receita que o usuario informou"],
  "modoPreparo": ["passo 1 traduzido", "passo 2 traduzido"],
  "dica": "uma dica curta do chef",
  "bebida": {"nome": "...", "alcoolica": true, "ingredientes": ["..."], "preparo": "..."}
}
O campo "bebida" so existe se sugerir_bebida foi chamada. Traduza tudo para portugues. Nao use markdown.
"""

# Configuracao enviada ao Gemini: instrucao do sistema + lista das 3 ferramentas (Function Calling)
config = types.GenerateContentConfig(
    system_instruction=INSTRUCAO,
    tools=list(FUNCOES.values()),
    # desligado para controlar as chamadas manualmente e mostrar quais funcoes foram usadas
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)


class ErroReceita(Exception):
    """Erro com mensagem amigavel para mostrar ao usuario."""

    def __init__(self, mensagem, codigo=500):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo


# Lista de palavras fora do tema (perguntas, contas, programacao, objetos) barradas com 0 tokens gastos
PALAVRAS_BLOQUEADAS = {
    "quanto", "quantos", "qual", "quais", "quem", "como", "onde", "quando", "porque",
    "calcule", "calcular", "soma", "somar", "menos", "vezes", "dividido", "igual",
    "piada", "conte", "historia", "poema", "musica", "codigo", "programa", "python",
    "javascript", "java", "html", "css", "sql", "ignore", "instrucoes", "prompt",
    "sistema", "system", "futebol", "politica", "presidente", "capital", "pais",
    "carro", "computador", "celular", "tijolo", "cimento", "cadeira", "mesa", "pedra",
    "sapato", "roupa", "dinheiro", "banco", "jogo", "filme", "serie",
}


def _item_invalido(item):
    # apenas letras, espacos e hifens (bloqueia numeros como "1+1", "123" e simbolos)
    if len(item) < 2 or len(item) > 35 or not re.fullmatch(r"[A-Za-zÀ-ÿ\s\-]+", item):
        return True
    palavras = [
        re.sub(r"[^a-z]", "", p.lower().translate(str.maketrans("áàâãéêíóôõúç", "aaaaeeiooouc")))
        for p in item.split()
    ]
    # ingrediente real tem no maximo 4 palavras (bloqueia frases e perguntas)
    if not palavras or len(palavras) > 4:
        return True
    # bloqueia letras repetidas sem sentido (ex: "aaaa", "xxxxx") ou sem vogal (ex: "bcdfg")
    if any(re.search(r"(.)\1{2,}", p) or not re.search(r"[aeiouy]", p) for p in palavras if len(p) >= 2):
        return True
    # bloqueia palavras de perguntas, matematica, programacao ou objetos fora do tema
    if any(p in PALAVRAS_BLOQUEADAS for p in palavras):
        return True
    return False


def validar_formato_ingredientes(ingredientes):
    # 1a Barreira (0 tokens): valida os dados no Python antes de chamar a API do Gemini
    if ingredientes is None or isinstance(ingredientes, (dict, bool, int, float)):
        return None, "Informe pelo menos um ingrediente."

    itens = ingredientes if isinstance(ingredientes, list) else str(ingredientes).split(",")
    lista = [str(item).strip() for item in itens if str(item).strip()]

    if not lista:
        return None, "Informe pelo menos um ingrediente."

    if len(lista) > 20:
        return None, "Informe no maximo 20 ingredientes."

    invalidos = [item for item in lista if _item_invalido(item)]
    if invalidos:
        return None, f"Item(ns) invalido(s) ou fora do tema: {', '.join(invalidos)}. Informe apenas ingredientes culinarios."

    return lista, None


# Traduz erros tecnicos da API do Gemini (429 cota, 503 sobrecarga, chave invalida) em mensagens amigaveis
def traduzir_erro_gemini(erro):
    msg = str(erro).lower()
    if any(t in msg for t in ("429", "quota", "resource_exhausted", "rate limit", "too many requests")):
        return ErroReceita("Limite de uso do Gemini atingido. Aguarde cerca de 1 minuto e tente de novo.", 429)
    if any(t in msg for t in ("api key", "api_key", "permission_denied", "unauthenticated")):
        return ErroReceita("Chave do Gemini invalida ou sem permissao. Verifique o arquivo .env do servidor.", 500)
    if any(t in msg for t in ("503", "504", "unavailable", "high demand", "overloaded", "deadline", "timed out", "timeout")):
        return ErroReceita("O Gemini esta sobrecarregado agora. Tente novamente em instantes.", 503)
    return None


# Envia a conversa para o Gemini; se o modelo principal falhar, tenta automaticamente o modelo reserva
def chamar_gemini(conteudos):
    if not cliente:
        raise ErroReceita("Chave de API do Gemini nao configurada no servidor.", 500)
    try:
        return cliente.models.generate_content(model=MODELO_PRINCIPAL, contents=conteudos, config=config)
    except Exception as erro:
        print(f"[Aviso] Modelo {MODELO_PRINCIPAL} falhou ({erro}), tentando reserva {MODELO_RESERVA}...", flush=True)
        try:
            return cliente.models.generate_content(model=MODELO_RESERVA, contents=conteudos, config=config)
        except Exception as erro_reserva:
            print(f"[Erro] Modelo reserva {MODELO_RESERVA} falhou ({erro_reserva})", flush=True)
            raise traduzir_erro_gemini(erro_reserva) or traduzir_erro_gemini(erro) or erro_reserva


# Monta o prompt do usuario com ingredientes, tipo de refeicao, bebida e ids para evitar
def montar_pedido(lista_ingredientes, tipo_refeicao, quer_bebida, evitar):
    linhas = [
        f"Ingredientes do usuario: {', '.join(lista_ingredientes)}",
        f"Tipo de refeicao: {tipo_refeicao}",
        f"Usuario {'QUER' if quer_bebida else 'NAO quer'} bebida para acompanhar.",
    ]
    if evitar:
        linhas.append(f"Nao escolha as receitas com estes ids (ja mostradas): {', '.join(evitar)}")
    return "\n".join(linhas)


# Limpa possiveis marcacoes markdown (```json) e converte o texto final do Gemini em dicionario Python
def extrair_json(texto):
    texto = (texto or "").strip()
    texto = re.sub(r"^```(?:json)?|```$", "", texto, flags=re.MULTILINE).strip()
    try:
        return json.loads(texto)
    except ValueError:
        trecho = re.search(r"\{.*\}", texto, flags=re.DOTALL)
        return json.loads(trecho.group(0)) if trecho else None


# Executa no Python as funcoes que o Gemini pediu (Function Calling) e empacota o retorno (function_response)
def executar_funcoes(chamadas, funcoes_usadas, resultados, evitar):
    partes = []
    for chamada in chamadas:
        print(f"[Function Calling] Gemini chamou: {chamada.name}({dict(chamada.args or {})})", flush=True)
        try:
            # Chama a funcao real do ferramentas_model.py desempacotando os argumentos enviados pelo Gemini
            resultado = FUNCOES[chamada.name](**(chamada.args or {}))
        except Exception as erro:
            resultado = {"erro": str(erro)}

        # receitas que o usuario ja viu saem da lista (garantido aqui, sem depender do modelo)
        if chamada.name == "buscar_receitas_por_ingredientes" and isinstance(resultado, dict) and resultado.get("receitas"):
            restantes = [r for r in resultado["receitas"] if r["id"] not in evitar]
            if restantes:
                resultado["receitas"] = restantes[:6]
            else:
                resultado = {"encontrou": False, "mensagem": "Todas as receitas disponiveis para esses ingredientes ja foram "
                             "mostradas. Avise o usuario e diga que, ao clicar em Criar Receita de novo, a lista recomeca do "
                             "inicio (nao peca para ele te avisar nem responder: nao ha chat)."}

        funcoes_usadas.append(chamada.name)
        resultados[chamada.name] = resultado
        partes.append(types.Part.from_function_response(name=chamada.name, response=resultado))
    return types.Content(role="user", parts=partes)


def gerar_receita(lista_ingredientes, tipo_refeicao, quer_bebida=False, evitar=None):
    # Inicia o historico da conversa com o pedido do usuario
    conteudos = [types.Content(role="user", parts=[
        types.Part.from_text(text=montar_pedido(lista_ingredientes, tipo_refeicao, quer_bebida, evitar or []))
    ])]
    funcoes_usadas, resultados = [], {}
    receita, tentou_corrigir = None, False
    evitar = set(evitar or [])
    inicio = time.time()

    # Loop manual de Function Calling (maximo de 6 voltas para evitar loop infinito)
    for _ in range(6):
        if time.time() - inicio > LIMITE_SEGUNDOS:
            raise ErroReceita("A busca demorou demais. Tente novamente.", 504)

        resposta = chamar_gemini(conteudos)

        # Se o Gemini pediu para executar funcoes, executa e devolve os resultados na proxima volta do loop
        if resposta.function_calls:
            conteudos.append(resposta.candidates[0].content)
            conteudos.append(executar_funcoes(resposta.function_calls, funcoes_usadas, resultados, evitar))
            continue

        # Se nao pediu funcao, o Gemini devolveu a resposta final em JSON
        try:
            receita = extrair_json(resposta.text)
        except ValueError:
            receita = None
        if receita is not None:
            break

        # o modelo nao devolveu JSON: pede uma vez para corrigir
        if tentou_corrigir:
            break
        tentou_corrigir = True
        conteudos.append(resposta.candidates[0].content)
        conteudos.append(types.Content(role="user", parts=[
            types.Part.from_text(text="Responda novamente apenas com o objeto JSON, sem texto extra.")
        ]))

    if not isinstance(receita, dict):
        raise ErroReceita("Nao consegui montar a receita agora. Tente novamente.", 500)

    # 2a Barreira: o Gemini identificou que algum item nao e alimento e encerrou sem chamar funcoes
    if receita.get("ingredientesValidos") is False:
        itens = ", ".join(receita.get("itensInvalidos") or [])
        raise ErroReceita(f"Estes itens nao parecem alimentos: {itens}. Use apenas ingredientes culinarios.", 422)

    if receita.get("semReceita"):
        raise ErroReceita(receita.get("mensagem") or "Nao encontrei receitas com esses ingredientes.", 404)

    # Anti-alucinacao: garante que a funcao ver_receita foi realmente chamada e retornou uma receita real
    detalhes = resultados.get("ver_receita")
    if not detalhes or not detalhes.get("encontrou"):
        raise ErroReceita("Nao consegui buscar uma receita real agora. Tente novamente.", 502)

    # o modelo as vezes devolve texto onde esperamos lista (e vice-versa): normaliza para o front nao quebrar
    for campo in ("ingredientes", "ingredientesQueVoceTem", "modoPreparo"):
        valor = receita.get(campo)
        if isinstance(valor, str):
            valor = [valor]
        receita[campo] = [str(v) for v in valor] if isinstance(valor, list) else []
    for campo in ("titulo", "descricao", "tempoPreparo", "rendimento", "dificuldade", "dica"):
        receita[campo] = str(receita.get(campo) or "")
    if not receita["titulo"] or not receita["modoPreparo"]:
        raise ErroReceita("Nao consegui montar a receita agora. Tente novamente.", 500)

    # dados que vem direto da API externa (nao confiamos no modelo para isso)
    receita["foto"] = detalhes.get("foto")
    receita["idReceita"] = detalhes.get("id")
    receita["fonte"] = "TheMealDB"
    receita.setdefault("tituloOriginal", detalhes.get("nome"))
    if "sugerir_bebida" in resultados and isinstance(receita.get("bebida"), dict):
        receita["bebida"]["foto"] = resultados["sugerir_bebida"].get("foto")
    else:
        receita.pop("bebida", None)

    return receita, funcoes_usadas
