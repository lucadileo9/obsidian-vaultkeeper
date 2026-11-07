"""End-to-End lifecycle test verifying complete audit, remediation and clean state."""

from pathlib import Path

from vaultkeeper import Vault


def test_full_vault_lifecycle_and_remediation(empty_temp_dir: Path) -> None:
    """Verify complete lifecycle: uncurated vault -> audit failure -> remediation -> 100% clean."""
    vault_root = empty_temp_dir / "Test_Vault"
    vault_root.mkdir()

    # 1. Setup folders
    folder_meta = vault_root / "00-09_Meta"
    folder_meta.mkdir()
    folder_notes = vault_root / "10-19_Note"
    folder_notes.mkdir()
    folder_media = vault_root / "90-99_Media"
    folder_media.mkdir()

    # 2. Setup taxonomy with frontmatter
    tax_file = folder_meta / "00_Tassonomia_Tag.md"
    tax_file.write_text(
        "---\ntipo: Sistema\ntags:\n  - tipo/sistema\n---\n# Taxonomy\n- #tipo/appunto\n- #tipo/indice\n- #tipo/sistema\n- #stato/attivo\n",
        encoding="utf-8",
    )

    # 3. Create Note 1 (Clean note)
    note1 = folder_notes / "Nota_Uno.md"
    note1.write_text(
        "---\ntipo: Appunto\ntags:\n  - tipo/appunto\n---\n# Nota Uno\n\nContenuto con link a [[bad name]].\n",
        encoding="utf-8",
    )

    # 4. Create Note 2 (Unnormalized name, missing frontmatter, broken link)
    note2 = folder_notes / "bad name.md"
    note2.write_text(
        "# Titolo Senza Frontmatter\n\nLink a [[Non_Esiste]].\n",
        encoding="utf-8",
    )

    # 5. Create orphan attachment
    orphan_img = folder_media / "Orphan_File.png"
    orphan_img.write_bytes(b"\x89PNG\r\n\x1a\n dummy data")

    # Initialize vault
    v = Vault(root_path=vault_root)

    # Initial Audit: Must discover issues and score < 100
    report_initial = v.audit()
    assert report_initial.is_clean() is False
    assert report_initial.total_issues > 0
    assert report_initial.health_score < 100.0

    # Phase 2 has naming violation ("bad name.md")
    assert any("bad name.md" in issue for issue in report_initial.phases[1].issues)
    # Phase 3 has missing frontmatter
    assert any("bad name.md" in issue for issue in report_initial.phases[2].issues)
    # Phase 5 has broken link [[Non_Esiste]]
    assert any("Non_Esiste" in issue for issue in report_initial.phases[4].issues)

    # --- REMEDIATION STEP 1: Normalize names ---
    norm_res = v.normalize_names()
    assert len(norm_res) >= 1
    # bad name.md renamed to Bad_Name.md, and Note 1's link [[bad name]] updated to [[Bad_Name]]
    v.refresh()

    renamed_note2 = folder_notes / "Bad_Name.md"
    assert renamed_note2.is_file()
    assert not (folder_notes / "bad name.md").exists()

    note1_content = note1.read_text(encoding="utf-8")
    assert "[[Bad_Name]]" in note1_content

    # --- REMEDIATION STEP 2: Fix frontmatter in renamed note ---
    v.set_frontmatter_type(renamed_note2, "Appunto")
    v.add_frontmatter_tags(renamed_note2, ["tipo/appunto", "stato/attivo"])

    # --- REMEDIATION STEP 3: Resolve broken link in renamed note ---
    # Replace broken link with valid link to [[Nota_Uno]]
    fixed_body = renamed_note2.read_text(encoding="utf-8").replace("[[Non_Esiste]]", "[[Nota_Uno]]")
    renamed_note2.write_text(fixed_body, encoding="utf-8")

    # --- REMEDIATION STEP 4: Clean orphan attachments ---
    cleaned_attachments = v.clean_attachments(hard_delete=True)
    assert len(cleaned_attachments) == 1
    assert not orphan_img.exists()

    # --- REMEDIATION STEP 5: Generate MOC Indices ---
    idx_results = v.generate_indices(recursive=True)
    assert len(idx_results) >= 1
    v.refresh()

    # Second Audit: Must be 100% clean with perfect Health Score 100.0!
    report_final = v.audit()
    assert report_final.total_issues == 0
    assert report_final.health_score == 100.0
    assert report_final.is_clean() is True
