# Assistente de Receitas - Projeto Final IA 2

O usuário informa os ingredientes que tem em casa e o tipo de refeição. O Gemini usa **Function Calling** para buscar uma receita real (TheMealDB), traduzi-la para português e, se o usuário quiser, sugerir uma bebida (TheCocktailDB).

**Integrantes:** Matheus Figueira Merlos e João Pedro Marucci Pagluiso

---

## Estrutura do Projeto (Padrão MVC)

```
Projeto Final/
├── backend/
│   ├── app.py                       # Flask, CORS e registro do Blueprint
│   ├── models/
│   │   ├── receita_model.py         # Gemini: instrução, fallback de modelo e loop de Function Calling
│   │   └── ferramentas_model.py     # As 3 funções que o Gemini pode chamar (APIs externas)
│   ├── views/
│   │   └── resposta_view.py         # Padroniza as respostas JSON
│   ├── controllers/
│   │   └── receita_controller.py    # Rotas /api/status e /api/receitas/gerar + validação
│   ├── requirements.txt
│   ├── .env                         # GEMINI_API_KEY (não vai para o GitHub)
│   └── .env.example
├── frontend/                        # HTML + CSS + JS puro (visual do projeto anterior em React)
│   ├── index.html
│   ├── style.css
│   └── script.js
└── README.md
```

---

## Atendimento aos Requisitos

| Requisito | Implementação | Arquivo |
| :--- | :--- | :--- |
| **API do Gemini** | SDK `google-genai`, com modelo reserva automático | `models/receita_model.py` |
| **Function Calling** | Funções declaradas em `tools`; o backend executa cada chamada do modelo num loop manual | `models/receita_model.py` |
| **APIs Externas** | TheMealDB (receitas) e TheCocktailDB (bebida) | `models/ferramentas_model.py` |
| **Front-end** | Formulário com ingredientes, tipo de refeição, receita salva e cópia | `frontend/` |

### Funções que o Gemini pode chamar

| Função | API | O que faz |
| :--- | :--- | :--- |
| `buscar_receitas_por_ingredientes(ingredientes, tipo_refeicao)` | TheMealDB | Consulta **cada** ingrediente e cruza os resultados; sobremesa só devolve sobremesas e os demais tipos nunca devolvem sobremesa |
| `ver_receita(id_receita)` | TheMealDB | Ingredientes, modo de preparo e foto |
| `sugerir_bebida()` | TheCocktailDB | Bebida aleatória para acompanhar |

> Por que a busca é por **lista** de ingredientes: a TheMealDB gratuita só filtra por um ingrediente por vez. Antes, "arroz + frango" buscava só "arroz" e retornava arroz doce. Agora cada ingrediente é consultado e fica quem usa todos (ex.: *Chicken & chorizo rice pot*).

---

## Fluxo e Proteção de Tokens (3 Camadas)

1. **1ª Barreira no Front-end (`script.js` — 0 tokens)**: `ingredienteValido()` bloqueia números (`1+1`), símbolos, frases (> 4 palavras), letras sem vogal e palavras fora do tema (`PALAVRAS_BLOQUEADAS`) antes mesmo de enviar ao servidor.
2. **2ª Barreira no Back-end Python (`receita_model.py` — 0 tokens)**: `validar_formato_ingredientes()` valida os mesmos critérios no servidor e retorna `HTTP 400` imediatamente sem chamar o Gemini.
3. **3ª Barreira no System Prompt (`INSTRUCAO`)**: Se passar alguma palavra que não seja alimento, o Gemini não chama nenhuma função e devolve `{"ingredientesValidos": false}`, encerrando na 1ª chamada com `HTTP 422`.
4. **Function Calling Real**: Para ingredientes válidos, o Gemini traduz para inglês e pede `buscar_receitas_por_ingredientes` → o backend consulta a TheMealDB → o Gemini escolhe um prato e pede `ver_receita` (e `sugerir_bebida`, se marcado) → o Gemini traduz tudo em JSON e o backend injeta a foto e o ID originais da API.

---

## Como Executar

### 1. Backend
No terminal, dentro de `backend`:
```bash
pip install -r requirements.txt
python app.py
```
O servidor roda em `http://localhost:5000`. Deixe o terminal aberto.

### 2. Frontend
Abra `frontend/index.html` no navegador (duplo clique). Não precisa de Node nem de build.
