#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# SW5 Plugin Source Exporter - Installer
# https://github.com/andrej-annenski/sw5-plugin-export
# ──────────────────────────────────────────────────────────────────────────────
set -e

REPO="andrej-annenski/sw5-plugin-export"
BRANCH="main"
SCRIPT_NAME="sw5export"
SCRIPT_URL="https://raw.githubusercontent.com/${REPO}/${BRANCH}/sw5export.py"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║  SW5 Plugin Source Exporter - Installation              ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Check prerequisites ─────────────────────────────────────────────────
echo -e "${BOLD}Prüfe Voraussetzungen ...${NC}"

errors=0

# Python 3
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 --version 2>&1)
    echo -e "  ${GREEN}✓${NC} ${PY_VERSION}"
else
    echo -e "  ${RED}✗${NC} Python 3 nicht gefunden!"
    echo -e "    ${YELLOW}→ sudo apt install python3${NC}"
    errors=$((errors + 1))
fi

# PHP CLI
if command -v php &>/dev/null; then
    PHP_VERSION=$(php -v 2>&1 | head -1)
    echo -e "  ${GREEN}✓${NC} ${PHP_VERSION}"
else
    echo -e "  ${RED}✗${NC} PHP CLI nicht gefunden!"
    echo -e "    ${YELLOW}→ sudo apt install php-cli${NC}"
    errors=$((errors + 1))
fi

# MySQL CLI
if command -v mysql &>/dev/null; then
    MYSQL_VERSION=$(mysql --version 2>&1)
    echo -e "  ${GREEN}✓${NC} ${MYSQL_VERSION}"
else
    echo -e "  ${RED}✗${NC} MySQL CLI nicht gefunden!"
    echo -e "    ${YELLOW}→ sudo apt install mysql-client${NC}"
    errors=$((errors + 1))
fi

# curl or wget
HAS_CURL=false
HAS_WGET=false
if command -v curl &>/dev/null; then
    HAS_CURL=true
    echo -e "  ${GREEN}✓${NC} curl"
elif command -v wget &>/dev/null; then
    HAS_WGET=true
    echo -e "  ${GREEN}✓${NC} wget"
else
    echo -e "  ${RED}✗${NC} Weder curl noch wget gefunden!"
    echo -e "    ${YELLOW}→ sudo apt install curl${NC}"
    errors=$((errors + 1))
fi

if [ $errors -gt 0 ]; then
    echo ""
    echo -e "${RED}${errors} fehlende Abhängigkeit(en). Bitte zuerst installieren.${NC}"
    exit 1
fi

echo ""

# ── Determine install location ──────────────────────────────────────────
INSTALL_DIR=""
USE_SUDO=""

if [ -w "/usr/local/bin" ]; then
    INSTALL_DIR="/usr/local/bin"
elif [ "$(id -u)" -eq 0 ]; then
    INSTALL_DIR="/usr/local/bin"
else
    # Try with sudo
    if command -v sudo &>/dev/null; then
        INSTALL_DIR="/usr/local/bin"
        USE_SUDO="sudo"
        echo -e "${YELLOW}Benötige sudo für Installation in /usr/local/bin${NC}"
    else
        # Fallback to user-local
        INSTALL_DIR="${HOME}/.local/bin"
        mkdir -p "${INSTALL_DIR}"
        # Ensure it's in PATH
        if [[ ":$PATH:" != *":${INSTALL_DIR}:"* ]]; then
            echo -e "${YELLOW}Hinweis: ${INSTALL_DIR} ist nicht in PATH.${NC}"
            echo -e "${YELLOW}Füge folgende Zeile zu ~/.bashrc hinzu:${NC}"
            echo -e "  export PATH=\"\$HOME/.local/bin:\$PATH\""
        fi
    fi
fi

INSTALL_PATH="${INSTALL_DIR}/${SCRIPT_NAME}"

echo -e "${BOLD}Installiere nach: ${INSTALL_PATH}${NC}"

# ── Download ─────────────────────────────────────────────────────────────
echo -e "Lade Script herunter ..."

TMPFILE=$(mktemp)
trap "rm -f ${TMPFILE}" EXIT

if [ "$HAS_CURL" = true ]; then
    if ! curl -fsSL "${SCRIPT_URL}" -o "${TMPFILE}" 2>/dev/null; then
        echo -e "${RED}Download fehlgeschlagen!${NC}"
        echo -e "URL: ${SCRIPT_URL}"
        echo -e "${YELLOW}Tipp: Ist das Repository bereits auf GitHub angelegt?${NC}"
        echo ""
        echo -e "Alternativ manuell installieren:"
        echo -e "  1. git clone https://github.com/${REPO}.git"
        echo -e "  2. sudo cp sw5-plugin-export/sw5export.py /usr/local/bin/sw5export"
        echo -e "  3. sudo chmod +x /usr/local/bin/sw5export"
        exit 1
    fi
else
    if ! wget -q "${SCRIPT_URL}" -O "${TMPFILE}" 2>/dev/null; then
        echo -e "${RED}Download fehlgeschlagen!${NC}"
        exit 1
    fi
fi

# Verify it's a Python script
if ! head -1 "${TMPFILE}" | grep -q "python3"; then
    echo -e "${RED}Heruntergeladene Datei ist kein gültiges Python-Script!${NC}"
    echo -e "Möglicherweise ist das GitHub-Repository noch nicht eingerichtet."
    exit 1
fi

# ── Install ──────────────────────────────────────────────────────────────
${USE_SUDO} cp "${TMPFILE}" "${INSTALL_PATH}"
${USE_SUDO} chmod +x "${INSTALL_PATH}"

echo ""
echo -e "${GREEN}${BOLD}✓ Installation erfolgreich!${NC}"
echo ""
echo -e "Verwende jetzt einfach:"
echo -e "  ${BOLD}sw5export${NC}              - Automatische Suche"
echo -e "  ${BOLD}sw5export /pfad/${NC}       - Pfad manuell angeben"
echo -e "  ${BOLD}sw5export --help${NC}       - Hilfe anzeigen"
echo ""
