# Batch Operation JSON Templates

This directory contains reference JSON template files for batch operations supported by `obsidian-vaultkeeper` (`vk`).

All batch operations enforce:
1. **Option 1 (Dictionary Mapping Format)**: Key-value dictionary syntax `{key: value}`.
2. **Strict All-or-Nothing Preflight**: If even a single item fails preflight validation (missing note, path collision, invalid type, or non-taxonomic tag under strict mode), the entire batch is rejected with zero disk modifications.
3. **Single Transaction**: Every batch run creates a single journal record that can be completely reverted with `vk undo`.
4. **Dry-Run Simulation**: `--dry-run` flag can be appended to any batch command to preview actions without altering state.

---

## 1. Batch Move (`batch_move_template.json`)

Moves multiple files or directories into target Johnny.Decimal folders and synchronizes folder MOC indices (`00_Indice.md`).

### Format
```json
{
  "source_relative_or_absolute_path": "destination_folder_relative_or_absolute_path"
}
```

### CLI Command
```bash
vk move --batch examples/batch/batch_move_template.json
vk move --batch examples/batch/batch_move_template.json --dry-run
```

---

## 2. Batch Rename (`batch_rename_template.json`)

Renames multiple notes or assets, updates folder indices, and refactors all incoming wikilinks across the vault.

### Format
```json
{
  "target_relative_or_absolute_path": "New_Name_Or_Stem"
}
```

### CLI Command
```bash
vk rename --batch examples/batch/batch_rename_template.json
vk rename --batch examples/batch/batch_rename_template.json --skip-links
vk rename --batch examples/batch/batch_rename_template.json --dry-run
```

---

## 3. Batch Frontmatter Set Type (`batch_set_type_template.json`)

Sets or updates the `tipo` (or configured type field) in the YAML frontmatter of multiple notes. Rejects notes with unconfigured types.

### Format
```json
{
  "target_relative_or_absolute_path": "AllowedType"
}
```

### CLI Command
```bash
vk frontmatter set-type --batch examples/batch/batch_set_type_template.json
vk frontmatter set-type --batch examples/batch/batch_set_type_template.json --dry-run
```

---

## 4. Batch Frontmatter Add Tags (`batch_add_tags_template.json`)

Appends or overwrites tags in the YAML frontmatter of multiple notes. Validates against `00_Tassonomia_Tag.md` if `strict_taxonomy = true`.

### Format
```json
{
  "target_relative_or_absolute_path": [
    "tag1",
    "tag2"
  ]
}
```

### CLI Command
```bash
# Append tags (default)
vk frontmatter add-tags --batch examples/batch/batch_add_tags_template.json

# Overwrite existing tags
vk frontmatter add-tags --batch examples/batch/batch_add_tags_template.json --overwrite

# Dry run
vk frontmatter add-tags --batch examples/batch/batch_add_tags_template.json --dry-run
```
