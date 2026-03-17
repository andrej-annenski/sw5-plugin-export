#!/bin/bash
# Uninstall SW5 Plugin Source Exporter
set -e

SCRIPT_NAME="sw5export"
LOCATIONS=("/usr/local/bin/${SCRIPT_NAME}" "${HOME}/.local/bin/${SCRIPT_NAME}")

echo "SW5 Plugin Source Exporter - Deinstallation"
echo ""

removed=0
for loc in "${LOCATIONS[@]}"; do
    if [ -f "$loc" ]; then
        if [ -w "$loc" ]; then
            rm -f "$loc"
        else
            sudo rm -f "$loc"
        fi
        echo "  ✓ Entfernt: $loc"
        removed=$((removed + 1))
    fi
done

if [ $removed -eq 0 ]; then
    echo "  sw5export ist nicht installiert."
else
    echo ""
    echo "  Deinstallation abgeschlossen."
fi
