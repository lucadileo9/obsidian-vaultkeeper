# Specifiche del File di Configurazione (`docs/configuration.md`)

Il comportamento dell'intero motore di **VaultKeeper** e' governato dal file `vault.toml`, caricato e validato tramite la libreria PyPI `proteus-config`.

---

## 1. Risoluzione Gerarchica del File di Configurazione

Quando VaultKeeper viene inizializzato, cerca il file di configurazione secondo questo ordine di precedenza:

1. **Percorso Esplicito:** Passato tramite parametro Python `config_file` o flag CLI `--config <path>`.
2. **Radice del Vault:** File `vault.toml` posizionato direttamente nella cartella root del Vault.
3. **Configurazione Globale Utente:** File posizionato in `~/.config/vaultkeeper/config.toml`.
4. **Fallback Interno:** Valori di default incorporati nella libreria se nessun file e' presente sul disco.

---

## 2. Schema Esaustivo delle Sezioni (`vault.toml`)

### Sezione `[vault]`
Governa i parametri di scansione dell'albero delle cartelle:

```toml
[vault]
# Percorso radice del Second Brain o dell'archivio documentale
root_path = "/srv/storage/Vault"

# Estensioni ammesse all'interno del Vault
allowed_extensions = [".md", ".pdf", ".png", ".jpg", ".jpeg", ".svg", ".docx", ".xlsx", ".pptx"]

# Cartelle ignorate dalla scansione (potatura preventiva dell'albero)
ignored_folders = [".obsidian", ".trash", ".git", ".stversions", ".deleted", "node_modules", ".venv"]

# Lunghezza massima ammessa per i percorsi assoluti (previene blocchi di sincronizzazione)
max_path_length = 240
```

---

### Sezione `[naming]`
Definisce la policy di denominazione di file e cartelle:

```toml
[naming]
# Strategia di normalizzazione: "Title_Case", "kebab-case", "snake_case", "none"
style = "Title_Case"

# Regex dei caratteri vietati da eliminare durante la normalizzazione
disallowed_chars = "[\'\\":?*!&|<>,\\\\\\\\()]"

# Lista di acronimi da preservare rigorosamente in lettere maiuscole
acronyms = ["AI", "API", "AWS", "BCG", "CRM", "HPC", "IT", "JEMORE", "MECE", "SQL", "UX", "MOC", "PKM"]

# Regex per preservare prefissi numerici Johnny.Decimal (es. 00_, 10-19_)
preserve_prefix_pattern = "^[0-9]{2}(-[0-9]{2})?_"
```

---

### Sezione `[frontmatter]`
Stabilisce le regole di tipizzazione per le intestazioni YAML delle note:

```toml
[frontmatter]
# Nome del campo YAML che identifica la tipologia di nota
type_field = "tipo"

# Vocabolario controllato delle tipologie consentite
allowed_types = ["Appunto", "Contatto", "Progetto", "Risorsa", "Indice", "Sistema"]

# Campi obbligatori che devono essere presenti in ogni nota
required_fields = ["tipo", "tags"]
```

---

### Sezione `[tags]`
Controlla la tassonomia dei tag e le eccezioni di parsing:

```toml
[tags]
# Nome o percorso relativo del file contenente la tassonomia ufficiale
taxonomy_file = "00_Tassonomia_Tag.md"

# Se true, qualsiasi tag non presente nella tassonomia genera una violazione di audit
strict_taxonomy = true

# Ignora direttive C/C++ (#include, #define) presenti nei blocchi di testo
protect_c_directives = true

# Ignora codici colore esadecimali (#FFFFFF, #000) presenti nei blocchi di testo
protect_hex_colors = true

# Mappa di sostituzione automatica per tag obsoleti o sinonimi
tag_replacements = { "appunti" = "tipo/appunto", "risorse" = "tipo/risorsa", "progetti" = "tipo/progetto" }
```

---

### Sezione `[attachments]`
Definisce la politica di gestione per immagini, documenti e file binari:

```toml
[attachments]
# Nomi convenzionali per cartelle dedicate agli allegati
folder_names = ["_attachments", "attachments", "assets", "Slide", "media"]

# Soglia in Megabyte per classificare un file come 'pesante' (raccomandato cold storage)
heavy_file_threshold_mb = 50

# Nome della cartella cestino per soft-deletion sicura
trash_folder = ".trash"
```

---

### Sezione `[indices]`
Governa la generazione automatica delle Mappe di Contenuto (MOC):

```toml
[indices]
# Pattern di denominazione: "contextual" (00_Indice_<Cartella>.md), "static" (00_Indice.md), "readme" (README.md)
naming_pattern = "contextual"

# Prefisso per mantenere l'indice in cima alla cartella
prefix = "00_"

# Lunghezza massima in caratteri per il sommario estratto nel corpo dell'indice
summary_max_chars = 250

# Se true, include nell'indice anche file documentali non-Markdown (.pdf, .docx, .xlsx)
include_non_md = true
```

---

## 3. Adattamento per Cartelle Documentali (Google Drive, SharePoint, OneDrive)

VaultKeeper puo' essere impiegato per manutenere archivi documentali privi di note Markdown:

```toml
[vault]
root_path = "/home/lucadileo9/SharePoint/Team_Docs"
allowed_extensions = [".pdf", ".docx", ".xlsx", ".pptx"]

[naming]
style = "kebab-case"                         # Spesso preferito negli ambienti cloud aziendali

[indices]
naming_pattern = "readme"                    # Genera file README.md leggibili via web
include_non_md = true
```
In questa configurazione, `vk generate-indices` crea o aggiorna file `README.md` in ogni cartella elencando tutti i PDF, Word ed Excel con le relative dimensioni in byte.
