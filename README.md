# ia-chat-agent-api

Guia de execução local (PT-BR)

Este repositório contém uma API FastAPI (`/chat`) e um agente simples capaz
de usar uma ferramenta de cálculo matemático (`tools/math_tool.py`). O README
abaixo explica, passo a passo, como configurar e executar o projeto localmente,
incluindo como instalar/usar um modelo local via Ollama (ou alternativa) e
como definir as variáveis de ambiente.

Sumário
- Visão geral
- Pré-requisitos
- Passo a passo: setup e execução
  - criar venv e instalar dependências
  - configurar `.env`
  - puxar modelo Ollama (`gemma3`) — opcional
  - iniciar a API (uvicorn) e usar scripts auxiliares
- Comandos de teste (PowerShell / Python / curl)
- Troubleshooting
- Arquivos úteis e scripts

--------------------------------------------------------------------------------

Visão geral

- Endpoint principal: `POST /chat` — recebe JSON: `{ "message": "..." }`.
- O agente pode responder diretamente ou pedir execução de tool: `{ "tool": {"name":"math","input":"2+2"}}`.
- Ferramenta de cálculo: `tools/math_tool.py` — avaliador seguro baseado em AST.

Pré-requisitos

- Python 3.9+ (recomendado)
- PowerShell (Windows) ou terminal de sua preferência
- (Opcional) Ollama instalado localmente para executar modelos (https://ollama.com)

Obs: Se não quiser usar modelo local, o agente pode rodar em modo mock definindo `MOCK_AGENT=true` no `.env`.

--------------------------------------------------------------------------------

Passo a passo: setup e execução (Windows PowerShell)

1) Clonar o repositório (se ainda não tiver):

```powershell
git clone <url-do-repo>
cd ia-chat-agent-api
```

2) Criar e ativar o virtualenv

```powershell
python -m venv .venv
# ativar (PowerShell)
.\.venv\Scripts\Activate.ps1
```

3) Instalar dependências

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install python-dotenv
```

4) Criar/editar `.env` (variáveis de ambiente)

Copie o arquivo de exemplo e edite se necessário:

```powershell
Copy-Item .env.example .env -Force
# Depois edite .env no editor de sua preferência
```

Exemplo mínimo de `.env` (colocar na raiz do projeto):

```
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=gemma3
PORT=8000
MOCK_AGENT=false
STRANDS_USE_SDK=false
STRANDS_SDK_PACKAGE=strands
LOG_LEVEL=INFO
```

Explicação das variáveis principais:
- `OLLAMA_URL`: URL do serviço Ollama (padrão `http://localhost:11434`).
- `OLLAMA_MODEL`: nome do modelo local (ex.: `gemma3`).
- `MOCK_AGENT`: quando `true`, o agente usa fluxo mock (não chama LLM real).
- `STRANDS_USE_SDK`: quando `false`, evita que o adaptador Strands SDK tente usar provedores na nuvem.

5) Instalar e rodar um modelo Ollama local

Observação: a forma exata depende da versão do Ollama que você instalou.
Siga as instruções oficiais em https://ollama.com para instalar o software.

Com a CLI `ollama` disponível (exemplo genérico):

```powershell
# puxar (download) o modelo localmente (ex.: gemma3)
ollama pull gemma3

# iniciar o serviço/daemon ou expor a API HTTP (algumas versões usam 'ollama serve')
ollama serve

# ou, dependendo da versão
ollama run gemma3 --api
```

Se sua instalação do Ollama expõe a API em outra URL/porta, ajuste `OLLAMA_URL` no `.env`.

6) Iniciar a API do projeto

Você pode usar o script helper `scripts/start_local.ps1` (criado neste repositório)
ou iniciar manualmente com `uvicorn`.

Usando o script helper (ex.: cria venv, instala deps, cria .env e inicia uvicorn):

```powershell
# iniciar (usa porta 8000 por padrão, cria .venv se necessário)
.\scripts\start_local.ps1

# puxar um modelo e iniciar (requer o 'ollama' no PATH):
.\scripts\start_local.ps1 -Model gemma3 -PullModel
```

Iniciando manualmente com uvicorn:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

7) Testes rápidos (exemplos fornecidos, necessario fazer em um novo terminal, sem fechar o antigo)

- Usando Python do venv (envio JSON via `requests`):

```powershell
.\.venv\Scripts\python.exe -c "import requests; print(requests.post('http://127.0.0.1:8000/chat', json={'message':'Qual a raiz quadrada de 4?'}).text)"
```

- Usando PowerShell `Invoke-RestMethod` (atenção ao JSON; use `-Compress`):

```powershell
$payload = @{ message = 'Quanto é 5 mais 5?' } | ConvertTo-Json -Compress
$bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/chat' -Method Post -Body $bytes -ContentType 'application/json; charset=utf-8'
```

#Mensagem padrão
.\scripts\post_example.ps1

#Mensagem customizada
.\scripts\post_example.ps1 -Message 'Quanto é 5 mais 5?'

#Usar outra URL (por ex. se uvicorn estiver em outra porta)
.\scripts\post_example.ps1 -Message 'Quanto é 5 mais 5?' -Url 'http://127.0.0.1:8000/chat'

8) Teste de integração (script incluso):

```powershell
.\.venv\Scripts\python.exe tools/test_api_requests.py
```

--------------------------------------------------------------------------------

Troubleshooting (problemas comuns)

- Erro 404 do Ollama "model not found": signfica que o servidor Ollama está
  acessível, mas não há o modelo nomeado em `OLLAMA_MODEL`. Rode `ollama pull <model>`
  e verifique se o serviço está em execução.
- Erro ao parsear JSON no PowerShell: use `ConvertTo-Json -Compress` antes de enviar.
- Erro `NoCredentialsError` do Strands SDK: defina `STRANDS_USE_SDK=false` no `.env` para evitar chamadas externas.
- Variáveis no `.env` não aplicadas: reinicie o `uvicorn` depois de editar `.env`.

Observação sobre segurança: nunca versionar chaves, credenciais ou `.env` reais.
Adicione `.env` ao `.gitignore` (já incluído no repositório gerado).

--------------------------------------------------------------------------------

Arquivos e scripts úteis

- `app/main.py` — servidor FastAPI. Carrega `load_dotenv()` na inicialização.
- `agent/agent.py` — lógica do agente; verifica heurísticas de cálculo e chama LLM.
- `agent/strands_agent.py` — adaptador opcional para o Strands Agents SDK.
- `tools/math_tool.py` — avaliador seguro de expressões matemáticas (AST).
- `tools/test_api_requests.py` — script de teste rápido do endpoint `/chat`.
- `scripts/start_local.ps1` — script helper para criar venv, instalar deps, preparar `.env`, puxar modelo (opcional) e iniciar uvicorn.
