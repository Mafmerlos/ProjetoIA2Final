from flask import jsonify


def inicio(modelos):
    return jsonify({
        "servico": "API Assistente de Receitas",
        "status": "online",
        "modelos": modelos
    }), 200


def status(tem_chave):
    return jsonify({
        "status": "online",
        "servico": "API Assistente de Receitas - Projeto Final IA2",
        "temChaveConfigurada": tem_chave
    }), 200


def sucesso(dados, funcoes=None):
    return jsonify({
        "sucesso": True,
        "dados": dados,
        "funcoes": funcoes or []
    }), 200


def erro(mensagem, codigo=400):
    return jsonify({
        "sucesso": False,
        "erro": mensagem,
        "mensagem": mensagem
    }), codigo
