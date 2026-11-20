# La imagen del respaldo: Python + age. Se arma y se usa y se tira (no corre como servicio).
#   docker build -f herramientas/respaldo/respaldo.Dockerfile -t enenos-respaldo herramientas/respaldo
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends age && rm -rf /var/lib/apt/lists/*
COPY respaldo.py /app/respaldo.py
WORKDIR /app
ENTRYPOINT ["python", "/app/respaldo.py"]
