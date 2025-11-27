"""Helper to run the Agent locally without Ollama by mocking LLM responses.

This script monkeypatches `Agent._call_llm` to simulate a two-step
interaction: the model first requests the `math` tool, and after the tool
result is provided, the model returns a final response. Use this to verify
the tool orchestration and `tools/math_tool` behavior without an LLM.
"""
import asyncio
import json
from agent.agent import Agent


async def main():
    agent = Agent()

    async def fake_call(messages):
        # If the messages already contain a tool_result, return a final response
        for m in messages:
            if m.get("role") == "assistant":
                content = m.get("content", "")
                try:
                    parsed = json.loads(content)
                except Exception:
                    parsed = None
                if isinstance(parsed, dict) and "tool_result" in parsed:
                    tr = parsed["tool_result"]
                    # try to extract result field or render the structure
                    if isinstance(tr, dict) and tr.get("ok"):
                        res = tr.get("result")
                    else:
                        # fallback: stringify
                        res = tr
                    return json.dumps({"response": f"Mock LLM: o resultado do cálculo é {res}"})

        # Otherwise, simulate a model requesting the math tool
        return json.dumps({"tool": {"name": "math", "input": "12*(3+4)"}})

    # monkeypatch agent's LLM call
    agent._call_llm = fake_call

    print("Executando teste local do agente (mock LLM) ...")
    result = await agent.run("Por favor calcule 12*(3+4).")
    print("Resultado do agente:", result)


if __name__ == "__main__":
    asyncio.run(main())
