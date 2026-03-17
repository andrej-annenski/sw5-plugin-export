#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SW5 Plugin Source Exporter
==========================
Finds Shopware 5 installations on the local machine, reads active plugins
from the database, and exports all source code of a selected plugin into
a single text file on the user's Desktop.

Requirements: Python 3.6+, PHP CLI, MySQL CLI (all present on any SW5 server)
No pip dependencies needed.

Author: https://github.com/andrej-annenski
License: MIT
"""

import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path

__version__ = "1.0.0"

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# File extensions considered as source / config files
SOURCE_EXTENSIONS = {
    # PHP / Backend
    '.php', '.phtml', '.inc',
    # JavaScript / TypeScript
    '.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs', '.vue',
    # Styles
    '.css', '.scss', '.sass', '.less', '.styl',
    # Templates
    '.tpl', '.twig', '.smarty', '.html', '.htm', '.xhtml',
    # Data / Config
    '.xml', '.xsd', '.xsl', '.xslt',
    '.json', '.yml', '.yaml', '.toml', '.ini', '.cfg', '.conf',
    '.env', '.dist', '.neon',
    # Documentation
    '.md', '.rst', '.txt', '.adoc',
    # SQL
    '.sql',
    # Shell
    '.sh', '.bash',
    # SVG (often contains template logic in SW5 themes)
    '.svg',
    # Build / Lock
    '.lock',
    # Misc
    '.csv', '.map',
}

# Files without extension (or special names) to always include
SOURCE_FILENAMES = {
    'Makefile', 'Dockerfile', 'Vagrantfile', 'Rakefile',
    '.gitignore', '.gitkeep', '.gitattributes',
    '.editorconfig', '.babelrc', '.eslintrc', '.prettierrc',
    '.htaccess', '.php_cs', '.php-cs-fixer.php',
    'composer.json', 'composer.lock',
    'package.json', 'package-lock.json', 'yarn.lock',
    'Gruntfile.js', 'gulpfile.js', 'webpack.config.js',
    'plugin.xml', 'plugin.png',  # plugin.png skipped by binary check
    'services.xml', 'config.xml',
    'LICENSE', 'CHANGELOG', 'UPGRADE',
}

# Where to search for Shopware installations
SEARCH_PATHS = ['/var/www', '/home', '/srv', '/opt', '/usr/share']

# Max depth for find command
MAX_SEARCH_DEPTH = 7


# ─────────────────────────────────────────────────────────────────────────────
# Colors (ANSI)
# ─────────────────────────────────────────────────────────────────────────────

class C:
    """ANSI color helpers. Disabled if not a TTY."""
    enabled = sys.stdout.isatty()

    @staticmethod
    def _wrap(code, text):
        return f"\033[{code}m{text}\033[0m" if C.enabled else text

    @staticmethod
    def bold(t):    return C._wrap("1", t)
    @staticmethod
    def green(t):   return C._wrap("32", t)
    @staticmethod
    def yellow(t):  return C._wrap("33", t)
    @staticmethod
    def red(t):     return C._wrap("31", t)
    @staticmethod
    def cyan(t):    return C._wrap("36", t)
    @staticmethod
    def dim(t):     return C._wrap("2", t)


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Find Shopware 5 Installations
# ─────────────────────────────────────────────────────────────────────────────

def find_shopware5_installations():
    """
    Search common web directories for Shopware 5 installations.
    A valid SW5 install has config.php + engine/Shopware/ directory.
    """
    installations = []

    for search_path in SEARCH_PATHS:
        if not os.path.isdir(search_path):
            continue
        try:
            result = subprocess.run(
                ['find', search_path,
                 '-maxdepth', str(MAX_SEARCH_DEPTH),
                 '-name', 'config.php',
                 '-type', 'f',
                 '-not', '-path', '*/vendor/*',
                 '-not', '-path', '*/node_modules/*'],
                capture_output=True, text=True, timeout=60
            )
            for config_path in result.stdout.strip().split('\n'):
                config_path = config_path.strip()
                if not config_path:
                    continue
                shop_dir = os.path.dirname(config_path)

                # Must have engine/Shopware/ to be Shopware 5
                engine_dir = os.path.join(shop_dir, 'engine', 'Shopware')
                if not os.path.isdir(engine_dir):
                    continue

                # Extra verification: check for shopware.php or autoload.php
                has_shopware_php = os.path.isfile(os.path.join(shop_dir, 'shopware.php'))
                has_autoload = os.path.isfile(os.path.join(shop_dir, 'autoload.php'))
                if has_shopware_php or has_autoload:
                    installations.append(shop_dir)

        except subprocess.TimeoutExpired:
            print(C.yellow(f"  Warnung: Suche in {search_path} dauerte zu lange, übersprungen."))
        except Exception as e:
            print(C.yellow(f"  Warnung: Fehler bei Suche in {search_path}: {e}"))

    # Deduplicate and sort
    return sorted(set(installations))


def detect_shopware_version(shop_dir):
    """Try to detect Shopware version from the installation."""
    # Try reading from engine/Shopware/Application.php
    app_file = os.path.join(shop_dir, 'engine', 'Shopware', 'Application.php')
    if os.path.isfile(app_file):
        try:
            with open(app_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if "'version'" in line or '"version"' in line:
                        # Extract version string
                        for part in line.split("'") + line.split('"'):
                            if part and part[0].isdigit() and '.' in part:
                                return part
        except Exception:
            pass

    # Try recovery/install/data/version
    version_file = os.path.join(shop_dir, 'recovery', 'install', 'data', 'version')
    if os.path.isfile(version_file):
        try:
            with open(version_file, 'r') as f:
                return f.read().strip()
        except Exception:
            pass

    return "unbekannt"


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Read Shopware Config
# ─────────────────────────────────────────────────────────────────────────────

def read_shopware_config(shop_dir):
    """
    Parse Shopware's config.php using PHP CLI and return DB credentials.
    config.php returns a PHP array - we use PHP to convert it to JSON.
    """
    config_path = os.path.join(shop_dir, 'config.php')
    if not os.path.isfile(config_path):
        return None

    php_code = f'echo json_encode(include "{config_path}");'
    try:
        result = subprocess.run(
            ['php', '-r', php_code],
            capture_output=True, text=True, timeout=10,
            cwd=shop_dir  # Some configs use relative paths
        )
        if result.returncode != 0:
            print(C.red(f"  PHP Fehler: {result.stderr.strip()}"))
            return None

        config = json.loads(result.stdout)
        db = config.get('db', {})
        if not db.get('dbname'):
            print(C.red("  Keine Datenbank-Konfiguration in config.php gefunden!"))
            return None
        return db

    except json.JSONDecodeError:
        print(C.red("  config.php konnte nicht als JSON geparst werden."))
        return None
    except FileNotFoundError:
        print(C.red("  PHP CLI nicht gefunden! Bitte 'php' installieren."))
        sys.exit(1)
    except Exception as e:
        print(C.red(f"  Fehler beim Lesen der Config: {e}"))
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Query Active Plugins from Database
# ─────────────────────────────────────────────────────────────────────────────

def mysql_query(db_config, query):
    """
    Execute a MySQL query using a temporary config file (avoids password
    exposure via process list and the CLI warning).
    """
    cnf_path = None
    try:
        # Write temporary MySQL config
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.cnf', prefix='sw5exp_', delete=False
        ) as f:
            f.write("[client]\n")
            f.write(f"user={db_config.get('username', 'root')}\n")
            f.write(f"password={db_config.get('password', '')}\n")
            f.write(f"host={db_config.get('host', 'localhost')}\n")
            f.write(f"port={db_config.get('port', '3306')}\n")
            # Handle unix_socket if present
            socket = db_config.get('unix_socket') or db_config.get('socket')
            if socket:
                f.write(f"socket={socket}\n")
            cnf_path = f.name

        os.chmod(cnf_path, 0o600)

        cmd = [
            'mysql',
            f'--defaults-extra-file={cnf_path}',
            db_config.get('dbname', 'shopware'),
            '-N', '-B', '--default-character-set=utf8',
            '-e', query
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

        if result.returncode != 0:
            stderr = result.stderr.strip()
            # Filter out the common "Using password on CLI" warning
            lines = [l for l in stderr.split('\n')
                     if 'Using a password on the command line' not in l]
            if lines:
                print(C.red(f"  MySQL Fehler: {' '.join(lines)}"))
                return None

        return result.stdout

    except FileNotFoundError:
        print(C.red("  MySQL CLI nicht gefunden! Bitte 'mysql' installieren."))
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(C.red("  MySQL Timeout - Datenbank nicht erreichbar?"))
        return None
    except Exception as e:
        print(C.red(f"  Datenbankfehler: {e}"))
        return None
    finally:
        if cnf_path and os.path.exists(cnf_path):
            os.unlink(cnf_path)


def query_active_plugins(db_config):
    """Query all active plugins from the s_core_plugins table."""
    query = (
        "SELECT name, label, source, namespace, version, author "
        "FROM s_core_plugins "
        "WHERE active = 1 "
        "ORDER BY name ASC"
    )

    output = mysql_query(db_config, query)
    if output is None:
        return []

    plugins = []
    for line in output.strip().split('\n'):
        if not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) >= 4:
            plugins.append({
                'name':      parts[0],
                'label':     parts[1] if len(parts) > 1 else parts[0],
                'source':    parts[2] if len(parts) > 2 else '',
                'namespace': parts[3] if len(parts) > 3 else '',
                'version':   parts[4] if len(parts) > 4 else '',
                'author':    parts[5] if len(parts) > 5 else '',
            })

    return plugins


# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Resolve Plugin Path & Export
# ─────────────────────────────────────────────────────────────────────────────

def resolve_plugin_path(shop_dir, plugin):
    """
    Determine the filesystem path of a plugin based on DB metadata.
    Checks new-style (custom/plugins/) first, then legacy paths.
    """
    name = plugin['name']
    source = plugin['source']
    namespace = plugin['namespace']

    candidates = [
        # New plugin system (SW 5.2+)
        os.path.join(shop_dir, 'custom', 'plugins', name),
        # Legacy: engine/Shopware/Plugins/{Source}/{Namespace}/{Name}
        os.path.join(shop_dir, 'engine', 'Shopware', 'Plugins', source, namespace, name),
        # Sometimes Local plugins
        os.path.join(shop_dir, 'engine', 'Shopware', 'Plugins', 'Local', namespace, name),
        os.path.join(shop_dir, 'engine', 'Shopware', 'Plugins', 'Community', namespace, name),
        # custom/project (rare)
        os.path.join(shop_dir, 'custom', 'project', name),
    ]

    for path in candidates:
        if os.path.isdir(path):
            return path

    return None


def is_source_file(filepath):
    """Check if a file should be included based on extension or name."""
    basename = os.path.basename(filepath)

    # Check known filenames
    if basename in SOURCE_FILENAMES:
        return True

    # Check extension
    _, ext = os.path.splitext(basename)
    if ext.lower() in SOURCE_EXTENSIONS:
        return True

    # Dotfiles without further extension (like .htaccess, .env.local)
    if basename.startswith('.') and not ext:
        return True

    return False


def is_binary_file(filepath, sample_size=8192):
    """Quick heuristic: read a chunk and look for null bytes."""
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(sample_size)
            # Empty files are fine
            if not chunk:
                return False
            # Null bytes indicate binary
            if b'\x00' in chunk:
                return True
            return False
    except (OSError, IOError):
        return True


def collect_source_files(plugin_path):
    """Walk the plugin directory and collect all source/config files."""
    files = []
    skip_dirs = {'.git', '.svn', '.hg', 'vendor', 'node_modules',
                 '__pycache__', '.idea', '.vscode'}

    for root, dirs, filenames in os.walk(plugin_path):
        # Filter directories in-place to prevent descent
        dirs[:] = sorted([d for d in dirs if d not in skip_dirs])

        for filename in sorted(filenames):
            filepath = os.path.join(root, filename)

            if not is_source_file(filepath):
                continue
            if is_binary_file(filepath):
                continue

            files.append(filepath)

    return files


def export_plugin_source(plugin_path, plugin_name, output_path):
    """
    Export all source files of a plugin into a single text file.
    Each file is preceded by a clear header showing its relative path.
    """
    files = collect_source_files(plugin_path)

    if not files:
        print(C.red("  Keine Quelldateien im Plugin-Verzeichnis gefunden!"))
        return False

    separator = "=" * 80

    with open(output_path, 'w', encoding='utf-8') as out:
        # Header
        out.write(f"{separator}\n")
        out.write(f"  SHOPWARE 5 PLUGIN - VOLLSTAENDIGER QUELLCODE EXPORT\n")
        out.write(f"{separator}\n")
        out.write(f"  Plugin:     {plugin_name}\n")
        out.write(f"  Pfad:       {plugin_path}\n")
        out.write(f"  Dateien:    {len(files)}\n")
        out.write(f"  Exportiert: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        out.write(f"  Generator:  sw5export v{__version__}\n")
        out.write(f"{separator}\n")

        # Table of contents
        out.write(f"\n{'─' * 80}\n")
        out.write("  INHALTSVERZEICHNIS\n")
        out.write(f"{'─' * 80}\n\n")
        for i, filepath in enumerate(files, 1):
            rel = os.path.relpath(filepath, plugin_path)
            out.write(f"  {i:4d}. {rel}\n")

        # File contents
        for filepath in files:
            rel_path = os.path.relpath(filepath, plugin_path)
            out.write(f"\n\n{separator}\n")
            out.write(f"FILE: {rel_path}\n")
            out.write(f"{separator}\n\n")
            try:
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    out.write(content)
                    # Ensure file ends with newline
                    if content and not content.endswith('\n'):
                        out.write('\n')
            except Exception as e:
                out.write(f"[FEHLER: Datei konnte nicht gelesen werden: {e}]\n")

    return True


# ─────────────────────────────────────────────────────────────────────────────
# UI Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_desktop_path():
    """Determine the user's Desktop directory (supports DE/EN/custom)."""
    home = Path.home()

    # Check XDG user dirs first
    xdg_config = home / '.config' / 'user-dirs.dirs'
    if xdg_config.is_file():
        try:
            with open(xdg_config, 'r') as f:
                for line in f:
                    if line.startswith('XDG_DESKTOP_DIR='):
                        path_str = line.split('=', 1)[1].strip().strip('"')
                        path_str = path_str.replace('$HOME', str(home))
                        p = Path(path_str)
                        if p.is_dir():
                            return p
        except Exception:
            pass

    # Common desktop directory names
    for name in ['Desktop', 'Schreibtisch', 'Bureau', 'Escritorio']:
        p = home / name
        if p.is_dir():
            return p

    # Fallback: home directory
    return home


