# Modelli di Dominio (Domain Models)

Il package `vaultkeeper.models` definisce le strutture dati immutabili e fortemente tipizzate impiegate dall'intero ecosistema di `obsidian-vaultkeeper`. 
La separazione dei modelli dal motore computazionale garantisce che la logica di dominio e il presentation layer scambino contratti deterministici, serializzabili e privi di effetti collaterali.

Tutti i 23 modelli sono organizzati in 5 moduli specializzati e riesportati collettivamente attraverso `vaultkeeper.models.__init__`.

---

## Mappa delle Relazioni tra Modelli

```mermaid
flowchart TD
    subgraph Configurazione
        VC["VaultConfig"]
    end

    subgraph Entita
        FM["Frontmatter"]
        NT["Note"]
        CAT["VaultCatalog"]
        NT --> FM
        CAT -.-> NT
    end

    subgraph Journal
        AR["ActionRecord"]
        TR["TransactionRecord"]
        UR["UndoResult"]
        TR o-- "1..*" AR
    end

    subgraph Risultati
        RR["RenameResult"]
        MR["MoveResult"]
        AcR["ArchiveResult"]
        OR["OffloadResult"]
        TMR["TagMutationResult"]
        CR["CreateResult"]
    end

    subgraph Telemetria
        BL["BrokenLink"]
        OA["OrphanAttachment"]
        PR["PhaseResult"]
        ARep["AuditReport"]
        SRI["SearchResultItem"]
        SR["SearchResult"]
        GH["GraphHub"]
        GHR["GraphHealthReport"]
        AS["AreaSummary"]
        VMR["VaultMapReport"]

        ARep o-- "1..*" PR
        SR o-- "0..*" SRI
        GHR o-- "0..*" GH
        VMR o-- "1..*" AS
    end

    VC -.-> CAT
    TR -.-> UR
```

---

## 1. Configurazione (`vaultkeeper.models.config`)

### `VaultConfig`
Rappresenta lo schema di configurazione del Vault caricato da `vault.toml` o dedotto dai parametri di default del sistema.

- **Import:** `from vaultkeeper.models import VaultConfig` (oppure `from vaultkeeper.models.config import VaultConfig`)
- **Produttore:** `vaultkeeper.config.load_vault_config()`
- **Consumatore:** `Vault`, tutti i moduli di `vaultkeeper.core.*`

#### Campi e Tipizzazione

| Campo | Tipo | Valore Predefinito | Descrizione |
| :--- | :--- | :--- | :--- |
| `root_path` | `Path` | *Obbligatorio* | Percorso assoluto della radice del Vault sul filesystem. |
| `allowed_extensions` | `Set[str]` | `{".md", ".pdf", ".png", ".jpg", ".jpeg", ".svg", ".docx", ".xlsx", ".pptx"}` | Insieme delle estensioni ammesse all'interno del Vault. |
| `ignored_folders` | `Set[str]` | `{".obsidian", ".trash", ".git", ".stversions", ".deleted", "node_modules", ".venv"}` | Cartelle escluse ricorsivamente da scansione e indicizzazione. |
| `max_path_length` | `int` | `240` | Limite massimo di caratteri per i percorsi file (anti-troncamento). |
| `naming_style` | `str` | `"Title_Case"` | Convenzione di denominazione delle note (`Title_Case_Con_Underscore`). |
| `acronyms` | `Set[str]` | `{"AI", "API", "AWS", "BCG", "CRM", "HPC", "IT", "JEMORE", "MECE", "SQL", "UX", "MOC", "PKM"}` | Sigle protette da forzature minuscole durante la normalizzazione. |
| `disallowed_chars_regex` | `str` | `r"['\":?*!&|<>,\\()]"` | Regex dei caratteri illegali nei nomi dei file. |
| `preserve_prefix_pattern` | `str` | `r"^[0-9]{2}(-[0-9]{2})?_"` | Pattern numerico Johnny.Decimal preservato durante la normalizzazione. |
| `type_field` | `str` | `"tipo"` | Chiave frontmatter deputata alla classificazione della nota. |
| `allowed_types` | `List[str]` | `["Appunto", "Contatto", "Progetto", "Risorsa", "Indice", "Sistema"]` | Vocabolario controllato dei tipi ammessi. |
| `required_frontmatter_fields` | `List[str]` | `["tipo", "tags"]` | Campi frontmatter obbligatori per il superamento dell'audit. |
| `taxonomy_file` | `Optional[str]` | `"00_Tassonomia_Tag.md"` | Nome del file sentinella contenente la tassonomia ufficiale dei tag. |
| `strict_taxonomy` | `bool` | `True` | Se attivo, vieta l'uso di tag non censiti nel file di tassonomia. |
| `protect_c_directives` | `bool` | `True` | Protegge direttive C (es. `#include`, `#define`) da parsing come tag. |
| `protect_hex_colors` | `bool` | `True` | Protegge codici colore esadecimali (es. `#FFFFFF`) da parsing come tag. |
| `tag_replacements` | `Dict[str, str]` | `{"appunti": "tipo/appunto", ...}` | Mappa di riscrittura automatica per tag obsoleti o errati. |
| `attachment_folders` | `List[str]` | `["_attachments", "attachments", "assets", "Slide", "media"]` | Nomi standard delle cartelle destinate agli allegati. |
| `heavy_file_threshold_mb` | `int` | `50` | Soglia in Megabyte oltre la quale un allegato è classificato pesante. |
| `trash_folder` | `str` | `".trash"` | Directory di destinazione per le eliminazioni reversibili (soft-delete). |
| `index_naming_pattern` | `str` | `"contextual"` | Strategia di denominazione dei file MOC (`00_Indice_<Cartella>.md`). |
| `index_prefix` | `str` | `"00_"` | Prefisso dei file MOC di cartella. |
| `index_summary_max_chars` | `int` | `250` | Lunghezza massima dell'abstract estratto per l'indice. |
| `include_non_md_in_indices` | `bool` | `True` | Include allegati (PDF, immagini) nella sezione media dell'indice. |
| `archive_path` | `Optional[str]` | `None` | Percorso opzionale del Cold Storage di archivio speculare. |
| `templates_folder` | `Optional[str]` | `"00-09_Meta/02_Template"` | Percorso relativo della cartella dei template. |
| `offload_folder` | `Optional[str]` | `None` | Percorso opzionale per il trasferimento automatico di media pesanti. |
| `max_undo_history` | `int` | `100` | Numero massimo di transazioni conservate nel journal su disco. |

