from flask import Blueprint, request
from models import receita_model
from views import resposta_view

receita_bp = Blueprint("receita", __name__)


@receita_bp.route("/api/status", methods=["GET"])
def verificar_status():
    return resposta_view.status(bool(receita_model.chave_gemini))


@receita_bp.route("/api/receitas/gerar", methods=["POST"])
def gerar_receita():
    try:
        dados = request.get_json(silent=True)
        if not isinstance(dados, dict):
            dados = {}
        lista, mensagem_erro = receita_model.validar_formato_ingredientes(dados.get("ingredientes"))
        if mensagem_erro:
            return resposta_view.erro(mensagem_erro, 400)

        tipo = dados.get("tipoRefeicao")
        if tipo not in receita_model.TIPOS_REFEICAO:
            tipo = receita_model.TIPOS_REFEICAO[0]

        evitar = dados.get("evitar") if isinstance(dados.get("evitar"), list) else []
        evitar = [str(i) for i in evitar][:20]
        receita, funcoes = receita_model.gerar_receita(lista, tipo, bool(dados.get("bebida")), evitar)
        return resposta_view.sucesso(receita, funcoes)

    except receita_model.ErroReceita as erro:
        return resposta_view.erro(erro.mensagem, erro.codigo)
    except Exception as erro_geral:
        print(f"[Erro Geral] {erro_geral}", flush=True)
        return resposta_view.erro("Erro ao gerar a receita. Tente novamente.", 500)