def select_from_list(prompt, items, format_func=str):
    """Interactive numbered list selection."""
    print(f"\n{C.bold(prompt)}\n")
    for i, item in enumerate(items, 1):
        print(f"  {C.cyan(f'[{i}]')} {format_func(item)}")
    print()

    while True:
        try:
            raw = input(f"  Auswahl (1-{len(items)}): ").strip()
            if not raw:
                continue
            idx = int(raw) - 1
            if 0 <= idx < len(items):
                return items[idx]
            print(C.yellow(f"  Bitte eine Zahl zwischen 1 und {len(items)} eingeben."))
        except ValueError:
            print(C.yellow("  Bitte eine gültige Zahl eingeben."))
        except (EOFError, KeyboardInterrupt):
            print(C.yellow("\n  Abgebrochen."))
            sys.exit(0)


def format_size(size_bytes):
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1048576:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / 1048576:.1f} MB"


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print()
    print(C.bold("╔══════════════════════════════════════════════════════════╗"))
    print(C.bold("║       SW5 Plugin Source Exporter  v" + __version__ + "               ║"))
    print(C.bold("║       Shopware 5 Plugin-Quellcode als Textdatei        ║"))
    print(C.bold("╚══════════════════════════════════════════════════════════╝"))

    # ── Step 1: Find Shopware installations ──────────────────────────────
    print(f"\n{C.bold('[1/4]')} Suche nach Shopware 5 Installationen ...")
    print(C.dim(f"       Durchsuche: {', '.join(SEARCH_PATHS)}"))

    installations = find_shopware5_installations()

    if not installations:
        print(C.red("\n  Keine Shopware 5 Installation gefunden!"))
        print(C.dim("  Tipp: Liegt die Installation in einem anderen Verzeichnis?"))
        print(C.dim("  Du kannst den Pfad auch manuell angeben:"))
        print(C.dim("    sw5export /pfad/zur/shopware/installation"))
        # Allow manual path as argument
        sys.exit(1)

    # Show found installations with version
    for inst in installations:
        ver = detect_shopware_version(inst)
        print(f"  {C.green('✓')} {inst} {C.dim(f'(v{ver})')}")

    # ── Step 2: Select installation ──────────────────────────────────────
    if len(installations) == 1:
        shop_dir = installations[0]
        print(f"\n  Verwende einzige Installation: {C.bold(shop_dir)}")
    else:
        shop_dir = select_from_list(
            "[2/4] Shopware-Installation auswählen:",
            installations,
            format_func=lambda d: f"{d} {C.dim(f'(v{detect_shopware_version(d)})')}"
        )

    # ── Step 3: Read config & query active plugins ───────────────────────
    print(f"\n{C.bold('[2/4]')} Lese Datenbank-Konfiguration ...")
    db_config = read_shopware_config(shop_dir)
    if not db_config:
        print(C.red("  Konnte config.php nicht parsen!"))
        sys.exit(1)

    db_name = db_config.get('dbname', '?')
    db_host = db_config.get('host', '?')
    print(f"  {C.green('✓')} Datenbank: {C.bold(db_name)} @ {db_host}")

    print(f"\n{C.bold('[3/4]')} Lese aktive Plugins aus der Datenbank ...")
    plugins = query_active_plugins(db_config)

    if not plugins:
        print(C.red("  Keine aktiven Plugins in der Datenbank gefunden!"))
        sys.exit(1)

    print(f"  {C.green('✓')} {C.bold(str(len(plugins)))} aktive(s) Plugin(s) gefunden.")

    # ── Step 4: Select plugin ────────────────────────────────────────────
    def format_plugin(p):
        ver = p['version']
        src = p['source']
        ns = p['namespace']
        auth = p['author']
        parts = [
            C.bold(p['name']),
            C.dim('v' + ver),
            '- ' + p['label'],
            C.dim('[' + src + '/' + ns + ']'),
        ]
        if auth:
            parts.append(C.dim('von ' + auth))
        return ' '.join(parts)

    plugin = select_from_list(
        "[3/4] Plugin zum Exportieren auswählen:",
        plugins,
        format_func=format_plugin
    )

    # ── Resolve plugin directory ─────────────────────────────────────────
    plugin_path = resolve_plugin_path(shop_dir, plugin)

    if not plugin_path:
        print(C.red(f"\n  Plugin-Verzeichnis für '{plugin['name']}' nicht gefunden!"))
        print(C.dim("  Geprüfte Pfade:"))
        for candidate in [
            os.path.join(shop_dir, 'custom', 'plugins', plugin['name']),
            os.path.join(shop_dir, 'engine', 'Shopware', 'Plugins',
                         plugin['source'], plugin['namespace'], plugin['name']),
        ]:
            print(C.dim(f"    - {candidate}"))
        print(C.dim("\n  Hinweis: Dies kann bei Core-Plugins passieren, deren Code"))
        print(C.dim("  direkt im Shopware-Kern liegt und kein eigenes Verzeichnis hat."))
        sys.exit(1)

    print(f"\n  Plugin-Pfad: {C.bold(plugin_path)}")

    # ── Count files first ────────────────────────────────────────────────
    source_files = collect_source_files(plugin_path)
    print(f"  Quelldateien: {C.bold(str(len(source_files)))}")

    if not source_files:
        print(C.red("  Keine exportierbaren Quelldateien gefunden!"))
        sys.exit(1)

    # ── Step 5: Export ───────────────────────────────────────────────────
    desktop = get_desktop_path()
    safe_name = plugin['name'].replace('/', '_').replace('\\', '_')
    output_file = desktop / f"SW5_Plugin_{safe_name}_source.txt"

    print(f"\n{C.bold('[4/4]')} Exportiere Quellcode ...")
    print(f"  Ziel: {C.bold(str(output_file))}")

    if export_plugin_source(plugin_path, plugin['name'], str(output_file)):
        file_size = os.path.getsize(str(output_file))
        print(f"\n  {C.green('✓')} {C.bold('Export erfolgreich!')}")
        print(f"    Datei:   {output_file}")
        print(f"    Größe:   {format_size(file_size)}")
        print(f"    Dateien: {len(source_files)}")
        print()
    else:
        print(C.red("\n  Export fehlgeschlagen!"))
        sys.exit(1)


