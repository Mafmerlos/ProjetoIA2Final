# Resumo de Estudo Completo — Assistente de Receitas (Projeto Final IA 2)

**Integrantes:** Matheus Figueira Merlos e João Pedro Marucci Pagluiso  
**Tecnologias:** Python + Flask (Padrão MVC) | Google Gemini (`google-genai`) + Function Calling | TheMealDB + TheCocktailDB | HTML + CSS + JavaScript Puro

---

## 1. O Projeto em 1 Frase (Para abrir a apresentação)

> *"O usuário informa os ingredientes que tem em casa no front-end, o nosso backend em Flask (organizado em MVC) envia o pedido ao Gemini, e o Gemini usa **Function Calling** para consultar APIs reais de receitas (TheMealDB) e bebidas (TheCocktailDB), devolvendo uma receita real traduzida para o português e sem risco de alucinação."*

---

## 2. Como Bloqueamos Uso de Tokens Fora do Tema (ex: `1+1`, `carro`, perguntas)

Se o professor perguntar: **"E se eu digitar `1+1` ou pedir um código em Python? Vai gastar tokens rodando o código todo?"**

A resposta é **NÃO! Criamos 3 Barreiras de Proteção em cascata:**

| Barreira | Onde fica | O que bloqueia | Gasto de Tokens |
| :--- | :--- | :--- | :--- |
| **1ª Barreira (Front-end)** | `ingredienteValido()` em [`frontend/script.js`](file:///c:/Users/Matheus/Desktop/Projeto%20Final/frontend/script.js#L126-L139) | Bloqueia números (`1+1`, `123`), símbolos matemáticos (`+`, `=`, `?`), frases com mais de 4 palavras, letras sem vogal (`bcdfg`), letras repetidas (`aaaa`) e a lista `PALAVRAS_BLOQUEADAS` (`quanto`, `calcule`, `carro`, `tijolo`, `piada`, `python`, etc.) **antes mesmo de adicionar a tag ou enviar requisição pro servidor**. | **0 tokens** (nem sai do navegador) |
| **2ª Barreira (Back-end Python)** | `_item_invalido()` e `validar_formato_ingredientes()` em [`backend/models/receita_model.py`](file:///c:/Users/Matheus/Desktop/Projeto%20Final/backend/models/receita_model.py#L77-L127) | Faz a mesma validação rigorosa no servidor Python. Se alguém chamar a API direto pelo Postman/Insomnia mandando `1+1`, `"quanto é 1 mais 1"` ou `"carro"`, o Controller devolve **HTTP 400** na hora, sem chamar `gerar_receita()`. | **0 tokens** (barra antes do Gemini) |
| **3ª Barreira (System Instruction do Gemini)** | Regra 1 da `INSTRUCAO` em [`backend/models/receita_model.py`](file:///c:/Users/Matheus/Desktop/Projeto%20Final/backend/models/receita_model.py#L26-L31) | Se passar uma palavra válida que não estava na lista bloqueada mas não é alimento (ex: `"travesseiro"` ou `"bicicleta"`), o Gemini é instruído a **NÃO chamar nenhuma função** e responder imediatamente `{"ingredientesValidos": false, "itensInvalidos": ["bicicleta"]}`. O loop para na 1ª volta e devolve **HTTP 422**. | **Mínimo possível** (interrompe na 1ª chamada, sem rodar as funções nem buscar receitas) |

---

## 3. Arquitetura MVC e Papel de Cada Arquivo

```text
Projeto Final/
├── backend/
│   ├── app.py                          # Cria o servidor Flask, ativa CORS, registra Blueprint e trata erros 404/405 em JSON
│   ├── controllers/
│   │   └── receita_controller.py       # (CONTROLLER) Rotas /api/status e /api/receitas/gerar; recebe JSON, chama validação e Model
│   ├── models/
│   │   ├── receita_model.py            # (MODEL) Configuração do Gemini, validação anti-tokens, fallback e loop de Function Calling
│   │   └── ferramentas_model.py        # (MODEL) As 3 ferramentas (funções Python) que consultam TheMealDB e TheCocktailDB
│   ├── views/
│   │   └── resposta_view.py            # (VIEW) Formata e padroniza todas as respostas JSON (sucesso, erro, status)
│   ├── requirements.txt                # Dependências: flask, flask-cors, python-dotenv, google-genai, requests
│   └── .env                            # Guarda a GEMINI_API_KEY (fica no .gitignore para não vazar no GitHub)
└── frontend/
    ├── index.html                      # Estrutura da página (abas Gerar Receita / Receitas Salvas, formulário e card)
    ├── style.css                       # Estilo visual (variáveis CSS, Flexbox, responsividade @media para celular)
    └── script.js                       # Estado da aplicação, validação no front, fetch assíncrono e localStorage
```

* **Por que usar MVC no Backend?**
  * **Controller (`receita_controller.py`)**: É a porta de entrada. Só recebe a requisição HTTP, valida os dados de entrada, chama o Model e devolve pela View.
  * **Model (`receita_model.py` e `ferramentas_model.py`)**: É o cérebro. Contém as regras de negócio, a comunicação com o Gemini e as chamadas às APIs externas.
  * **View (`resposta_view.py`)**: Em uma API REST, a View é a camada que padroniza o formato do JSON devolvido (`{"sucesso": true/false, "dados": ..., "funcoes": ...}`). O Front-end fica separado na pasta `frontend/` consumindo essa API.

---

## 4. Como Funciona o Function Calling (O Ponto Mais Importante!)

> **Atenção para pergunta de prova:** O Gemini **NÃO** acessa a internet sozinho e **NÃO** executa código Python. No Function Calling, nós damos ao Gemini um "cardápio" de funções disponíveis. Ele analisa o pedido e devolve um `function_call` dizendo: *"Quero que você execute a função X com os argumentos Y"*. O nosso código Python executa a função de verdade, pega os dados na API externa e devolve ao Gemini em um `function_response`.

### As 3 Funções expostas ao Gemini (em [`ferramentas_model.py`](file:///c:/Users/Matheus/Desktop/Projeto%20Final/backend/models/ferramentas_model.py)):
1. **`buscar_receitas_por_ingredientes(ingredientes: list[str], tipo_refeicao: str)`**:
   * O Gemini traduz os ingredientes do usuário do português para o inglês no singular (ex: `["arroz", "frango"]` → `["rice", "chicken"]`) e chama esta função.
   * Como a TheMealDB gratuita só filtra 1 ingrediente por vez (`filter.php?i=rice`), o nosso Python consulta cada ingrediente separadamente e faz a **interseção** (conta quantos ingredientes do usuário cada receita usa).
   * Também filtra pela categoria `Dessert` (se o usuário pediu Sobremesa, só deixa sobremesas; se pediu Almoço/Jantar, Café ou Lanche, **remove todas as sobremesas** — resolvendo o antigo *"bug do arroz doce"*).
2. **`ver_receita(id_receita: str)`**:
   * O Gemini escolhe 1 receita da lista retornada no passo anterior e passa o `id` dela (ex: `"53161"`).
   * A função chama `lookup.php?i=53161` na TheMealDB e junta os 20 campos `strIngredient1..20` e `strMeasure1..20`, devolvendo nome, ingredientes, modo de preparo em inglês e URL da foto.
3. **`sugerir_bebida()`**:
   * Só é chamada pelo Gemini se o usuário marcou a caixinha *"Sugerir uma bebida para acompanhar"*.
   * Consulta `random.php` na API **TheCocktailDB** e retorna um drink real com nome, se tem álcool, ingredientes, preparo e foto.

### Como o Gemini sabe que essas funções existem e quais parâmetros passar?
* Através de `tools=list(FUNCOES.values())` no `GenerateContentConfig`.
* O SDK `google-genai` lê automaticamente o **nome da função**, os **type hints** (`ingredientes: list[str]`) e a **docstring** (`""" texto """` abaixo do `def`). Por isso a docstring e a tipagem são obrigatórias.

### Por que desligamos o `automatic_function_calling` (`disable=True`)?
1. Para fazermos o **loop manual** (`for _ in range(6):` em `gerar_receita`) e podermos imprimir no terminal cada chamada (`[Function Calling] Gemini chamou: ...`) e mostrar no rodapé do card no front-end quais funções foram usadas.
2. Para filtrar no próprio servidor os IDs de receitas que o usuário já viu (botão *"Outra receita com esses ingredientes"*), sem depender da boa vontade do modelo.
3. Para verificar se `ver_receita` foi realmente chamada antes de aceitar a resposta final (impedindo alucinação).

---

## 5. Passo a Passo Completo de uma Requisição (Do Clique até a Tela)

1. **Clique no Front (`script.js`)**: O usuário digita `arroz, frango`, escolhe `Almoco/Jantar`, marca `bebida` e clica em **Criar Receita**. O JS valida com `ingredienteValido()` e envia `POST /api/receitas/gerar`.
2. **Controller (`receita_controller.py`)**: Lê o JSON, passa pela validação `validar_formato_ingredientes()` (se tiver `1+1` ou palavra proibida, já barra com erro `400` e 0 tokens) e chama `receita_model.gerar_receita()`.
3. **1ª Volta do Loop (`receita_model.py`)**: Envia o pedido ao Gemini (`gemini-3.1-flash-lite`).
4. **1º Pedido de Função**: O Gemini traduz os itens e responde pedindo `buscar_receitas_por_ingredientes(ingredientes=["rice", "chicken"], tipo_refeicao="Almoco/Jantar")`.
5. **Execução no Python (`executar_funcoes`)**: O Python consulta a TheMealDB, cruza as listas de `rice` e `chicken`, remove sobremesas, tira receitas que já estejam em `evitar` e devolve as candidatas ao Gemini via `Part.from_function_response`.
6. **2ª Volta do Loop**: O Gemini vê a lista, escolhe a receita `53161` (*Chicken & chorizo rice pot*) e pede duas funções: `ver_receita(id_receita="53161")` e `sugerir_bebida()`.
7. **Execução no Python**: O Python busca os detalhes completos da receita `53161` na TheMealDB e sorteia uma bebida na TheCocktailDB, devolvendo tudo ao Gemini.
8. **3ª Volta do Loop (Resposta Final)**: Com os dados reais em mãos, o Gemini traduz tudo para português e devolve apenas o objeto JSON final.
9. **Pós-processamento e Anti-Alucinação**: O Python extrai o JSON (`extrair_json`), confere se `ver_receita` rodou de verdade, normaliza listas/textos e injeta a **foto** e o **idReceita** originais vindos direto da API (para o modelo nunca inventar link de imagem).
10. **Exibição no Front**: O `script.js` recebe o JSON com HTTP `200`, guarda o ID em `idsVistos` e monta o cartão na tela usando `textContent`.

---

## 6. Números e Detalhes Técnicos para Decorar

* **Modelos utilizados**:
  * Principal: `gemini-3.1-flash-lite` (mais rápido e menos sujeito a fila/sobrecarga).
  * Reserva (Fallback): `gemini-3.8-flash` (acionado automaticamente no `try/except` de `chamar_gemini` se o principal falhar).
* **Tempos Limite (Timeouts)**:
  * **10 segundos** em cada chamada às APIs externas (`requests.get(..., timeout=10)`).
  * **30 segundos** por chamada ao Gemini (`http_options={"timeout": 30000}`).
  * **100 segundos** no loop total do backend (`LIMITE_SEGUNDOS = 100` → retorna HTTP `504`).
  * **150 segundos** no front-end (`AbortController` no `script.js`).
* **Limites de Entrada e Loop**:
  * Máximo de **6 voltas** no loop de Function Calling (evita loop infinito e gasto de cota).
  * Máximo de **20 ingredientes** por pedido, de **2 a 35 caracteres** e no máximo **4 palavras** por ingrediente.
* **Códigos HTTP usados no projeto**:
  * `200 OK`: Receita gerada com sucesso ou status online.
  * `400 Bad Request`: Ingrediente vazio, formato inválido, números (`1+1`), frases ou palavras fora do tema (**0 tokens gastos**).
  * `404 Not Found`: Nenhuma receita encontrada para a combinação ou rota inexistente.
  * `405 Method Not Allowed`: Tentativa de chamar `GET` em `/api/receitas/gerar`.
  * `422 Unprocessable Entity`: O Gemini detectou item não culinário que passou pelo filtro sintático.
  * `429 Too Many Requests`: Cota gratuita do Gemini atingida por minuto.
  * `500 Internal Server Error`: Chave ausente/inválida no `.env` ou falha inesperada.
  * `502 Bad Gateway`: Modelo tentou responder sem chamar `ver_receita`.
  * `503 Service Unavailable`: Servidores do Gemini sobrecarregados.
  * `504 Gateway Timeout`: Geração demorou mais de 100 segundos.

---

## 7. Perguntas Clássicas do Professor (Bate-Pronto)

1. **"E se eu mandar `1+1` ou uma pergunta fora do tema? Vai gastar tokens?"**
   * *"Não! Temos validação tanto no JavaScript do front-end quanto na função `validar_formato_ingredientes` do Python no back-end. Ela barra qualquer número, símbolo matemático, frase com mais de 4 palavras, palavras sem vogal ou termos de perguntas/objetos (`PALAVRAS_BLOQUEADAS`), devolvendo erro 400 antes mesmo de chamar o Gemini, gastando zero tokens. E se ainda passar alguma palavra válida que não seja alimento, o passo 1 da System Instruction faz o Gemini abortar na primeira resposta com erro 422 sem chamar nenhuma função."*
2. **"Quem executa as funções: o Gemini ou o seu servidor?"**
   * *"O nosso servidor Python! O Gemini apenas devolve um pedido estruturado (`function_call`) dizendo qual função quer chamar e com quais argumentos. A nossa função `executar_funcoes()` no `receita_model.py` é quem executa a função Python de verdade, acessa a API externa via `requests` e devolve o `function_response` para o Gemini."*
3. **"Como vocês garantem que o Gemini não inventou (alucinou) a receita ou a foto?"**
   * *"Primeiro, a System Instruction proíbe inventar. Segundo, no código Python (linha 258 do `receita_model.py`), nós verificamos se `resultados.get('ver_receita')` realmente existiu e retornou sucesso; se o Gemini tentar devolver uma receita sem ter consultado a API, bloqueamos com erro 502. Além disso, a URL da foto e o ID da receita são copiados diretamente do retorno da API TheMealDB pelo Python, sem passar pelo texto do Gemini."*
4. **"Por que vocês fazem uma requisição por ingrediente na TheMealDB em vez de mandar todos juntos?"**
   * *"Porque a versão gratuita da TheMealDB (`filter.php?i=`) só aceita filtrar por um ingrediente de cada vez. Então a nossa função `buscar_receitas_por_ingredientes` consulta cada ingrediente individualmente e calcula a interseção no Python, priorizando as receitas que usam todos os ingredientes informados e filtrando sobremesas."*
5. **"Como funciona o botão 'Outra receita com esses ingredientes'?"**
   * *"O front-end guarda na lista `idsVistos` os IDs das receitas já exibidas para aquela busca e envia no campo `evitar`. No backend, dentro de `executar_funcoes()`, nós removemos esses IDs da lista retornada pela TheMealDB antes mesmo de entregar ao Gemini, garantindo que ele sempre escolha um prato inédito."*
6. **"Onde ficam salvas as receitas favoritas e por que usaram `textContent` no JS?"**
   * *"As receitas salvas ficam no `localStorage` do navegador em formato JSON (`JSON.stringify` / `JSON.parse`). E usamos `textContent` em vez de `innerHTML` na função `el()` para evitar ataques de XSS (Cross-Site Scripting), garantindo que qualquer texto vindo de fora seja tratado apenas como texto puro."*
7. **"De onde vêm o Tempo de Preparo, Rendimento e Dificuldade?"**
   * *"Esses três campos são estimativas geradas pelo próprio Gemini com base nos ingredientes e nos passos da receita real, pois a API gratuita da TheMealDB não fornece tempo nem porções."*

---

## 8. Roteiro Rápido para a Demonstração ao Vivo (5 minutos)

1. **Subir o servidor**: No terminal dentro de `backend/`, rodar `python app.py` e deixar o terminal visível.
2. **Abrir o Front**: Abrir `frontend/index.html` e mostrar o aviso **"Servidor online"** em verde no topo.
3. **Demonstrar o Bloqueio de Tokens (Tema da sua pergunta)**:
   * Digitar `1+1` ou `carro` no campo de ingrediente e clicar em **Adicionar**: mostrar que é bloqueado na hora com 0 tokens gastos!
4. **Demonstrar o Function Calling com Receita Real**:
   * Digitar `arroz, frango`, escolher `Almoco/Jantar`, marcar `Sugerir uma bebida` e clicar em **Criar Receita**.
   * Mostrar no terminal as linhas `[Function Calling] Gemini chamou: buscar_receitas_por_ingredientes...`, `ver_receita...` e `sugerir_bebida...`.
   * Mostrar na tela a receita traduzida, a foto real, a bebida sugerida e o rodapé listando as funções chamadas.
5. **Demonstrar Variação e Salvar**:
   * Clicar em **"Outra receita com esses ingredientes"** para mostrar que ele traz um prato diferente sem repetir.
   * Clicar em **"Salvar"** e abrir a aba **Receitas Salvas**.

