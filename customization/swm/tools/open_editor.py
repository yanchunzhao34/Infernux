"""Open the prepared SWM demo project in the installed Infernux Editor."""
import argparse
import os
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("project", type=Path)
parser.add_argument("--mcp-port", type=int, help="独立演示项目的本机 MCP 端口，避免与其他编辑器冲突")
args = parser.parse_args()
if args.mcp_port is not None:
    if not 1024 <= args.mcp_port <= 65535:
        parser.error("MCP 端口需要在 1024–65535 范围内")
    os.environ["INFERNUX_MCP_PORT"] = str(args.mcp_port)

import infernux
infernux.release_engine(str(args.project.resolve()))
