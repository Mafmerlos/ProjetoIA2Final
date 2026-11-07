import unicodedata
import requests

# Endpoints publicos (chave gratuita "1") das duas APIs externas
URL_MEALDB = "https://www.themealdb.com/api/json/v1/1"
URL_COCKTAILDB = "https://www.thecocktaildb.com/api/json/v1/1"


# Remove acentos e deixa em minusculas para comparar o tipo de refeicao com seguranca
def _sem_acento(texto):
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()


def _filtrar(parametro, valor):
    # a TheMealDB so filtra por UM valor por vez; devolve {id: nome}
    resposta = requests.get(f"{URL_MEALDB}/filter.php", params={parametro: valor}, timeout=10)
    receitas = resposta.json().get("meals")
    if not isinstance(receitas, list):
        return {}
    return {r["idMeal"]: r["strMeal"] for r in receitas}


_nomes_cache = []


def _nomes_ingredientes():
    # lista oficial de ingredientes da TheMealDB (busca uma vez e guarda)
    if not _nomes_cache:
        resposta = requests.get(f"{URL_MEALDB}/list.php", params={"i": "list"}, timeout=10)
        for item in resposta.json().get("meals") or []:
            if item.get("strIngredient"):
                _nomes_cache.append(item["strIngredient"].strip().lower().replace(" ", "_"))
    return _nomes_cache


def _resolver_ingrediente(nome):
    # "eggs" -> "egg"; "chocolate" -> dark_chocolate, milk_chocolate...; se nao achar, usa o nome como veio
    try:
        nomes = _nomes_ingredientes()
    except Exception:
        return [nome]

    # singular e plural sao ingredientes separados na TheMealDB (tomato / tomatoes): usa os dois se existirem
    candidatos = [nome, nome + "s", nome + "es"]
    if nome.endswith("es"):
        candidatos.append(nome[:-2])
    if nome.endswith("s"):
        candidatos.append(nome[:-1])
    exatos = [c for c in dict.fromkeys(candidatos) if c in nomes]
    if exatos:
        return exatos

    palavras = set(nome.split("_"))
    parecidos = sorted((n for n in nomes if palavras <= set(n.split("_"))), key=len)
    return parecidos[:4] or [nome]


def buscar_receitas_por_ingredientes(ingredientes: list[str], tipo_refeicao: str = "") -> dict:
    """Busca receitas reais que usam TODOS os ingredientes informados (ou o maximo possivel deles).

    Args:
        ingredientes: lista de ingredientes em ingles, ex: ["chicken", "rice"]. Passe todos de uma vez.
        tipo_refeicao: tipo de refeicao pedido pelo usuario, exatamente como recebido
            (Almoco/Jantar, Cafe da Manha, Lanche ou Sobremesa).
    """
    if isinstance(ingredientes, str):
        ingredientes = [ingredientes]

    por_ingrediente = {}
    sem_resultado = []
    falhas = 0
    for ingrediente in ingredientes:
        nome = str(ingrediente).strip().lower().replace(" ", "_")
        if not nome or nome in por_ingrediente or nome in sem_resultado:
            continue
        achadas = {}
        for variante in _resolver_ingrediente(nome):
            try:
                achadas.update(_filtrar("i", variante))
            except Exception:
                falhas += 1
        if achadas:
            por_ingrediente[nome] = achadas
        else:
            sem_resultado.append(nome)

    if not por_ingrediente:
        if falhas:
            return {"encontrou": False, "mensagem": "A API de receitas nao respondeu agora. Tente novamente em instantes.",
                    "ingredientes_sem_resultado": sem_resultado}
        return {"encontrou": False,
                "mensagem": "Nenhuma receita encontrada. Tente outro nome em ingles (mais comum ou sinonimo).",
                "ingredientes_sem_resultado": sem_resultado}

    # quantos dos ingredientes cada receita usa
    contagem, nomes = {}, {}
    for ingrediente, achadas in por_ingrediente.items():
        for id_receita, nome_receita in achadas.items():
            contagem[id_receita] = contagem.get(id_receita, 0) + 1
            nomes[id_receita] = nome_receita

    # sobremesa so com receitas de sobremesa; os outros tipos nunca devolvem sobremesa
    tipo = _sem_acento(tipo_refeicao)
    try:
        if "sobremesa" in tipo:
            sobremesas = _filtrar("c", "Dessert")
            contagem = {i: c for i, c in contagem.items() if i in sobremesas}
        else:
            sobremesas = _filtrar("c", "Dessert")
            contagem = {i: c for i, c in contagem.items() if i not in sobremesas}
        cafe = set(_filtrar("c", "Breakfast")) if "cafe" in tipo else set()
    except Exception:
        cafe = set()

    if not contagem:
        return {"encontrou": False,
                "mensagem": f"Nenhuma receita do tipo '{tipo_refeicao}' encontrada com esses ingredientes.",
                "ingredientes_sem_resultado": sem_resultado}

    melhor = max(contagem.values())

    # quando nenhuma receita usa todos, quem usa o ingrediente mais raro (o principal) vem primeiro;
    # senao a lista seria dominada pelo ingrediente mais comum (ex: tomate)
    def raridade(i):
        return sum(1 / len(achadas) for achadas in por_ingrediente.values() if i in achadas)

    melhores = [i for i, c in contagem.items() if c == melhor]
    if melhor < len(por_ingrediente):
        # parcial: fica so quem usa o ingrediente principal (o de menos receitas), se houver
        principal = min(por_ingrediente, key=lambda k: len(por_ingrediente[k]))
        melhores = [i for i in melhores if i in por_ingrediente[principal]] or melhores

    candidatas = sorted(melhores, key=lambda i: (i not in cafe, -raridade(i), nomes[i]))[:12]

    receitas = [
        {"id": i, "nome": nomes[i],
         "ingredientes_usados": [ing for ing, achadas in por_ingrediente.items() if i in achadas]}
        for i in candidatas
    ]
    return {
        "encontrou": True,
        "usam_todos_os_ingredientes": melhor == len(por_ingrediente) and not sem_resultado,
        "ingredientes_sem_resultado": sem_resultado,
        "receitas": receitas,
    }