---

## 2. Entità di Dominio (`vaultkeeper.models.entities`)

### `Frontmatter`
Rappresenta i metadati YAML posizionati all'inizio di una nota Markdown.

- **Import:** `from vaultkeeper.models import Frontmatter`
- **Produttore:** `vaultkeeper.core.frontmatter.parse_note_content()`, `MarkdownDocument`
- **Consumatore:** `Note`, `AuditEngine`, `SearchEngine`, comandi `vk frontmatter`

#### Campi
- `raw_content: str`: Blocco YAML testuale grezzo, inclusi i delimitatori `---`.
- `metadata: Dict[str, Any]`: Dizionario Python risultante dal parsing YAML.
- `tipo: Optional[str]`: Valore della chiave tipologica (es. `"Appunto"`, `"Progetto"`).
- `tags: List[str]`: Lista dei tag normalizzati (privi del carattere `#`).

#### Metodi Helper
- `has_tag(tag: str) -> bool`: Restituisce `True` se il tag specificato è presente nella nota.
- `is_valid_type(allowed_types: List[str]) -> bool`: Verifica se il campo `tipo` appartiene all'insieme dei tipi consentiti.

---

### `Note`
Rappresentazione astratta e disaccoppiata di un appunto Markdown presente nel Vault.

- **Import:** `from vaultkeeper.models import Note`
- **Produttore:** `vaultkeeper.core.frontmatter.read_note()`, `Vault.get_note()`
- **Consumatore:** `IndexManager`, `SearchEngine`, comandi CLI di ispezione

#### Campi
- `file_path: Path`: Percorso assoluto del file `.md`.
- `rel_path: Path`: Percorso relativo rispetto alla radice del Vault.
- `frontmatter: Optional[Frontmatter]`: Oggetto frontmatter estratto, oppure `None` se assente o malformato.
- `body: str`: Corpo testuale della nota privato del blocco frontmatter.
- `size_bytes: int`: Dimensione del file in byte su disco.

---

### `VaultCatalog`
Indice $O(1)$ in memoria contenente la mappatura completa di percorsi, stem e file del Vault. Consente di evitare scansioni ricorsive del disco durante operazioni ripetitive (es. risoluzione wikilink o audit).

- **Import:** `from vaultkeeper.models import VaultCatalog`
- **Produttore:** `vaultkeeper.core.traversal.build_vault_catalog()`
- **Consumatore:** `Vault.catalog`, `WikilinkEngine`, `SearchEngine`, `GraphTelemetry`

