"""Simple agent that uses an LLM (Ollama) and a small toolset.

Design:
- The agent asks the LLM to either return a direct `response` string or a
  structured tool call in JSON form: {"tool": {"name":"math", "input":"2+2"}}
- If a tool call is returned, the agent executes the tool and feeds the
  result back to the LLM to obtain a final response.

This is a lightweight orchestration compatible with adding the Strands
Agents SDK later; the code tries to keep the agent boundary explicit.
"""
from typing import List, Dict, Any, Optional
import os
import json
import logging
import httpx

from tools.math_tool import evaluate_expression

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, ollama_url: Optional[str] = None, model: Optional[str] = None):
        self.ollama_url = ollama_url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.model = model or os.environ.get("OLLAMA_MODEL", "mistral")

    async def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """Call Ollama (or compatible) HTTP chat endpoint.

        The implementation assumes an OpenAI-like `/v1/chat/completions` API
        which some local deployments (or proxies) provide. If your Ollama
        exposes a different API, adjust this function accordingly.
        """
        # Try multiple common endpoints/payloads so this works with
        # OpenAI-like proxies and Ollama-native HTTP APIs.
        endpoints = [
            (f"{self.ollama_url}/v1/chat/completions", "openai_chat"),
            (f"{self.ollama_url}/v1/completions", "openai_comp"),
            (f"{self.ollama_url}/chat", "ollama_chat"),
            (f"{self.ollama_url}/api/generate", "ollama_generate"),
        ]

        last_exc: Optional[Exception] = None
        async with httpx.AsyncClient(timeout=30) as client:
            for url, kind in endpoints:
                try:
                    if kind == "openai_chat":
                        payload = {"model": self.model, "messages": messages, "max_tokens": 512}
                        r = await client.post(url, json=payload)
                    elif kind == "openai_comp":
                        # some proxies expect a single prompt string
                        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
                        payload = {"model": self.model, "prompt": prompt, "max_tokens": 512}
                        r = await client.post(url, json=payload)
                    elif kind == "ollama_chat":
                        # try a simple chat-like payload
                        payload = {"model": self.model, "messages": messages}
                        r = await client.post(url, json=payload)
                    else:  # ollama_generate
                        # Ollama native `/api/generate` often expects `model` and `prompt`
                        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
                        payload = {"model": self.model, "prompt": prompt}
                        r = await client.post(url, json=payload)

                    # If non-success, try next endpoint
                    if r.status_code >= 400:
                        last_exc = RuntimeError(f"{r.status_code} from {url}: {r.text}")
                        continue

                    data = r.json()

                    # OpenAI-like response
                    if isinstance(data, dict) and "choices" in data and len(data["choices"]) > 0:
                        choice = data["choices"][0]
                        # chat format
                        if "message" in choice and "content" in choice["message"]:
                            return choice["message"]["content"]
                        # completion-like
                        if "text" in choice:
                            return choice["text"]

                    # Ollama-style: look for common keys
                    if isinstance(data, dict):
                        if "text" in data and isinstance(data["text"], str):
                            return data["text"]
                        if "output" in data:
                            return data["output"]
                        # some Ollama responses embed results in `result` or `choices`
                        if "result" in data:
                            return json.dumps(data["result"])

                    # fallback: if response body is simple string
                    if isinstance(data, str):
                        return data

                    # otherwise return the full JSON as string
                    return json.dumps(data)

                except Exception as e:
                    last_exc = e
                    continue

        # If none of the endpoints worked, raise the last exception
        raise last_exc or RuntimeError("No viable LLM endpoint responded")

    async def run(self, user_input: str, max_steps: int = 3) -> Dict[str, Any]:
        """Process user input: interact with LLM and tools until a final response.

        Returns a dict: {"ok": True, "response": "text"} or {"ok": False, "error": "msg"}
        """
        system_prompt = (
            "You are an assistant that can either answer directly or request to run "
            "a tool. When requesting a tool, reply ONLY with a JSON object exactly in one of the formats:\n"
            "1) {\"response\": \"...\"}  OR\n"
            "2) {\"tool\": {\"name\": \"math\", \"input\": \"2+2\"}}\n"
            "Do not add any other text. The math tool evaluates arithmetic expressions "
            "and Python `math` functions (e.g., sin, cos)."
        )

        # Quick heuristic: if the user input appears to be a direct math request,
        # evaluate it locally with the math tool instead of relying on the LLM.
        if self._looks_like_math(user_input):
            tool_result = evaluate_expression(self._extract_expression(user_input))
            if tool_result.get("ok"):
                return {"ok": True, "response": str(tool_result.get("result"))}
            else:
                return {"ok": False, "error": tool_result.get("error")}

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]

        for step in range(max_steps):
            try:
                llm_out = await self._call_llm(messages)
            except Exception as e:
                logger.exception("LLM call failed")
                return {"ok": False, "error": f"LLM call failed: {e}"}

            # attempt to parse JSON from model output
            try:
                parsed = json.loads(llm_out.strip())
            except Exception:
                # Not valid JSON — treat as direct response
                return {"ok": True, "response": llm_out.strip()}

            if isinstance(parsed, dict) and "response" in parsed:
                return {"ok": True, "response": parsed["response"]}

            if isinstance(parsed, dict) and "tool" in parsed:
                tool_call = parsed["tool"]
                name = tool_call.get("name")
                inp = tool_call.get("input")
                if name == "math":
                    tool_result = evaluate_expression(inp)
                    # feed tool result back to the model
                    tool_msg = {"role": "assistant", "content": json.dumps({"tool_result": tool_result})}
                    messages.append({"role": "assistant", "content": json.dumps(parsed)})
                    messages.append(tool_msg)
                    # next loop will ask LLM to finalize answer
                    continue
                else:
                    return {"ok": False, "error": f"Unknown tool: {name}"}

            # fallback: if parsing produced something else, return it as JSON string
            return {"ok": True, "response": json.dumps(parsed)}

    def _looks_like_math(self, text: str) -> bool:
        """Heuristic to detect if the user asked for a math computation."""
        import re
        t = text.lower()
        # common Portuguese triggers and presence of digits/operators
        if any(k in t for k in ("quanto é", "quanto", "calcule", "calcular", "raiz quadrada", "sqrt")):
            return True
        # simple expression detection: digits with operators or Portuguese words
        if re.search(r"\d+\s*[\+\-\*\/\%\^]", text):
            return True
        # detection for Portuguese operator words (e.g., '5 mais 5', '5 vezes 5')
        if re.search(r"\d+\s*(mais|menos|vezes|dividido|por|x)\s*\d+", t):
            return True
        return False

    def _extract_expression(self, text: str) -> str:
        """Try to extract a math expression from the user's text.

        Very small heuristic: return digits/operators substring, otherwise return original text.
        """
        import re
        # normalize and work with lowercase for pattern matching
        t = text.replace(',', '')
        t = t.replace('\u00A0', ' ')
        tl = t.lower()

        # Handle Portuguese phrase "raiz quadrada de X" -> sqrt(X)
        m = re.search(r"raiz\s+quadrada\s+de\s*([0-9A-Za-z_\.\(\)\+\-\*\/\%\^\s]+)", tl)
        if m:
            inner = m.group(1).strip()
            inner = inner.replace('^', '**')
            return f"sqrt({inner})"

        # Handle shorter form "raiz de X" -> sqrt(X)
        m2 = re.search(r"raiz\s+de\s*([0-9A-Za-z_\.\(\)\+\-\*\/\%\^\s]+)", tl)
        if m2:
            inner = m2.group(1).strip()
            inner = inner.replace('^', '**')
            return f"sqrt({inner})"

        # Translate Portuguese operator words into symbols before tokenizing
        # e.g. '5 mais 5' -> '5 + 5', '10 dividido por 2' -> '10 / 2'
        replacements = [
            (r"\bmais\b", "+"),
            (r"\bmenos\b", "-"),
            (r"\bvezes\b", "*"),
            (r"\bx\b", "*"),
            (r"\bdividido\s+por\b", "/"),
            (r"\bdividido\b", "/"),
            # 'por' is ambiguous but commonly used as division in 'dividido por'
        ]
        for pat, sub in replacements:
            tl = re.sub(pat, sub, tl)
            t = re.sub(pat, sub, t)

        # extract allowed tokens (digits, operators, parentheses, dots and func names)
        parts = re.findall(r"[0-9A-Za-z_\.\(\)\+\-\*\/\%\^]+", t)
        if parts:
            allowed_funcs = {
                'sin', 'cos', 'tan', 'sqrt', 'log', 'exp', 'abs', 'floor', 'ceil', 'pow'
            }
            filtered = []
            for p in parts:
                pl = p.lower()
                if re.search(r"\d", p):
                    filtered.append(p)
                    continue
                if pl in allowed_funcs:
                    filtered.append(pl)
                    continue
                if re.fullmatch(r"[\+\-\*\/\%\^]+", p):
                    filtered.append(p)
                    continue
                if re.fullmatch(r"[\(\)]+", p):
                    filtered.append(p)
                    continue
            if filtered:
                expr = " ".join(filtered)
                expr = expr.replace('^', '**')
                expr = expr.strip()
                return expr
        return text
