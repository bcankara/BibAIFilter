# BibAIFilter 2 — container image (interface + API on port 8765).
# The web interface is pre-built in src/bibaifilter/_web, so Node.js is not needed here.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    BIBAIFILTER_HOME=/data BIBAIFILTER_CONFIG_DIR=/data/.config
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .
VOLUME ["/data"]
EXPOSE 8765
# Inside a container the server must listen on all interfaces; publish the port to
# 127.0.0.1 only (see docker-compose.yml) so that it is not reachable from the network.
CMD ["bibaifilter", "serve", "--host", "0.0.0.0", "--port", "8765", "--no-browser"]