def ver_receita(id_receita: str) -> dict:
    """Retorna os detalhes de uma receita: ingredientes, modo de preparo e foto.

    Args:
        id_receita: id da receita retornado pela busca de receitas.
    """
    resposta = requests.get(f"{URL_MEALDB}/lookup.php", params={"i": id_receita}, timeout=10)
    receitas = resposta.json().get("meals")  # id invalido volta como texto ("Invalid ID")

    if not isinstance(receitas, list) or not receitas:
        return {"encontrou": False, "mensagem": "Receita nao encontrada."}

    r = receitas[0]
    # A TheMealDB guarda os ingredientes em 20 campos separados (strIngredient1..20 e strMeasure1..20)
    ingredientes = []
    for i in range(1, 21):
        nome = (r.get(f"strIngredient{i}") or "").strip()
        medida = (r.get(f"strMeasure{i}") or "").strip()
        if nome:
            ingredientes.append(f"{medida} {nome}".strip())

    return {
        "encontrou": True,
        "id": r["idMeal"],
        "nome": r["strMeal"],
        "categoria": r.get("strCategory"),
        "origem": r.get("strArea"),
        "ingredientes": ingredientes,
        "modo_preparo": r.get("strInstructions"),
        "foto": r.get("strMealThumb"),
    }


def sugerir_bebida() -> dict:
    """Sugere uma bebida aleatoria para acompanhar a refeicao."""
    # Consulta a API TheCocktailDB para sortear uma bebida real
    resposta = requests.get(f"{URL_COCKTAILDB}/random.php", timeout=10)
    b = resposta.json()["drinks"][0]

    ingredientes = [b[f"strIngredient{i}"] for i in range(1, 16) if b.get(f"strIngredient{i}")]

    return {
        "nome": b["strDrink"],
        "alcoolica": b.get("strAlcoholic"),
        "ingredientes": ingredientes,
        "preparo": b.get("strInstructions"),
        "foto": b.get("strDrinkThumb"),
    }


# usado pelo receita_model.py para achar a funcao pelo nome que o Gemini pedir
FUNCOES = {
    "buscar_receitas_por_ingredientes": buscar_receitas_por_ingredientes,
    "ver_receita": ver_receita,
    "sugerir_bebida": sugerir_bebida,
}
