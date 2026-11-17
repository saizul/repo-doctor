FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install . && useradd --system --uid 10001 app && rm -rf /app/build
USER app
WORKDIR /repo
ENTRYPOINT ["repo-doctor"]
CMD ["check", "."]
