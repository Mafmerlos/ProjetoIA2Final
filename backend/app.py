import os
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from controllers.receita_controller import receita_bp
from views import resposta_view

# Carrega as variaveis do arquivo .env (como GEMINI_API_KEY e PORT)
load_dotenv()

# Cria a aplicacao Flask (apontando para a pasta frontend) e libera o CORS
app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)

# Registra o Blueprint com as rotas /api/status e /api/receitas/gerar
app.register_blueprint(receita_bp)


# Abre a tela do front-end (index.html) ao acessar http://127.0.0.1:5000/
@app.route("/")
def pagina_inicial():
    return app.send_static_file("index.html")


# Em vez de devolver erro 404/405 em HTML, devolve JSON padronizado pela View
@app.errorhandler(404)
def rota_inexistente(_erro):
    return resposta_view.erro("Rota nao encontrada.", 404)


@app.errorhandler(405)
def metodo_nao_permitido(_erro):
    return resposta_view.erro("Metodo nao permitido para esta rota.", 405)


porta = int(os.getenv("PORT", 5000))

if __name__ == "__main__":
    print(f"Servidor Assistente de Receitas rodando na porta {porta}...", flush=True)
    # 127.0.0.1: so este computador acessa. Com debug=True, 0.0.0.0 abriria o depurador do Flask para a rede
    app.run(host="127.0.0.1", port=porta, debug=True)
