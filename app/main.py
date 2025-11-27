"""FastAPI app exposing a simple `/chat` endpoint powered by the Agent.

Usage (after installing requirements):
  $ set OLLAMA_URL=http://localhost:11434
  $ set OLLAMA_MODEL=mistral
  $ uvicorn app.main:app --reload

POST /chat
  JSON body: {"input": "Pergunte algo que pode precisar de cálculo, por exemplo: 'Qual é 12 * 7 + 3?'"}
"""
from fastapi import FastAPI, HTTPException, Response
import os
import json
from dotenv import load_dotenv

from agent.strands_agent import StrandsAgent
from pydantic import BaseModel

app = FastAPI(title="IA Chat Agent API")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@app.on_event("startup")
async def startup_event():
    # Load .env (if present) so env vars are available to the agent
    load_dotenv()

    # create a StrandsAgent (will fallback if SDK missing)
    app.state.agent = StrandsAgent()

    # If MOCK_AGENT is set, monkeypatch the agent to simulate LLM responses
    mock_flag = os.getenv("MOCK_AGENT", "false").lower()
    if mock_flag in ("1", "true", "yes"):
        async def _fake_call(messages):
            # If messages already contain a tool_result, return final response
            for m in messages:
                if m.get("role") == "assistant":
                    content = m.get("content", "")
                    try:
                        parsed = json.loads(content)
                    except Exception:
                        parsed = None
                    if isinstance(parsed, dict) and "tool_result" in parsed:
                        tr = parsed["tool_result"]
                        if isinstance(tr, dict) and tr.get("ok"):
                            res = tr.get("result")
                        else:
                            res = tr
                        return json.dumps({"response": f"(mock) resultado do cálculo: {res}"})
            # otherwise request the math tool for a sample expression
            return json.dumps({"tool": {"name": "math", "input": "12*(3+4)"}})

        # If the agent has an _call_llm attribute (fallback SimpleAgent), patch it
        if hasattr(app.state.agent, "_fallback") and hasattr(app.state.agent._fallback, "_call_llm"):
            app.state.agent._fallback._call_llm = _fake_call
        else:
            # attempt best-effort patch
            if hasattr(app.state.agent, "_call_llm"):
                app.state.agent._call_llm = _fake_call


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    agent = app.state.agent
    # The StrandsAgent.run and fallback Agent.run expect a message string.
    result = await agent.run(req.message)
    if not result.get("ok"):
        # normalize error
        raise HTTPException(status_code=500, detail=result.get("error") or "agent error")
    return {"response": result.get("response")}


@app.get("/", tags=["health"])
async def root():
    """Root endpoint to confirm the service is running."""
    return {"status": "ok", "docs": "http://127.0.0.1:8000/docs", "chat": "/chat"}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # Return empty response for favicon requests (avoids 404 in browser)
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", 8000)), reload=False)
