FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    tree-sitter==0.25.2 \
    tree-sitter-python==0.25.0

COPY parse.py /app/parse.py
COPY hello_world_example.py /app/hello_world_example.py

CMD ["python", "parse.py", "hello_world_example.py"]