def main_with_args():
    """Entry point that handles optional manual path argument."""
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ('-h', '--help'):
            print(f"""
SW5 Plugin Source Exporter v{__version__}

Verwendung:
  sw5export              Automatische Suche nach Shopware 5 Installationen
  sw5export /pfad/       Shopware-Installation manuell angeben
  sw5export --help       Diese Hilfe anzeigen
  sw5export --version    Version anzeigen

Beschreibung:
  Findet Shopware 5 Installationen, liest aktive Plugins aus der Datenbank,
  und exportiert den gesamten Quellcode eines Plugins in eine Textdatei
  auf dem Desktop.

Voraussetzungen:
  - Python 3.6+
  - PHP CLI (php)
  - MySQL CLI (mysql)

GitHub: https://github.com/andrej-annenski/sw5-plugin-export
""")
            sys.exit(0)
        elif arg in ('-v', '--version'):
            print(f"sw5export v{__version__}")
            sys.exit(0)
        elif os.path.isdir(arg):
            # Check if it's a valid Shopware installation
            if os.path.isdir(os.path.join(arg, 'engine', 'Shopware')):
                # Monkey-patch to use provided path
                global find_shopware5_installations
                original = find_shopware5_installations
                find_shopware5_installations = lambda: [os.path.abspath(arg)]
                main()
                return
            else:
                print(C.red(f"  '{arg}' ist keine gültige Shopware 5 Installation!"))
                print(C.dim("  (engine/Shopware/ Verzeichnis nicht gefunden)"))
                sys.exit(1)
        else:
            print(C.red(f"  Unbekannte Option oder Pfad: {arg}"))
            print(C.dim("  Verwende 'sw5export --help' für Hilfe."))
            sys.exit(1)
    else:
        main()


if __name__ == '__main__':
    main_with_args()