#### Campi
- `vault_root: Path`: Radice del Vault indicizzato.
- `notes_by_stem: Dict[str, List[Path]]`: Mappa tra stem normalizzato (es. `"Architettura_Sistema"`) e percorsi assoluti corrispondenti (supporta il rilevamento di collisioni).
- `files_by_name: Set[str]`: Insieme di tutti i nomi file presenti nel Vault (con estensione).
- `rel_paths: Set[str]`: Insieme di tutti i percorsi relativi serializzati in formato stringa.
- `total_files: int`: Conteggio totale dei file validi censiti.
- `total_size_bytes: int`: Volume complessivo in byte dei file censiti.

---

## 3. Motore Transazionale e Reversibilità (`vaultkeeper.models.journal`)

### `ActionRecord`
Rappresenta una micro-mutazione atomica e reversibile operata sul filesystem o sul contenuto di un file.

- **Import:** `from vaultkeeper.models import ActionRecord`
- **Produttore:** Metodi di `Transaction` (`write_content`, `move_file`, `create_file`, `delete_file`)
- **Consumatore:** `TransactionRecord`, `TransactionJournal.undo()`

#### Campi
- `action_type: str`: Natura dell'operazione (`"write_content"`, `"move_file"`, `"create_file"`, `"delete_file"`).
- `path: str`: Percorso sorgente del file coinvolto.
- `target_path: Optional[str]`: Percorso di destinazione (valorizzato per spostamenti o rinomine).
- `content_before: Optional[str]`: Testo antecedente alla mutazione (per file di testo).
- `content_after: Optional[str]`: Testo successivo alla mutazione.
- `hash_before: Optional[str]`: Hash SHA-256 pre-mutazione (per verifica integrità anti-conflitto).
- `hash_after: Optional[str]`: Hash SHA-256 post-mutazione.
- `metadata: Dict[str, Any]`: Metadati addizionali (es. permessi, dimensione, opzioni).

#### Metodi di Serializzazione
- `to_dict() -> Dict[str, Any]`: Converte il record in dizionario serializzabile JSON.
- `classmethod from_dict(data: Dict[str, Any]) -> ActionRecord`: Ricostruisce il record da JSON.

---

### `TransactionRecord`
Incapsula una transazione completata, composta da una o più azioni correlate che devono essere annullate o ripristinate congiuntamente.

- **Import:** `from vaultkeeper.models import TransactionRecord`
- **Produttore:** `TransactionJournal.commit()`
- **Consumatore:** `TransactionJournal.list_transactions()`, `TransactionJournal.undo()`, `vk history`

#### Campi
- `tx_id: str`: Identificativo univoco temporale con entropia (es. `"tx_20261108_143015_123456_a1b2c3"`).
- `timestamp: str`: Timestamp ISO 8601 UTC di creazione.
- `command: str`: Nome del comando CLI o metodo Python invocato (es. `"rename"`, `"normalize-names"`).
- `description: str`: Sintesi ad alto livello dell'operazione.
- `actions: List[ActionRecord]`: Sequenza ordinata delle azioni atomiche eseguite.
- `reverted: bool`: Flag booleano che indica se la transazione è già stata annullata.
- `reverted_at: Optional[str]`: Timestamp ISO 8601 del rollback (se applicato).

---

### `UndoResult`
Esito dell'operazione di rollback eseguita da `TransactionJournal.undo()` o dal comando `vk undo`.

- **Import:** `from vaultkeeper.models import UndoResult`
- **Produttore:** `TransactionJournal.undo()`
- **Consumatore:** `Vault.undo()`, `vk undo`

#### Campi
- `tx_id: str`: Identificativo della transazione sottoposta a rollback.
- `success: bool`: `True` se il ripristino di tutte le azioni ha avuto esito positivo.
- `reverted_actions: int`: Numero di micro-azioni ripristinate con successo in ordine inverso.
- `message: str`: Dettaglio testuale sull'esito o spiegazione della causa di blocco.
- `affected_files: List[str]`: Elenco dei percorsi ripristinati sul filesystem.

---

## 4. Risultati delle Operazioni di Scrittura (`vaultkeeper.models.results`)

I modelli di risultato rappresentano l'output immutabile delle mutazioni eseguite sul Vault, esponendo sia il nuovo stato sia l'identificativo della transazione generata per il rollback.

### `RenameResult`
Esito dell'operazione `Vault.rename()` / `vk rename`.

