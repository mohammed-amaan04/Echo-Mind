"""Phase 3 tests — entity normalization (pure unit tests, no DB needed)."""

from echomind.persistence.entity_normalizer import normalize_entity_name


class TestNormalizeEntityName:
    def test_lowercase(self) -> None:
        assert normalize_entity_name("Amaan") == "amaan shaikh"  # alias mapped

    def test_strip_whitespace(self) -> None:
        assert normalize_entity_name("  hello  ") == "hello"

    def test_collapse_internal_whitespace(self) -> None:
        assert normalize_entity_name("some   name") == "some name"

    def test_remove_punctuation(self) -> None:
        assert normalize_entity_name("EchoMind!") == "echomind"

    def test_alias_mapping_amaan(self) -> None:
        assert normalize_entity_name("Amaan") == "amaan shaikh"
        assert normalize_entity_name("amaan") == "amaan shaikh"

    def test_alias_mapping_abrar(self) -> None:
        assert normalize_entity_name("Abrar") == "abrar ahmed"

    def test_alias_mapping_abdullah(self) -> None:
        assert normalize_entity_name("Abdullah") == "abdullah khan"

    def test_no_alias_passthrough(self) -> None:
        assert normalize_entity_name("PostgreSQL") == "postgresql"

    def test_unicode_normalization(self) -> None:
        # NFKD decomposes e.g. ﬁ → fi
        assert normalize_entity_name("ﬁle") == "file"

    def test_empty_string(self) -> None:
        assert normalize_entity_name("") == ""
