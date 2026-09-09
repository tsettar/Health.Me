FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY apps /usr/share/nginx/html/apps
COPY data /usr/share/nginx/html/data

EXPOSE 8080

# Loopback-only listener (see nginx.conf) means this only ever answers from
# inside the container's own network namespace, so the healthcheck is the
# simplest possible smoke test of "is nginx still serving".
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1
