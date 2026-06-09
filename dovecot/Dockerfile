FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        dovecot-core \
        dovecot-imapd \
        dovecot-auth-oauth2 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Create mail storage directory and vmail user
RUN groupadd -g 5000 vmail && \
    useradd -u 5000 -g vmail -d /var/mail/vhosts vmail && \
    mkdir -p /var/mail/vhosts && \
    chown -R vmail:vmail /var/mail/vhosts

EXPOSE 143

CMD ["dovecot", "-F"]
