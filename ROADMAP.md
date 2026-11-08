# Roadmap Evolutiva e Visione Architetturale (`ROADMAP.md`)

> Piano strategico e specifiche architetturali per l'estensione di **VaultKeeper** (`obsidian-vaultkeeper` / `vk`).

---

## 1. Visione e Obiettivi Strategici

VaultKeeper e' il motore di governance, integrità referenziale e manutenzione universale per Second Brain Obsidian basati su tassonomia controllata e metodo Johnny.Decimal.

L'evoluzione della piattaforma si fonda su tre imperativi architetturali:
1. **Principio DRY Rigoroso (Don't Repeat Yourself):** Centralizzazione di tutte le operazioni ricorrenti (parsing frontmatter, riscrittura wikilink, mutazione indici, gestione transazioni) all'interno di motori dedicati condivisi sia dai comandi preesistenti che dalle nuove funzionalità.
2. **Sicurezza e Reversibilita' Totale (Transaction Journaling):** Nessuna mutazione distruttiva sul filesystem senza la previa generazione di una ricevuta atomica compressa che consenta il rollback istantaneo tramite `vk undo`.
3. **Formattazione Unificata e Polimorfica:** Separazione netta tra estrazione dei dati e presentazione, con supporto universale ai formati `md` (predefinito per Obsidian), `json`, `yaml` e `csv`.

---

## 2. I 6 Motori Fondamentali DRY (`vaultkeeper.core.*`)

Tutti i comandi CLI e i metodi della classe facciata `Vault` operano esclusivamente delegando a 6 motori centralizzati:

### 2.1. `TransactionJournal` (`vaultkeeper.core.journal`)
- **Scopo:** Fornire un context manager transazionale atomico per qualsiasi mutazione (`rename`, `move`, `archive`, `offload`, `clean-attachments`, `normalize-names`, `frontmatter set`).
- **Funzionamento:**
  - Registra l'antidoto (azione inversa, hash preventivo, percorsi originali, testo originale) in `.vaultkeeper/history/<tx_id>.json.gz`.
  - In caso di errore durante l'esecuzione, applica il rollback immediato in memoria prima di sollevare l'eccezione.
  - Alimenta il comando `vk undo` per il ripristino sicuro dell'ultima transazione e `vk history` per l'ispezione della cronologia.
  - Gestisce la rotazione automatica (default: ultime 100 transazioni memorizzate, impatto disco $\le 2$ MB).

### 2.2. `IndexManager` (`vaultkeeper.core.indices`)
- **Scopo:** Unico punto di scrittura per tutti i file indice di cartella (`00_Indice_<Cartella>.md`).
- **Interfaccia:**
  - `add_entry(folder, stem, title)`
  - `remove_entry(folder, stem)`
  - `rename_entry(folder, old_stem, new_stem, new_title=None)`
  - `mark_archived(folder, stem)`
  - `rebuild_index(folder)`

### 2.3. `WikilinkEngine` (`vaultkeeper.core.links`)
- **Scopo:** Analisi, estrazione e riscrittura coerente di tutti i formati di collegamento supportati da Obsidian.
- **Supporto Sintassi:**
  - Wikilink semplici: `[[Nota_Target]]`
  - Wikilink con ancore di sezione: `[[Nota_Target#Sezione]]`
  - Wikilink con alias descrittivi: `[[Nota_Target|Mio Alias]]`
  - Combinazione ancora + alias: `[[Nota_Target#Sezione|Mio Alias]]`
  - Link Markdown standard: `[Mio Alias](percorso/Nota_Target.md)`
  - Embed di allegati: `![[Allegato.png]]` e `![Allegato](percorso/Allegato.png)`

### 2.4. `TaxonomyEngine` (`vaultkeeper.core.taxonomy`)
- **Scopo:** Gestione unificata e sicura del file `00_Tassonomia_Tag.md`.
- **Interfaccia:**
  - `load_taxonomy() -> Set[str]`
  - `is_valid_tag(tag: str) -> bool`
  - `search_tags(query: str) -> List[str]`
  - `add_tag(tag: str, section: Optional[str] = None)`
  - `remove_tag(tag: str, force: bool = False)` (con verifica preventiva di utilizzo nelle note)

### 2.5. `MarkdownDocument` (`vaultkeeper.models.document`)
- **Scopo:** Modello a oggetti atomico per l'interazione con i singoli file `.md`.
- **Proprietà e Metodi:**
  - `frontmatter: Dict[str, Any]` (campi YAML deserializzati e validati)
  - `body: str` (testo Markdown escluso il frontmatter)
  - `wikilinks: List[Wikilink]` (elenco dei link estratti)
  - `replace_wikilink(old_stem, new_stem)`
  - `save(transaction: Optional[TransactionContext] = None)`

### 2.6. `OutputFormatter` (`vaultkeeper.utils.formatters`)
- **Scopo:** Serializzazione polimorfica di report, elenchi e tabelle.
- **Formati Supportati:**
  - `md` (predefinito): Report Markdown con tabelle GFM nativamente consultabili su Obsidian.
  - `json`: Struttura machine-readable per script e automazioni.
  - `yaml`: Formato leggibile human/machine per frontmatter e configurazioni.
  - `csv`: Esportazione tabellare per analisi su fogli di calcolo.

---

## 3. Specifiche Funzionali dei Nuovi Comandi CLI

### 3.1. `vk rename <file> <nuovo_nome>`
- **Descrizione:** Ridenomina una nota o allegato aggiornando tutti i wikilink in ingresso nel Vault.
- **Pre-flight Checks:**
  1. Verifica unicità del nuovo stem: se il nome esiste già in qualsiasi cartella, blocca l'operazione (`CollisionError`).
  2. Verifica unicità del file di origine: se esistono omonimi preesistenti in altre cartelle, richiede `--skip-links` per evitare riscritture ambigue.
- **Azioni Eseguite:** Rinomina file sul disco, riscrittura globale di tutti i wikilink, aggiornamento titolo H1 nella nota e aggiornamento riga in `00_Indice_<Cartella>.md`.
- **Flag:** `--dry-run`, `--skip-links`.
- **Transazionale:** Sì (`vk undo` supportato).

### 3.2. `vk move <file_o_dir> <cartella_destinazione>`
- **Descrizione:** Spostamento topologico Johnny.Decimal senza alterazione dello stem.
- **Azioni Eseguite:** Trasferimento fisico del file/cartella, rimozione da `00_Indice` di partenza, inserimento in `00_Indice` di arrivo. I wikilink globali non vengono toccati.
- **Flag:** `--dry-run`.
- **Transazionale:** Sì (`vk undo` supportato).

### 3.3. `vk archive <path_vault>`
- **Descrizione:** Archiviazione del ciclo di vita verso `vault.archive_path` speculare.
- **Azioni Eseguite:**
  1. Spostamento del file/cartella originale nel percorso speculare in `/srv/storage/Archive/`.
  2. Aggiornamento frontmatter del file archiviato (`stato: archiviato`, `data_archiviazione: YYYY-MM-DD`).
  3. Generazione Tombstone Note nel Vault con estrazione automatica della sintesi iniziale (`> ...` o primo paragrafo) e link esterno all'archivio.
  4. Marcatura della voce come `(Archiviato)` nell'indice di cartella.
- **Flag:** `--no-tombstone`, `--dry-run`.
- **Transazionale:** Sì (`vk undo` supportato).

### 3.4. `vk offload <target>`
- **Descrizione:** Igiene dello storage per allegati binari pesanti (>50MB).
- **Target:** Singolo file (es. `90-99_Allegati/Video.mp4`) o intera cartella (applica la soglia configurata `attachments.max_size_mb`).
- **Azioni Eseguite:**
  1. Spostamento fisico del binario in `attachments.offload_folder`.
  2. Scansione delle note che includevano l'allegato (`![[Video.mp4]]`).
  3. Sostituzione dell'embed con un collegamento trasparente all'archivio:
     `> [!INFO] Allegato archiviato su storage freddo: [Video.mp4](file:///srv/storage/Archive/...)`
  4. La nota Markdown originaria rimane inalterata nella sua cartella attiva.
- **Flag:** `--dry-run`.
- **Transazionale:** Sì (`vk undo` supportato).

### 3.5. `vk search <query>`
- **Descrizione:** Motore di ricerca semantico consapevole della struttura di Obsidian.
- **Filtri Combinabili:**
  - `--tag <tag>`: Filtra per presenza del tag nella nota.
  - `--type <tipo>`: Filtra per campo frontmatter `tipo` (Appunto, Progetto, ecc.).
  - `--links-to <stem>`: Trova tutte le note che contengono un wikilink a quella specifica nota.
  - `--folder <cartella>`: Limita la ricerca a una specifica area Johnny.Decimal.
- **Formati:** `--format md|json|yaml|csv` (default: `md`).
- **Transazionale:** No (Sola lettura).

### 3.6. `vk graph-health`
- **Descrizione:** Telemetria topologica non-punitiva del grafo concettuale.
- **Metriche Calcolate:**
  - Note Isolate (*True Orphans*): grado entrante 0, grado uscente 0, assenti da qualsiasi `00_Indice`.
  - Vicoli Ciechi (*Dead-Ends*): backlink presenti ma zero link uscenti.
  - Top 10 Hub: elenco delle note con il maggior numero di backlink in ingresso.
  - Componenti disconnesse ($\le 3$ note isolate dal grafo principale).
- **Regola di Design:** Valori puramente diagnostici/esplorativi. Zero penalità nel Vault Health Score di `vk audit`.
- **Formati:** `--format md|json|yaml`.
- **Transazionale:** No (Sola lettura).

### 3.7. `vk map`
- **Descrizione:** Generazione della mappa gerarchica Johnny.Decimal ad alto livello.
- **Metriche:** Conteggio note per area, peso complessivo degli allegati, conformità e presenza degli indici `00_Indice`.
- **Opzioni:** `--output <file.md>` per generare il file MOC master radice (`00_Vault_Map.md`).
- **Formati:** `--format md|json`.
- **Transazionale:** No.

### 3.8. `vk tags show|add|remove`
- **`vk tags show`:** Mostra tutti i tag validi della tassonomia controllata, con supporto a ricerca testuale (`--query <termine>`).
- **`vk tags add <tag>`:** Inserisce il tag in `00_Tassonomia_Tag.md` in ordine alfabetico sotto la categoria corretta.
- **`vk tags remove <tag>`:** Rimuove un tag dalla tassonomia previa verifica che nessuna nota nel Vault lo stia utilizzando (blocco di sicurezza con override `--force`).
- **Transazionale:** `add` e `remove` supportati in `vk undo`.

### 3.9. `vk config show|set`
- **`vk config show`:** Stampa l'albero completo delle impostazioni attive caricate tramite `proteus-config`.
- **`vk config set <chiave> <valore>`:** Aggiorna direttamente una direttiva nel file `vault.toml`.
- **Transazionale:** Sì.

### 3.10. `vk create "<Titolo>"`
- **Descrizione:** Creazione standardizzata di nuove note partendo da template Markdown.
- **Parametri:** `--type <tipo>` (obbligatorio), `--folder <path>`, `--tags <tag1,tag2>`, `--template <nome>`.
- **Azioni Eseguite:** Sanitizzazione nome (`Title_Case_Con_Underscore.md`), compilazione template con frontmatter conforme, convalida tag contro la tassonomia, auto-registrazione in `00_Indice_<Cartella>.md`.
- **Transazionale:** Sì (`vk undo` supportato).

### 3.11. `vk history` e `vk undo`
- **`vk history`:** Mostra la tabella Markdown con ID transazione, data/ora, comando eseguito e numero di file coinvolti.
- **`vk undo`:** Ripristina l'ultimo stato valido annullando le modifiche sul filesystem.
- **`vk undo --tx <id>`:** Ripristina una specifica transazione storica.

---

## 4. Pianificazione delle Milestone di Sviluppo

```text
+-----------------------------------------------------------------------------------+
| MILESTONE 1: DRY Foundations & Reversibility Engine                               |
| - TransactionJournal & Context Manager (.vaultkeeper/history/*.json.gz)           |
| - MarkdownDocument Model & Document Object Abstraction                            |
| - OutputFormatter (md, json, yaml, csv)                                           |
| - CLI commands: vk history, vk undo                                               |
| - Migrazione dei comandi esistenti su TransactionJournal (normalize, clean)        |
+-----------------------------------------------------------------------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
| MILESTONE 2: Lifecycle & Safe Refactoring Engine                                  |
| - IndexManager unificato (00_Indice_<Cartella>.md)                                |
| - WikilinkEngine potenziato (ancore, alias, link standard, regex unificata)       |
| - CLI commands: vk rename (con pre-flight checks), vk move, vk archive, vk offload|
| - Integrazione configurazione: vault.archive_path, attachments.offload_folder     |
+-----------------------------------------------------------------------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
| MILESTONE 3: Intelligence, Topology & Taxonomy                                    |
| - TaxonomyEngine (00_Tassonomia_Tag.md)                                           |
| - CLI commands: vk tags show|add|remove, vk config show|set                       |
| - CLI command: vk search (filtri semantici tag, type, links-to, folder)           |
| - CLI command: vk graph-health (telemetria non-punitiva orfani/dead-ends/hub)     |
| - CLI command: vk map (tree view e generazione 00_Vault_Map.md)                   |
+-----------------------------------------------------------------------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
| MILESTONE 4: Templating & Creation Engine                                         |
| - TemplateEngine (templates_folder, interpolazione variabili, validazione)        |
| - CLI command: vk create (con validazione rigida tipo/tags e auto-indicizzazione) |
+-----------------------------------------------------------------------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
| MILESTONE 5 (PARCHEGGIATA): MCP Server Protocol Adapter                           |
| - Esposizione di VaultKeeper via Model Context Protocol (stdio/sse) per agenti AI |
+-----------------------------------------------------------------------------------+
```

---

## 5. Standard di Qualità e Vincoli Inviolabili

- **Copertura Test:** Ogni milestone deve mantenere la copertura dei test $\ge 90\%$ (`pytest --cov=vaultkeeper`).
- **Zero Regressioni:** Tutti i 61 test preesistenti devono continuare a superare le verifiche su Ubuntu, macOS e Windows.
- **Tipizzazione e Stile:** Rigoroso rispetto di `ruff check`, `ruff format` e `mypy src/` con zero avvisi.
- **Convenzioni di Commit:** Commit atomici con messaggi convenzionali (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`) per ciascun file o modulo creato.
