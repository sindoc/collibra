# c/Makefile — Build trusted TCP acceptor

CC      := gcc
CFLAGS  := -Wall -Wextra -std=c11 -O2 -D_POSIX_C_SOURCE=200809L
INCLUDE := -Iinclude
SRC     := src/accept_tcp.c
BIN_DIR := bin
TARGET  := $(BIN_DIR)/accept_tcp

.PHONY: all clean

all: $(TARGET)

$(BIN_DIR):
	mkdir -p $(BIN_DIR)

$(TARGET): $(SRC) include/tcp_server.h | $(BIN_DIR)
	$(CC) $(CFLAGS) $(INCLUDE) -o $@ $(SRC)
	@echo "Built: $@"

clean:
	rm -rf $(BIN_DIR)
