# Build context is the repo root (see docker-compose.yml, if/when wired
# there), not this folder -- needed so this image can COPY the app/ subtree
# its tools reuse for tenant config reading.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /repo

COPY mcp_servers/requirements.txt mcp_servers/requirements.txt
RUN pip install --no-cache-dir -r mcp_servers/requirements.txt

COPY app/ app/
COPY mcp_servers/clinyq_mcp.py mcp_servers/clinyq_mcp.py
COPY mcp_servers/main.py mcp_servers/main.py
COPY mcp_servers/fastmcp.json mcp_servers/fastmcp.json
COPY mcp_servers/agb/ mcp_servers/agb/
COPY mcp_servers/azure_translator/ mcp_servers/azure_translator/

WORKDIR /repo/mcp_servers

EXPOSE 8931

CMD ["fastmcp", "run", "fastmcp.json", "--stateless"]
