# Sync automatique reMarkable -> Mac (PDF)

Synchronise toutes les notes de la tablette reMarkable vers le Mac sous forme de PDFs, automatiquement toutes les heures via `launchd`.

Basé sur [rmirro](https://github.com/hersle/rmirro) avec un renderer custom (`render_rmc.py`) qui utilise `rmc` + `cairosvg` pour convertir les fichiers `.rm` natifs en PDF sans dépendre de l'interface web USB.

## Architecture

```
reMarkable (USB/SSH) ──rsync──> remarkable_backup/ (fichiers bruts)
                                       │
                                  render_rmc.py
                                  .rm -> SVG (rmc) -> PDF (cairosvg)
                                       │
                                       ▼
                               remarkable/ (PDFs organisés)
```

### Arborescence des fichiers

```
~/20-DEV/_PYTHON/10-PERSO/rmirro/    # Code source
├── rmirro.py                         # Script principal (modifié : ajout --yes)
├── render_rmc.py                     # Renderer custom rmc+cairosvg
├── sync-remarkable.sh                # Wrapper pour l'automatisation
├── .venv/                            # Virtualenv Python (rmc, cairosvg, pypdf)
└── render_usb.py, render_rmrl.py...  # Autres renderers (non utilisés)

~/Documents/reMarkable/               # Données synchronisées
├── remarkable/                        # PDFs exportés (arborescence miroir)
├── remarkable_backup/                 # Backup brut des fichiers reMarkable
└── remarkable_metadata/               # Fichiers .metadata téléchargés

~/.ssh/config                          # Host SSH "remarkable"
~/.ssh/id_ed25519_remarkable           # Clé SSH dédiée

~/Library/LaunchAgents/com.remarkable.sync.plist   # Service launchd
~/Library/Logs/remarkable-sync.log                 # Logs
```

---

## Installation depuis zéro

### Prérequis

- macOS avec Homebrew
- Python 3.12+ et `uv` (gestionnaire de paquets Python)
- Une tablette reMarkable connectée en USB

### 1. Dépendances système

```bash
brew install cairo rsync sshpass
```

- `cairo` : librairie C de rendu graphique (utilisée par cairosvg)
- `rsync` : déjà présent sur macOS normalement
- `sshpass` : pour la copie initiale de la clé SSH (peut être désinstallé après)

### 2. Cloner rmirro

```bash
git clone https://github.com/hersle/rmirro.git ~/20-DEV/_PYTHON/10-PERSO/rmirro
cd ~/20-DEV/_PYTHON/10-PERSO/rmirro
```

### 3. Créer le virtualenv et installer les dépendances Python

```bash
uv venv .venv
source .venv/bin/activate
uv pip install rmc cairosvg pypdf
```

- `rmc` : convertit les fichiers `.rm` (format natif reMarkable) en SVG
- `cairosvg` : convertit SVG en PDF
- `pypdf` : fusionne les pages PDF pour les documents multi-pages

### 4. Ajouter le flag --yes à rmirro.py

Le script original demande une confirmation interactive. Pour l'automatisation, ajouter le flag `--yes`.

Dans `rmirro.py`, après la ligne `parser.add_argument("-s", ...)` :

```python
parser.add_argument("-y", "--yes", action="store_true", help="auto-confirm all actions (for non-interactive/automated use)")
```

Et remplacer le bloc `input()` (vers la ligne 532) :

```python
# Avant :
answer = input(f"Pull {npull}, push {npush} and drop {ndrop} files (y/n)? ")

# Après :
if args.yes:
    answer = "y"
else:
    answer = input(f"Pull {npull}, push {npush} and drop {ndrop} files (y/n)? ")
```

### 5. Créer le renderer `render_rmc.py`

Copier le fichier `render_rmc.py` dans le dossier rmirro. Ce renderer :

- Cherche les fichiers `.rm` dans le dossier du document (backup)
- Si c'est un PDF/EPUB importé, le copie directement
- Sinon, convertit chaque page `.rm` -> SVG via `rmc`, puis SVG -> PDF via `cairosvg`
- Fusionne les pages avec `pypdf` pour les documents multi-pages
- Crée automatiquement les dossiers parents (gère les noms de documents contenant `/`)

```bash
chmod +x render_rmc.py
```

### 6. Configurer SSH

#### a) Récupérer le mot de passe SSH de la reMarkable

Sur la tablette : **Paramètres > Aide > Informations copyleft** (tout en bas).

#### b) Ajouter le host dans `~/.ssh/config`

```
Host remarkable
    HostName 10.11.99.1
    User root
    IdentityFile ~/.ssh/id_ed25519_remarkable
    IdentitiesOnly yes
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    ConnectTimeout 5
```

`10.11.99.1` est l'IP USB par défaut de la reMarkable.

#### c) Générer et copier la clé SSH

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_remarkable -N "" -C "rmirro-sync"
sshpass -p 'MOT_DE_PASSE_REMARKABLE' ssh-copy-id -i ~/.ssh/id_ed25519_remarkable \
    -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@10.11.99.1
```

#### d) Vérifier

```bash
ssh remarkable "uname -n"
# Doit afficher : reMarkable
```

### 7. Créer le dossier de sortie

```bash
mkdir -p ~/Documents/reMarkable
```

### 8. Créer le script d'automatisation `sync-remarkable.sh`

```bash
#!/bin/bash
set -euo pipefail

RMIRRO_DIR="$HOME/20-DEV/_PYTHON/10-PERSO/rmirro"
OUTPUT_DIR="$HOME/Documents/reMarkable"
LOG_FILE="$HOME/Library/Logs/remarkable-sync.log"
VENV_PYTHON="$RMIRRO_DIR/.venv/bin/python"
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/cairo/lib"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

if ! ssh -o ConnectTimeout=3 remarkable "true" 2>/dev/null; then
    log "reMarkable not reachable, skipping sync"
    exit 0
fi

log "Starting reMarkable sync"
cd "$OUTPUT_DIR"

"$VENV_PYTHON" "$RMIRRO_DIR/rmirro.py" remarkable \
    -r render_rmc.py \
    --yes \
    2>&1 | tee -a "$LOG_FILE"

log "Sync complete"
```

```bash
chmod +x sync-remarkable.sh
```

### 9. Première synchronisation manuelle

```bash
cd ~/Documents/reMarkable
~/20-DEV/_PYTHON/10-PERSO/rmirro/.venv/bin/python \
    ~/20-DEV/_PYTHON/10-PERSO/rmirro/rmirro.py remarkable \
    -r render_rmc.py --yes
```

La première exécution fait un backup complet et prend quelques minutes.

### 10. Configurer l'automatisation avec launchd

Créer `~/Library/LaunchAgents/com.remarkable.sync.plist` :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://purl.apple.com/dtds/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.remarkable.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/TON_USER/20-DEV/_PYTHON/10-PERSO/rmirro/sync-remarkable.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>StandardOutPath</key>
    <string>/Users/TON_USER/Library/Logs/remarkable-sync.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/TON_USER/Library/Logs/remarkable-sync-error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>DYLD_LIBRARY_PATH</key>
        <string>/opt/homebrew/opt/cairo/lib</string>
    </dict>
</dict>
</plist>
```

> Remplacer `TON_USER` par ton nom d'utilisateur macOS.

Activer le service :

```bash
launchctl load ~/Library/LaunchAgents/com.remarkable.sync.plist
```

---

## Utilisation

### Sync manuelle

```bash
~/20-DEV/_PYTHON/10-PERSO/rmirro/sync-remarkable.sh
```

### Consulter les logs

```bash
cat ~/Library/Logs/remarkable-sync.log
tail -f ~/Library/Logs/remarkable-sync.log   # suivi en direct
```

### Désactiver/réactiver la sync automatique

```bash
# Désactiver
launchctl unload ~/Library/LaunchAgents/com.remarkable.sync.plist

# Réactiver
launchctl load ~/Library/LaunchAgents/com.remarkable.sync.plist

# Vérifier l'état
launchctl list | grep remarkable
```

### Changer la fréquence

Modifier `StartInterval` dans le plist (en secondes) :

| Valeur | Fréquence      |
|--------|----------------|
| 1800   | 30 minutes     |
| 3600   | 1 heure        |
| 7200   | 2 heures       |

Puis recharger : `launchctl unload ... && launchctl load ...`

---

## Fonctionnement détaillé

1. Le script vérifie que la reMarkable est joignable en SSH (sinon skip silencieux)
2. `rmirro.py` fait un **rsync** des fichiers bruts vers `remarkable_backup/`
3. Il télécharge les fichiers `.metadata` pour construire l'arborescence
4. Il compare les timestamps pour déterminer les actions (PULL/PUSH/DROP)
5. Pour chaque fichier à PULL, `render_rmc.py` convertit en PDF :
   - Documents importés (PDF/EPUB) : copie directe
   - Notes manuscrites : `.rm` -> SVG (`rmc`) -> PDF (`cairosvg`)
   - Multi-pages : fusion via `pypdf`
6. Les PDFs sont déposés dans `remarkable/` en respectant l'arborescence des dossiers

---

## Dépannage

### "reMarkable not reachable"

- Vérifier que la tablette est branchée en USB
- Vérifier l'IP : `ping 10.11.99.1`
- Tester SSH : `ssh remarkable "uname -n"`

### "no library called cairo was found"

```bash
brew install cairo
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/cairo/lib"
```

### Erreur de rendu sur un document

Lancer en mode verbose pour diagnostiquer :

```bash
cd ~/Documents/reMarkable
~/.../rmirro/.venv/bin/python ~/.../rmirro/rmirro.py remarkable -r render_rmc.py --yes -v
```

### Le venv est cassé après un déplacement

Recréer le venv :

```bash
cd ~/20-DEV/_PYTHON/10-PERSO/rmirro
rm -rf .venv
uv venv .venv
source .venv/bin/activate
uv pip install rmc cairosvg pypdf
```

### Reset complet de la sync

Pour tout resynchroniser depuis zéro :

```bash
rm -rf ~/Documents/reMarkable/remarkable
rm -rf ~/Documents/reMarkable/remarkable_metadata
rm -f ~/Documents/reMarkable/.last_sync
# Puis relancer la sync
```

Le dossier `remarkable_backup/` peut aussi être supprimé mais sera retéléchargé (long).
