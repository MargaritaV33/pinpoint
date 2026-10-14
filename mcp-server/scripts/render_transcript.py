"""Mechanically render `claude -p ... --output-format stream-json --verbose`
output as a readable transcript. Reads stdin, writes stdout (UTF-8).

It only lays events out; it never rewrites, summarises or reorders text. It
drops event kinds that carry no conversation: the `system` init event (a list
of every MCP server on the machine), `rate_limit_event`, empty `thinking`
blocks (encrypted signature only), and the final `result` event's cost data.
The only edit it can make is replacing a configured secret with `[redacted]`:
pass secrets as arguments, e.g. `render_transcript.py "$PINPOINT_PASSWORD"`.

    claude -p "<prompt>" ... --output-format stream-json --verbose \
        | python mcp-server/scripts/render_transcript.py "<prompt>"
"""

import json
import sys


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    prompt, *secrets = sys.argv[1:] or [""]

    def clean(text: str) -> str:
        for secret in filter(None, secrets):
            text = text.replace(secret, "[redacted]")
        return text

    print(f"PROMPT: {prompt}\n")
    for line in sys.stdin:
        if not line.strip():
            continue
        event = json.loads(line)
        kind = event.get("type")
        if kind not in ("assistant", "user"):
            continue
        for block in event["message"]["content"]:
            if isinstance(block, str):
                print(clean(block) + "\n")
            elif block["type"] == "text":
                print("ASSISTANT:\n" + clean(block["text"]) + "\n")
            elif block["type"] == "tool_use":
                args = json.dumps(block["input"], ensure_ascii=False)
                print(f"TOOL CALL: {block['name']} {clean(args)}\n")
            elif block["type"] == "tool_result":
                content = block["content"]
                if isinstance(content, list):
                    parts = [
                        c["text"] if c["type"] == "text" else json.dumps(c, ensure_ascii=False)
                        for c in content
                    ]
                    content = "\n".join(parts)
                print("TOOL RESULT:\n" + clean(content) + "\n")


if __name__ == "__main__":
    main()