- `old_path: Path`: Percorso originario della nota.
- `new_path: Path`: Nuovo percorso con stem normalizzato.
- `updated_links_count: int`: Numero di wikilink interni aggiornati nell'intero Vault.
- `index_updated: bool`: `True` se il file `00_Indice.md` della cartella è stato risincronizzato.
- `tx_id: Optional[str]`: Identificativo della transazione registrata nel Journal (se non `--dry-run`).

### `MoveResult`
Esito dell'operazione `Vault.move()` / `vk move`.

- `source_path: Path`: Percorso originale del file o cartella.
- `dest_path: Path`: Percorso di destinazione finale.
- `old_index_updated: bool`: Aggiornamento del MOC della cartella di partenza.
- `new_index_updated: bool`: Aggiornamento del MOC della cartella di arrivo.
- `tx_id: Optional[str]`: Identificativo di transazione per il rollback.

### `ArchiveResult`
Esito dell'operazione `Vault.archive()` / `vk archive`.

- `source_path: Path`: Posizione originale nel Vault.
- `archive_path: Path`: Posizione finale nel cold storage (`/srv/storage/Archive`).
- `tombstone_created: bool`: Indica se nel Vault è stata depositata la scheda tombstone con backlink.
- `summary: str`: Sintesi testuale dell'esito.
- `tx_id: Optional[str]`: Identificativo di transazione.

### `OffloadResult`
Esito dell'operazione `Vault.offload()` / `vk offload`.

- `offloaded_files: List[Tuple[Path, Path, int]]`: Elenco delle tuple `(sorgente, destinazione, byte_risparmiati)`.
- `total_bytes_saved: int`: Volume complessivo alleggerito dal Vault.
- `updated_notes_count: int`: Numero di note Markdown i cui puntamenti sono stati convertiti.
- `tx_id: Optional[str]`: Identificativo di transazione.

### `TagMutationResult`
Esito delle operazioni di mutazione tassonomica `Vault.tags_add()` e `Vault.tags_remove()`.

- `tag: str`: Tag modificato.
- `action: str`: Azione applicata (`"add"` o `"remove"`).
- `taxonomy_file: Path`: File di tassonomia aggiornato.
- `notes_affected_count: int`: Numero di note modificate sul filesystem.
- `tx_id: Optional[str]`: Identificativo di transazione.

### `CreateResult`
Esito dell'operazione di creazione standardizzata `Vault.create()` / `vk create`.

- `file_path: Path`: Percorso assoluto della nuova nota generata.
- `rel_path: Path`: Percorso relativo rispetto al Vault.
- `stem: str`: Nome file privo di estensione normalizzato in Title_Case.
- `title: str`: Titolo originale dell'appunto.
- `tipo: str`: Tipologia assegnata (`Appunto`, `Progetto`, `Contatto`, `Risorsa`).
- `tags: List[str]`: Tag assegnati e validati.
- `template_used: Optional[str]`: Nome del template risolto e applicato.
- `index_updated: bool`: Esito dell'aggiornamento automatico dell'indice di cartella.
- `index_path: Optional[Path]`: Percorso del file MOC aggiornato.
- `tx_id: Optional[str]`: Transazione di creazione per rollback con `vk undo`.
- `dry_run: bool`: `True` se l'operazione è stata una simulazione.

---

## 5. Telemetria e Diagnostica (`vaultkeeper.models.telemetry`)

### `BrokenLink`
Rappresenta un collegamento non risolto scoperto all'interno di una nota.

- `source_file: Path`: Nota Markdown in cui risiede il link orfano.
- `line_number: int`: Riga esatta del documento in cui compare il link.
- `raw_target: str`: Contenuto grezzo tra parentesi quadre (es. `[[Concetto#Sezione|Alias]]`).
- `clean_target: str`: Stem o percorso ripulito da ancore e alias.
- `anchor: Optional[str]`: Sezione o blocco specificato dopo `#`.
- `alias: Optional[str]`: Testo alternativo specificato dopo `|`.
- `is_media_embed() -> bool`: Restituisce `True` se il bersaglio è un file binario o multimediale.

---

### `OrphanAttachment`
Rappresenta un allegato presente su disco che non risulta citato da alcuna nota del Vault.

- `file_path: Path`: Percorso assoluto dell'allegato.
- `rel_path: Path`: Percorso relativo.
- `size_bytes: int`: Peso in byte del file orfano.
- `folder_type: str`: Classificazione della cartella di appartenenza (es. `"dedicated_attachment"`, `"root"`).

---

### `PhaseResult` & `AuditReport`
Modelli aggregati che compongono il referto dell'audit a 5 fasi.

