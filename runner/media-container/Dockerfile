FROM ubuntu:22.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 python3-pil python3-cairosvg libavif-bin ffmpeg && rm -rf /var/lib/apt/lists/*
COPY normalize.py /opt/normalize.py
USER 1000:1000
WORKDIR /work
ENTRYPOINT ["python3", "/opt/normalize.py"]
