/*
 * tcp_server.h — Trusted TCP acceptor interface
 * Singine smtpAgent C layer
 *
 * Accepts inbound TCP connections on a loopback-bound port and relays
 * data to the Clojure SMTP service via a child-process pipe.
 * Only connections from TRUSTED_ORIGIN are accepted; all others are
 * immediately closed without reading data.
 */

#ifndef TCP_SERVER_H
#define TCP_SERVER_H

#include <stdint.h>

/* Maximum simultaneous connections accepted (matches meta/config.edn :backlog) */
#define TCP_BACKLOG       10

/* Relay buffer size in bytes */
#define RELAY_BUF_SIZE    65536

/* Default bind address — loopback only for trusted operation */
#define DEFAULT_BIND_ADDR "127.0.0.1"
#define DEFAULT_PORT      8025

/* Trusted origin — connections from any other source are silently dropped */
#define TRUSTED_ORIGIN    "127.0.0.1"

/* Log file path (relative to working directory) */
#define LOG_PATH          "logs/tcp_accept.log"

/* Clojure SMTP service HTTP endpoint (for relaying parsed requests) */
#define SMTP_SERVICE_URL  "http://127.0.0.1:8026/send"

/* Result codes */
typedef enum {
    TCP_OK           =  0,
    TCP_ERR_SOCKET   = -1,
    TCP_ERR_BIND     = -2,
    TCP_ERR_LISTEN   = -3,
    TCP_ERR_ACCEPT   = -4,
    TCP_ERR_UNTRUSTED = -5,
    TCP_ERR_RELAY    = -6
} tcp_result_t;

/* Connection context passed to each accepted-connection handler */
typedef struct {
    int      client_fd;
    uint32_t client_ip;   /* network byte order */
    uint16_t client_port; /* host byte order    */
} conn_ctx_t;

/* Public API */
tcp_result_t tcp_server_init(const char *bind_addr, uint16_t port);
tcp_result_t tcp_server_accept_loop(int server_fd);
int          is_trusted_origin(uint32_t ip_nbo);
void         log_connection(const conn_ctx_t *ctx, const char *event);

#endif /* TCP_SERVER_H */
