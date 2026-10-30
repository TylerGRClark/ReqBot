# Optional reranker service (see docker-compose.example.yml, profile "rerank").
# Default build is CPU-only torch (small); a GPU host builds with --build-arg TORCH_INDEX=https://download.pytorch.org/whl/cu124
FROM python:3.12-slim
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir torch --index-url ${TORCH_INDEX} \
    && pip install --no-cache-dir transformers
WORKDIR /app
COPY server.py .
ENV HF_HOME=/models
EXPOSE 8732
CMD ["python", "server.py"]
