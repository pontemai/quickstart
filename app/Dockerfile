FROM python:3.12-alpine
RUN pip install --no-cache-dir 'pontem==0.11.0'
COPY main.py /app/main.py
COPY static /app/static
WORKDIR /app
# Telemetry goes to stdout; the Pontem daemon ships container logs from there.
ENV PONTEM_EMIT_TARGET=stdout
USER 65534
EXPOSE 8080
CMD ["python", "-u", "main.py"]
