# Single-stage Rust build — no Node.js, no npm, no JavaScript framework.
# Frontend is server-rendered HTML + HTMX, compiled into the binary via askama.

FROM rust:1.77-alpine AS builder
RUN apk add --no-cache musl-dev
WORKDIR /build
COPY rust/ ./
RUN cargo build --release

FROM alpine:3.19
RUN addgroup -g 1001 -S app && adduser -S app -u 1001 -G app
COPY --from=builder /build/target/release/datasheetminer /usr/local/bin/
ENV PORT=3001
EXPOSE 3001
USER app
ENTRYPOINT ["datasheetminer"]
CMD ["serve", "--port", "3001"]
