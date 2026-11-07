# Manuale di Riferimento della CLI (`docs/cli-reference.md`)

Manuale di riferimento tecnico completo per il comando `vk` di **VaultKeeper**.

---

## 1. Opzioni Globali

Tutti i comandi supportano i seguenti argomenti globali:

```text
vk [-h] [-v] [-q] [--log-file LOG_FILE] [--root ROOT] [--config CONFIG] [--version] <comando>
```

- `-h, --help`: Mostra il messaggio di aiuto ed esce.
- `-v, --verbose`: Attiva il livello di log `DEBUG` a terminale.
- `-q, --quiet`: Sopprime i messaggi informativi, visualizzando esclusivamente `WARNING` ed `ERROR`.
- `--log-file <percorso>`: Salva lo storico delle operazioni in un file di testo piano privo di colori ANSI.
- `--root <percorso>`: Sovrascrive il percorso radice del Vault rispetto al valore di configurazione.
- `--config <percorso>`: Specifica un file `vault.toml` esplicito.
- `--version`: Visualizza la versione corrente del pacchetto ed esce.

---

## 2. Riferimento Dettagliato dei Comandi

### `vk init`
Inizializza un file `vault.toml` con la configurazione di default.

```text
vk init [--target TARGET] [--force]
```
- `--target <dir>`: Cartella in cui generare `vault.toml` (default: cartella di lavoro corrente).
- `--force`: Sovrascrive il file se gia' esistente.

*Esempi:*
```bash
vk init
vk init --target /srv/storage/Vault --force
```

---

### `vk audit`
Esegue la diagnostica multifase e calcola il Vault Health Score.

```text
vk audit [--step {1,2,3,4,5}] [--json FILE] [--report-md FILE]
```
- `--step <1..5>`: Esegue esclusivamente la fase indicata (1: Storage, 2: Nomi, 3: Frontmatter, 4: Tag, 5: Link).
- `--json <file>`: Esporta i risultati dettagliati in un file JSON strutturato.
- `--report-md <file>`: Esporta il resoconto formattato in una nota Markdown.

*Exit Code:* `0` se il Vault e' pulito (0 criticita'); `2` se vengono rilevate violazioni.

*Esempi:*
```bash
# Audit completo su tutto il Vault
vk audit

# Audit rapido focalizzato solo sui collegamenti
vk audit --step 5

# Generazione del report per Obsidian
vk audit --report-md /srv/storage/Vault/01-09_Risorse_Di_Sistema/Report_Audit.md
```

---

### `vk check-links`
Scansiona le note Markdown per isolare collegamenti spezzati o embed mancanti.

```text
vk check-links [--target TARGET]
```
- `--target <path>`: Limita la scansione a una singola nota o a una cartella specifica.

*Exit Code:* `0` se tutti i link sono risolti; `2` se sono presenti link o embed interrotti.

*Esempi:*
```bash
vk check-links
vk check-links --target /srv/storage/Vault/10-19_Progetti/Progetto_Alpha.md
```

---

### `vk clean-attachments`
Individua e bonifica i file multimediali non citati da alcuna nota.

```text
vk clean-attachments [--target TARGET] [--dry-run] [--hard-delete]
```
- `--target <path>`: Circoscrive la ricerca degli orfani a una cartella.
- `--dry-run`: Simula l'azione mostrando i file individuati e lo spazio occupato senza spostarli.
- `--hard-delete`: Elimina i file in modo definitivo anziche' spostarli in `.trash/`.

*Esempi:*
```bash
# Simulazione di sicurezza
vk clean-attachments --dry-run

# Spostamento nel cestino .trash
vk clean-attachments
```

---

### `vk normalize-names`
Rinomina file e cartelle conformemente allo standard impostato (`Title_Case`) e aggiorna atomicamente tutti i wikilink correlati.

```text
vk normalize-names [--target TARGET] [--dry-run]
```
- `--target <path>`: Limita la normalizzazione a una specifica cartella.
- `--dry-run`: Mostra le modifiche previste e il conteggio dei wikilink da sincronizzare senza toccare il disco.

*Esempi:*
```bash
vk normalize-names --target /srv/storage/Vault/20-29_Aree --dry-run
vk normalize-names --target /srv/storage/Vault/20-29_Aree
```

---

### `vk generate-indices`
Crea o aggiorna le note MOC (Map of Content) con naming contestuale anti-collisione (`00_Indice_<Cartella>.md`).

```text
vk generate-indices [--target TARGET] [--all] [--dry-run]
```
- `--target <path>`: Cartella specifica di cui generare o aggiornare l'indice.
- `--all`: Esegue la generazione ricorsiva per tutte le cartelle e sottocartelle del Vault.
- `--dry-run`: Simula la generazione senza scrivere i file su disco.

*Esempi:*
```bash
# Aggiornamento MOC per l'intera gerarchia
vk generate-indices --all

# Aggiornamento puntuale di una cartella
vk generate-indices --target /srv/storage/Vault/10-19_Progetti
```

---

### `vk frontmatter`
Gestione avanzata delle intestazioni YAML frontmatter.

```text
vk frontmatter {set-type,add-tags,sanitize-tags} ...
```

#### Sottocomando `set-type`
```text
vk frontmatter set-type --target NOTE --type TIPO [--dry-run]
```
- `--target <file>`: Percorso della nota da modificare.
- `--type <tipo>`: Valore da impostare nel campo `tipo` (es. `Appunto`, `Progetto`).

#### Sottocomando `add-tags`
```text
vk frontmatter add-tags --target NOTE --tags TAG1 [TAG2 ...] [--overwrite] [--dry-run]
```
- `--target <file>`: Percorso della nota da modificare.
- `--tags`: Uno o piu' tag da inserire.
- `--overwrite`: Sostituisce i tag esistenti invece di appenderli.

#### Sottocomando `sanitize-tags`
```text
vk frontmatter sanitize-tags [--target TARGET] [--dry-run]
```
- Applica la mappatura dei sinonimi definita in `tag_replacements` di `vault.toml`.

*Esempi:*
```bash
vk frontmatter set-type --target /srv/storage/Vault/10-19_Progetti/Nuova_Idea.md --type Progetto
vk frontmatter add-tags --target /srv/storage/Vault/10-19_Progetti/Nuova_Idea.md --tags stato/attivo area/lavoro
vk frontmatter sanitize-tags --dry-run
```

---

### `vk disambiguate`
Rileva e visualizza le note che condividono il medesimo stem in cartelle differenti, suggerendo percorsi di disambiguazione.

```text
vk disambiguate [--target TARGET] [--dry-run]
```

*Exit Code:* `0` se non vi sono collisioni; `2` se vengono rilevate duplicazioni di stem.
