FROM eclipse-temurin:17.0.16_8-jre-jammy
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-psutil python3-aiohttp curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ARG JMETER_SHA512=5978a1a35edb5a7d428e270564ff49d2b1b257a65e17a759d259a9283fc17093e522fe46f474a043864aea6910683486340706d745fcdf3db1505fd71e689083
RUN curl --fail --location --retry 3 https://archive.apache.org/dist/jmeter/binaries/apache-jmeter-5.6.3.tgz -o /tmp/jmeter.tgz \
    && printf '%s  %s\n' "$JMETER_SHA512" /tmp/jmeter.tgz | sha512sum --check - \
    && tar -xzf /tmp/jmeter.tgz -C /opt \
    && rm /tmp/jmeter.tgz
RUN mkdir -p /opt/consul \
    && curl --fail --location --retry 3 https://releases.hashicorp.com/consul/1.20.6/consul_1.20.6_linux_amd64.zip -o /tmp/consul_1.20.6_linux_amd64.zip \
    && curl --fail --location --retry 3 https://releases.hashicorp.com/consul/1.20.6/consul_1.20.6_SHA256SUMS -o /tmp/consul_SHA256SUMS \
    && cd /tmp && grep 'consul_1.20.6_linux_amd64.zip$' consul_SHA256SUMS | sha256sum --check - \
    && unzip consul_1.20.6_linux_amd64.zip -d /opt/consul \
    && rm consul_1.20.6_linux_amd64.zip consul_SHA256SUMS
ENV JMETER_HOME=/opt/apache-jmeter-5.6.3
WORKDIR /work
