FROM python:3.12-slim

ARG TERRAFORM_VERSION=1.9.0

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl unzip git postgresql-client ansible \
 && curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -o /tmp/tf.zip \
 && curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_SHA256SUMS" -o /tmp/tf_sums \
 && grep "terraform_${TERRAFORM_VERSION}_linux_amd64.zip" /tmp/tf_sums | (cd /tmp && sed "s/terraform_${TERRAFORM_VERSION}_linux_amd64.zip/tf.zip/" | sha256sum -c -) \
 && unzip /tmp/tf.zip -d /usr/local/bin \
 && rm -f /tmp/tf.zip /tmp/tf_sums \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=appuser:appuser . .
USER appuser

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["bash", "bin/entrypoint.sh", "flask", "--app", "app:create_app", "run", "--host", "0.0.0.0", "--port", "8000"]
