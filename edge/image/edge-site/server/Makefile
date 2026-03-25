# Makefile — build edge-site-server.jar
#
# Compiles EdgeSiteServerMain.java (JDK 11 built-ins only, no external deps)
# and packages it as an executable JAR.
#
#   make              → build edge-site-server.jar
#   make clean        → remove build artefacts
#   make install      → copy JAR to ../edge-site-server.jar (Dockerfile context)

SERVER_DIR  := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
BUILD_DIR   := $(SERVER_DIR)/build
JAR_OUT     := $(SERVER_DIR)/edge-site-server.jar
MANIFEST    := $(BUILD_DIR)/MANIFEST.MF
SRC         := $(SERVER_DIR)/EdgeSiteServerMain.java

.PHONY: all clean install

all: $(JAR_OUT)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(BUILD_DIR)/EdgeSiteServerMain.class: $(SRC) | $(BUILD_DIR)
	javac -source 11 -target 11 -d $(BUILD_DIR) $(SRC)

$(MANIFEST): | $(BUILD_DIR)
	@printf 'Main-Class: EdgeSiteServerMain\nManifest-Version: 1.0\n' > $(MANIFEST)

$(JAR_OUT): $(BUILD_DIR)/EdgeSiteServerMain.class $(MANIFEST)
	jar cfm $(JAR_OUT) $(MANIFEST) -C $(BUILD_DIR) .
	@echo "Built: $(JAR_OUT)"

install: $(JAR_OUT)
	cp $(JAR_OUT) $(SERVER_DIR)/../edge-site-server.jar
	@echo "Installed: $(SERVER_DIR)/../edge-site-server.jar"

clean:
	rm -rf $(BUILD_DIR) $(JAR_OUT)