#### `PhaseResult`
- `phase_id: int`: Identificativo della fase (da 1 a 5).
- `title: str`: Titolo descrittivo della fase diagnostica.
- `issues: List[str]`: Problematiche bloccanti (penalità piena sul punteggio).
- `warnings: List[str]`: Avvertimenti minori (penalità lieve).
- `metrics: Dict[str, Any]`: Metriche quantitative della fase.
- `is_clean() -> bool`: Restituisce `True` se non sussistono criticità.

#### `AuditReport`
- `vault_root: Path`: Radice del Vault verificato.
- `timestamp: str`: Data e ora dell'esecuzione.
- `phases: List[PhaseResult]`: Risultati strutturati delle 5 fasi.
- `total_issues: int`: Somma algebrica delle problematiche riscontrate.
- `health_score: float`: Punteggio di salute del Vault (da 0.0 a 100.0).
- `is_clean() -> bool`: `True` se `total_issues == 0`.
- `to_dict() -> Dict[str, Any]`: Serializzazione completa JSON-compatibile.

---

### `SearchResultItem` & `SearchResult`
Modelli restituiti dal motore di ricerca semantico e tassonomico.

#### `SearchResultItem`
- `file_path: Path`: Percorso assoluto della nota corrispondente.
- `rel_path: str`: Percorso relativo per visualizzazione sintetica.
- `title: str`: Titolo della nota desunto dal nome o dal primo header H1.
- `tipo: Optional[str]`: Tipologia desunta dal frontmatter.
- `tags: List[str]`: Insieme dei tag assegnati.
- `matched_terms: List[str]`: Termini o criteri che hanno innescato il match.
- `snippet: str`: Estratto contestuale ad alto contrasto del testo circostante.

#### `SearchResult`
- `query: Optional[str]`: Termini testuali ricercati.
- `filters: Dict[str, Any]`: Filtri addizionali applicati (tag, cartella, tipo, links_to).
- `items: List[SearchResultItem]`: Lista delle note individuate.
- `total_matches: int`: Conteggio totale dei riscontri.
- `to_dict() -> Dict[str, Any]`: Serializzazione per export JSON.

---

### `GraphHub` & `GraphHealthReport`
Modelli di telemetria topologica generati da `GraphTelemetry` per l'analisi della rete concettuale.

#### `GraphHub`
- `stem: str`: Nome della nota centrale.
- `file_path: Path`: Percorso del file.
- `in_degree: int`: Numero di collegamenti entranti (backlink).
- `out_degree: int`: Numero di collegamenti uscenti (forward link).

#### `GraphHealthReport`
- `vault_root: Path`: Radice del Vault analizzato.
- `timestamp: str`: Data e ora dell'analisi.
- `total_nodes: int`: Numero totale di nodi (note censite).
- `total_edges: int`: Numero complessivo di connessioni (wikilink validi).
- `true_orphans: List[str]`: Note con grado totale nullo (nessun link entrante né uscente).
- `dead_ends: List[str]`: Note che ricevono citazioni ma non rimandano ad alcun altro concetto.
- `top_hubs: List[GraphHub]`: Note a più alta densità di connessioni (centri di gravitazione).
- `disconnected_components: List[List[str]]`: Grappoli concettuali isolati dal corpo centrale della rete.
- `to_dict() -> Dict[str, Any]`: Serializzazione per visualizzatori di grafo o export.

---

### `AreaSummary` & `VaultMapReport`
Modelli cartografici per la navigazione e il monitoraggio dell'architettura Johnny.Decimal.

#### `AreaSummary`
- `area_name: str`: Denominazione dell'area decimale (es. `"10-19_Progetti"`).
- `path: Path`: Percorso assoluto della cartella di area.
- `notes_count: int`: Numero di file Markdown presenti nell'area.
- `attachments_count: int`: Numero di file non-Markdown presenti.
- `total_bytes: int`: Peso su disco dell'intera area.
- `has_index: bool`: Presenza confermata del file `00_Indice.md`.
- `index_path: Optional[Path]`: Percorso dell'indice (se esistente).

#### `VaultMapReport`
- `vault_root: Path`: Radice del Vault.
- `timestamp: str`: Timestamp di generazione.
- `total_notes: int`: Totale note nell'intero Vault.
- `total_attachments: int`: Totale allegati nell'intero Vault.
- `total_bytes: int`: Volume totale occupato.
- `areas: List[AreaSummary]`: Mappatura analitica per singola area decimale.
- `to_dict() -> Dict[str, Any]`: Esportazione strutturata.
