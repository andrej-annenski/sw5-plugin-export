# SW5 Plugin Source Exporter

Exportiert den kompletten Quellcode eines aktiven Shopware 5 Plugins in eine einzige Textdatei — ideal zur Weitergabe an KI-Tools, Code-Reviews oder Dokumentation.

## Features

- **Automatische Erkennung** aller Shopware 5 Installationen auf dem Server
- **Liest aktive Plugins** direkt aus der Shopware-Datenbank (nur Lesezugriff)
- **Exportiert alle Quelldateien** (.php, .js, .tpl, .xml, .css, .scss, .json, .md, …)
- **Inhaltsverzeichnis** am Anfang der Exportdatei
- **Null Abhängigkeiten** — benötigt nur Python 3, PHP CLI und MySQL CLI (auf jedem Shopware-Server vorhanden)
- Unterstützt **neues** (`custom/plugins/`) und **Legacy** Plugin-System (`engine/Shopware/Plugins/`)

## Installation

### Ein-Befehl-Installation

```bash
curl -sSL https://raw.githubusercontent.com/andrej-annenski/sw5-plugin-export/main/install.sh | bash
```

### Manuelle Installation

```bash
git clone https://github.com/andrej-annenski/sw5-plugin-export.git
sudo cp sw5-plugin-export/sw5export.py /usr/local/bin/sw5export
sudo chmod +x /usr/local/bin/sw5export
```

### Voraussetzungen

Alle diese Programme sind auf einem typischen Shopware 5 Server bereits installiert:

| Programm    | Minimum | Prüfen mit         |
|-------------|---------|---------------------|
| Python 3    | 3.6+    | `python3 --version` |
| PHP CLI     | 7.0+    | `php --version`     |
| MySQL CLI   | 5.6+    | `mysql --version`   |

## Verwendung

```bash
# Automatische Suche nach Shopware-Installationen
sw5export

# Shopware-Pfad manuell angeben
sw5export /var/www/shopware/

# Hilfe anzeigen
sw5export --help
```

### Ablauf

1. Das Script durchsucht `/var/www`, `/home`, `/srv`, `/opt` nach Shopware 5
2. Bei mehreren Installationen wird eine Auswahl angeboten
3. `config.php` wird gelesen, um die DB-Verbindung herzustellen
4. Alle aktiven Plugins werden aus `s_core_plugins` geladen
5. Du wählst ein Plugin aus
6. Alle Quelldateien werden in eine Textdatei auf dem Desktop exportiert

### Beispiel-Ausgabe

Die erzeugte Textdatei hat folgendes Format:

```
================================================================================
  SHOPWARE 5 PLUGIN - VOLLSTAENDIGER QUELLCODE EXPORT
================================================================================
  Plugin:     MeinPlugin
  Pfad:       /var/www/shopware/custom/plugins/MeinPlugin
  Dateien:    42
  Exportiert: 2025-01-15 14:30:00
  Generator:  sw5export v1.0.0
================================================================================

────────────────────────────────────────────────────────────────────────────────
  INHALTSVERZEICHNIS
────────────────────────────────────────────────────────────────────────────────

     1. MeinPlugin.php
     2. Resources/config.xml
     3. Resources/services.xml
     ...


================================================================================
FILE: MeinPlugin.php
================================================================================

<?php
namespace MeinPlugin;
...
```

## Deinstallation

```bash
curl -sSL https://raw.githubusercontent.com/andrej-annenski/sw5-plugin-export/main/uninstall.sh | bash
```

Oder manuell:

```bash
sudo rm /usr/local/bin/sw5export
```

## Unterstützte Dateitypen

Das Script exportiert alle gängigen Quellcode- und Konfigurationsdateien:

**Code:** `.php`, `.js`, `.ts`, `.jsx`, `.tsx`, `.vue`
**Styles:** `.css`, `.scss`, `.sass`, `.less`
**Templates:** `.tpl`, `.twig`, `.html`, `.htm`, `.smarty`
**Config:** `.xml`, `.json`, `.yml`, `.yaml`, `.ini`, `.env`
**Docs:** `.md`, `.txt`, `.rst`
**Sonstige:** `.sql`, `.sh`, `.svg`, `.htaccess`, `composer.json`, `plugin.xml`, …

Binärdateien (Bilder, Fonts, etc.) werden automatisch übersprungen.

## Sicherheit

- Das Script liest **nur** aus der Datenbank — keine Schreibzugriffe
- MySQL-Passwörter werden über temporäre Config-Dateien übergeben (nicht über CLI-Argumente)
- Temporäre Dateien werden sofort nach Verwendung gelöscht

## Kompatibilität

- **OS:** Ubuntu 18.04 und höher (auch Debian, CentOS, etc.)
- **Shopware:** 5.0 bis 5.7.x
- **Plugin-Systeme:** Neues System (`custom/plugins/`) und Legacy (`engine/Shopware/Plugins/`)

## Lizenz

MIT License — siehe [LICENSE](LICENSE)
