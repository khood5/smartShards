FROM ubuntu:bionic

#update and install util packages 
RUN apt-get update && apt-get install gnupg -y
RUN apt-get update
RUN apt-get install -y -q --allow-downgrades \
    apt-transport-https \
    build-essential \
    curl \
    libssl-dev \
    gcc \
    git \
    pkg-config \
    python3 \
    software-properties-common \
    unzip \
    systemd

# install ptotoc compiler and rust
RUN curl -OLsS https://github.com/google/protobuf/releases/download/v3.5.1/protoc-3.5.1-linux-x86_64.zip \
 && unzip protoc-3.5.1-linux-x86_64.zip -d protoc3 \
 && rm protoc-3.5.1-linux-x86_64.zip

RUN curl https://sh.rustup.rs -sSf > /usr/bin/rustup-init \
 && chmod +x /usr/bin/rustup-init \
 && rustup-init -y

# set PATH and IP var
ENV PATH=$PATH:/protoc3/bin:/project/sawtooth-core/bin:/root/.cargo/bin CARGO_INCREMENTAL=0

# install sawtooth and sawtooth-pbft
RUN apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 8AA7AF1F1091A5FD \
&& add-apt-repository 'deb [arch=amd64] http://repo.sawtooth.me/ubuntu/chime/stable bionic universe'

RUN apt-get update
RUN apt install -y sawtooth 
RUN apt install -y sawtooth sawtooth-pbft-engine

# Keeps container running.
#   If this command it not here then the container will exit immediately, the next step to create
#   keys in the container and start PBFT
CMD tail -f /dev/null