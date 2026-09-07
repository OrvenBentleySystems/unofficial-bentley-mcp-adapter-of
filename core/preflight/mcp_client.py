from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from typing import Any


class McpError(RuntimeError):
    pass


class StdioMcpClient:
    def __init__(
        self,
        command: str,
        args: list[str],
        env: dict[str, str] | None = None,
        timeout: float = 30,
    ) -> None:
        self.timeout = timeout
        child_env = os.environ.copy()
        child_env.update(env or {})
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            [command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=child_env,
            creationflags=creationflags,
        )
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stderr: list[str] = []
        self._next_id = 1
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        if self.process.stdout is None:
            raise McpError("MCP server stdout pipe is unavailable")
        for line in self.process.stdout:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                self._responses.put(payload)

    def _read_stderr(self) -> None:
        if self.process.stderr is None:
            raise McpError("MCP server stderr pipe is unavailable")
        for line in self.process.stderr:
            self._stderr.append(line.rstrip())
            if len(self._stderr) > 100:
                del self._stderr[:50]

    def _send(self, payload: dict[str, Any]) -> None:
        if self.process.poll() is not None:
            detail = "\n".join(self._stderr[-10:])
            raise McpError(f"MCP server exited with {self.process.returncode}: {detail}")
        if self.process.stdin is None:
            raise McpError("MCP server stdin pipe is unavailable")
        self.process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self.process.stdin.flush()

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        deadline = time.monotonic() + self.timeout
        deferred: list[dict[str, Any]] = []
        try:
            while time.monotonic() < deadline:
                try:
                    remaining = max(0.0, deadline - time.monotonic())
                    response = self._responses.get(timeout=min(0.25, remaining))
                except queue.Empty:
                    if self.process.poll() is not None:
                        detail = "\n".join(self._stderr[-10:])
                        raise McpError(
                            f"MCP server exited with {self.process.returncode}: {detail}"
                        )
                    continue
                if response.get("id") == request_id:
                    if "error" in response:
                        raise McpError(f"{method} failed: {response['error']}")
                    return response.get("result") or {}
                deferred.append(response)
        finally:
            for response in deferred:
                self._responses.put(response)
        raise McpError(f"Timed out after {self.timeout:g}s waiting for {method}")

    def initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "bentley-adapter-preflight", "version": "0.1.0"},
            },
        )
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def list_tools(self) -> set[str]:
        result = self._request("tools/list", {})
        return {
            str(tool["name"])
            for tool in result.get("tools", [])
            if isinstance(tool, dict) and tool.get("name")
        }

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        result = self._request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        if result.get("isError"):
            texts = [
                item.get("text", "")
                for item in result.get("content", [])
                if isinstance(item, dict)
            ]
            raise McpError(f"{name} returned an error: {' '.join(texts)}")
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return structured
        for item in result.get("content", []):
            if not isinstance(item, dict) or not isinstance(item.get("text"), str):
                continue
            try:
                parsed = json.loads(item["text"])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return {"content": result.get("content", [])}

    def close(self) -> None:
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=3)

    def __enter__(self) -> "StdioMcpClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
