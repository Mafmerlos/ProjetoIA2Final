from flask import jsonify


def inicio(modelos):
    return jsonify({
        "servico": "API Assistente de Receitas",
        "status": "online",
        "modelos": modelos
    }), 200


# Padroniza a resposta de GET /api/status
def status(tem_chave):
    return jsonify({
        "status": "online",
        "servico": "API Assistente de Receitas - Projeto Final IA2",
        "temChaveConfigurada": tem_chave
    }), 200


# Padroniza a resposta de sucesso (HTTP 200) com a receita e as funcoes chamadas pelo Gemini
def sucesso(dados, funcoes=None):
    return jsonify({
        "sucesso": True,
        "dados": dados,
        "funcoes": funcoes or []
    }), 200


# Padroniza qualquer resposta de erro (HTTP 400, 404, 422, 429, 500, etc.)
def erro(mensagem, codigo=400):
    return jsonify({
        "sucesso": False,
        "erro": mensagem,
        "mensagem": mensagem
    }), codigo
