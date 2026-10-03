# Usa a versão oficial do Python 3.14 (a mesma que você usa no Windows)
FROM python:3.14-slim

# Define que o sistema não vai gerar ficheiros .pyc e envia os logs direto para o terminal
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Cria e define a pasta de trabalho dentro do "contentor"
WORKDIR /app

# Instala as dependências do sistema operacional necessárias
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copia o ficheiro de requisitos e instala as bibliotecas do Python
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Instala o Gunicorn (O Servidor Profissional para rodar o Django)
RUN pip install gunicorn

# Copia o resto do código do nosso sistema para dentro da "caixa"
COPY . /app/

# Expõe a porta 8000 para podermos aceder
EXPOSE 8000

# O comando que o Docker vai executar quando ligar a "caixa"
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]