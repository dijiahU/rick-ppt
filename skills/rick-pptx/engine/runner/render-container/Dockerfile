FROM ubuntu:22.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libreoffice-impress fonts-noto-cjk fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
USER 1000:1000
WORKDIR /work
ENTRYPOINT ["/usr/bin/libreoffice"]
