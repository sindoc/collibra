/*
 * accept_tcp.c — Singine smtpAgent trusted TCP acceptor
 *
 * Lifecycle:
 *   1. Bind to loopback (127.0.0.1:8025 by default).
 *   2. Accept() loop — each connection is handled in a forked child.
 *   3. Origin check — non-trusted IPs are closed immediately, logged.
 *   4. Relay — raw request bytes are forwarded to the Clojure SMTP
 *      service endpoint via a pipe to curl (avoids linking libcurl).
 *   5. Response — Clojure's JSON response is written back to the client.
 *
 * Build: make -C c/
 * Usage: ./c/bin/accept_tcp [bind_addr] [port]
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <signal.h>
#include <time.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#include "../include/tcp_server.h"

/* ── Logging ─────────────────────────────────────────────────────────────── */

static FILE *g_log = NULL;

static void log_init(void) {
    g_log = fopen(LOG_PATH, "a");
    if (!g_log) g_log = stderr;
}

void log_connection(const conn_ctx_t *ctx, const char *event) {
    char ipstr[INET_ADDRSTRLEN];
    struct in_addr addr = { .s_addr = ctx->client_ip };
    inet_ntop(AF_INET, &addr, ipstr, sizeof(ipstr));

    time_t now = time(NULL);
    char ts[32];
    strftime(ts, sizeof(ts), "%Y-%m-%dT%H:%M:%SZ", gmtime(&now));

    FILE *out = g_log ? g_log : stderr;
    fprintf(out,
        "{\"timestamp\":\"%s\",\"event\":\"%s\","
        "\"client\":\"%s\",\"port\":%u,\"fd\":%d}\n",
        ts, event, ipstr, ctx->client_port, ctx->client_fd);
    fflush(out);
}

/* ── Origin trust check ──────────────────────────────────────────────────── */

int is_trusted_origin(uint32_t ip_nbo) {
    struct in_addr trusted;
    inet_pton(AF_INET, TRUSTED_ORIGIN, &trusted);
    return (ip_nbo == trusted.s_addr);
}

/* ── Relay to Clojure SMTP service ───────────────────────────────────────── */

static void relay_to_smtp_service(int client_fd) {
    char buf[RELAY_BUF_SIZE];
    ssize_t n = recv(client_fd, buf, sizeof(buf) - 1, 0);
    if (n <= 0) return;
    buf[n] = '\0';

    /* Pipe buf → curl → Clojure HTTP endpoint → write response back */
    int pipe_in[2], pipe_out[2];
    if (pipe(pipe_in) < 0 || pipe(pipe_out) < 0) return;

    pid_t pid = fork();
    if (pid == 0) {
        /* child: curl */
        dup2(pipe_in[0],  STDIN_FILENO);
        dup2(pipe_out[1], STDOUT_FILENO);
        close(pipe_in[1]);
        close(pipe_out[0]);
        execlp("curl", "curl",
               "-s", "-X", "POST",
               "-H", "Content-Type: application/json",
               "--data-binary", "@-",
               SMTP_SERVICE_URL,
               (char *)NULL);
        _exit(1);
    }

    /* parent: write request, read response */
    close(pipe_in[0]);
    close(pipe_out[1]);

    ssize_t written = write(pipe_in[1], buf, (size_t)n);
    (void)written; /* relay best-effort; curl reads what arrived */
    close(pipe_in[1]);

    char resp[RELAY_BUF_SIZE];
    ssize_t rn = read(pipe_out[0], resp, sizeof(resp) - 1);
    close(pipe_out[0]);
    waitpid(pid, NULL, 0);

    if (rn > 0) {
        resp[rn] = '\0';
        send(client_fd, resp, (size_t)rn, 0);
    }
}

/* ── Connection handler (runs in forked child) ───────────────────────────── */

static void handle_connection(conn_ctx_t ctx) {
    log_connection(&ctx, "accepted");

    if (!is_trusted_origin(ctx.client_ip)) {
        log_connection(&ctx, "rejected-untrusted-origin");
        close(ctx.client_fd);
        return;
    }

    log_connection(&ctx, "trusted-relay-start");
    relay_to_smtp_service(ctx.client_fd);
    log_connection(&ctx, "relay-complete");
    close(ctx.client_fd);
}

/* ── Server init ─────────────────────────────────────────────────────────── */

tcp_result_t tcp_server_init(const char *bind_addr, uint16_t port) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) { perror("socket"); return TCP_ERR_SOCKET; }

    int opt = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in sa = {
        .sin_family      = AF_INET,
        .sin_port        = htons(port),
    };
    inet_pton(AF_INET, bind_addr, &sa.sin_addr);

    if (bind(fd, (struct sockaddr *)&sa, sizeof(sa)) < 0) {
        perror("bind"); close(fd); return TCP_ERR_BIND;
    }
    if (listen(fd, TCP_BACKLOG) < 0) {
        perror("listen"); close(fd); return TCP_ERR_LISTEN;
    }

    fprintf(stdout,
        "{\"event\":\"listening\",\"bind\":\"%s\",\"port\":%u,"
        "\"trusted_origin\":\"%s\"}\n",
        bind_addr, port, TRUSTED_ORIGIN);
    fflush(stdout);
    return (tcp_result_t)fd;
}

/* ── Accept loop ─────────────────────────────────────────────────────────── */

tcp_result_t tcp_server_accept_loop(int server_fd) {
    signal(SIGCHLD, SIG_IGN);   /* auto-reap children */

    for (;;) {
        struct sockaddr_in client_sa;
        socklen_t sa_len = sizeof(client_sa);

        int cfd = accept(server_fd, (struct sockaddr *)&client_sa, &sa_len);
        if (cfd < 0) {
            if (errno == EINTR) continue;
            perror("accept");
            return TCP_ERR_ACCEPT;
        }

        conn_ctx_t ctx = {
            .client_fd   = cfd,
            .client_ip   = client_sa.sin_addr.s_addr,
            .client_port = ntohs(client_sa.sin_port)
        };

        pid_t pid = fork();
        if (pid == 0) {
            /* child */
            close(server_fd);
            handle_connection(ctx);
            _exit(0);
        }
        /* parent: close client fd, loop */
        close(cfd);
    }
}

/* ── main ────────────────────────────────────────────────────────────────── */

int main(int argc, char *argv[]) {
    const char *bind_addr = DEFAULT_BIND_ADDR;
    uint16_t    port      = DEFAULT_PORT;

    if (argc >= 2) bind_addr = argv[1];
    if (argc >= 3) port      = (uint16_t)atoi(argv[2]);

    log_init();

    int server_fd = (int)tcp_server_init(bind_addr, port);
    if (server_fd < 0) return 1;

    return tcp_server_accept_loop(server_fd) == TCP_OK ? 0 : 1;
}
