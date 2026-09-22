"""Generate reproducible PNG evidence for the README from real demo responses."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
sys.path.insert(0, str(ROOT))

from stateless_mcp import PROTOCOL_VERSION, RequestStateCodec, handle_rpc  # noqa: E402


def render_terminal(title: str, lines: list[str], destination: Path) -> None:
    """Render text as a readable terminal-style PNG."""
    font_paths = [
        Path("C:/Windows/Fonts/CascadiaMono.ttf"),
        Path("C:/Windows/Fonts/consola.ttf"),
    ]
    font_path = next(path for path in font_paths if path.exists())
    font = ImageFont.truetype(str(font_path), 22)
    title_font = ImageFont.truetype(str(font_path), 21)
    line_height = 31
    width = 1500
    height = 92 + line_height * len(lines) + 35
    image = Image.new("RGB", (width, height), "#0d1117")
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((12, 12, width - 12, height - 12), radius=18,
                           fill="#0d1117", outline="#30363d", width=2)
    draw.rounded_rectangle((13, 13, width - 13, 66), radius=17, fill="#161b22")
    draw.rectangle((13, 48, width - 13, 66), fill="#161b22")
    for x, color in ((38, "#ff5f56"), (66, "#ffbd2e"), (94, "#27c93f")):
        draw.ellipse((x - 8, 31 - 8, x + 8, 31 + 8), fill=color)
    draw.text((125, 20), title, font=title_font, fill="#c9d1d9")

    y = 82
    for line in lines:
        color = "#7ee787" if line.startswith(("PASS", "OK", "HTTP")) else "#c9d1d9"
        if '"resultType": "input_required"' in line:
            color = "#d2a8ff"
        if '"resultType": "complete"' in line:
            color = "#79c0ff"
        draw.text((34, y), line, font=font, fill=color)
        y += line_height

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, optimize=True)


def rpc_evidence() -> tuple[dict, dict]:
    codec = RequestStateCodec(b"readme-screenshot-secret")
    headers = {
        "mcp-protocol-version": PROTOCOL_VERSION,
        "mcp-method": "tools/call",
        "mcp-name": "confirm_operation",
    }
    meta = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientCapabilities": {"elicitation": {"form": {}}},
    }
    base_params = {
        "name": "confirm_operation",
        "arguments": {"operation": "generate the Task 1 completion report"},
        "_meta": meta,
    }
    first_request = {
        "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": base_params,
    }
    first_status, first = handle_rpc(first_request, headers, codec)
    assert first_status == 200

    retry_params = dict(base_params)
    retry_params["requestState"] = first["result"]["requestState"]
    retry_params["inputResponses"] = {
        "confirm": {"action": "accept", "content": {"confirmed": True}}
    }
    second_request = {
        "jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": retry_params,
    }
    second_status, second = handle_rpc(second_request, headers, codec)
    assert second_status == 200

    # Tokens are intentionally opaque. Shorten it only in the screenshot.
    first_for_display = json.loads(json.dumps(first))
    first_for_display["result"]["requestState"] = "<signed, opaque requestState>"
    return first_for_display, second


def main() -> None:
    first, second = rpc_evidence()
    render_terminal(
        "Round 1 — input required",
        ["HTTP 200", *json.dumps(first, indent=2).splitlines()],
        ASSETS / "round-1-input-required.png",
    )
    render_terminal(
        "Round 2 — complete",
        ["HTTP 200", *json.dumps(second, indent=2).splitlines()],
        ASSETS / "round-2-complete.png",
    )

    test = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    output = (test.stdout + test.stderr).replace("\r", "")
    lines = []
    for line in output.splitlines():
        if not line.strip() or set(line.strip()) == {"-"}:
            continue
        if line.endswith(" ... ok"):
            lines.append(f"PASS  {line.split(' (', 1)[0]}")
        else:
            lines.append(line)
    render_terminal("Automated verification", lines, ASSETS / "tests-passing.png")


if __name__ == "__main__":
    main()
