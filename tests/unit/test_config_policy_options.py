"""Unit tests for the Story 02-14 typed policy config options."""

from pathlib import Path

import pytest

from docsentinel import Config, ConfigError, load_config
from docsentinel.engine import scan


def test_policy_option_defaults_match_specification():
    """
    [Unit] config: verifies policy option defaults match specification.

    Scenario:
        Given a default Config instance
        When its Milestone 0005 policy options are read
        Then each option equals the value named in the milestone specification.

    Boundaries:
        - Focus: policy option defaults
        - Fixtures/params: none
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the specific policy option default
        - Recent changes to Config field defaults
        - The milestone story that owns the option
    """
    config = Config()
    assert config.anchor_collision_policy == "explicit"
    assert config.anchor_renderer == "github"
    assert config.heading_level_policy == "no-skips"
    assert config.first_heading_level == 1
    assert config.multiple_h1_policy == "allow"
    assert config.setext_heading_support is True
    assert config.empty_section_policy == "leaf"
    assert config.empty_section_min_text_chars == 0
    assert config.duplicate_reference_definitions == "warn"
    assert config.fence_dialect == "gfm-subset"
    assert config.require_fence_languages is False
    assert config.allow_unlabelled_empty_fences is True
    assert config.allowed_fence_languages == ()
    assert config.table_enable is True
    assert config.navigation_indexes == ()
    assert config.asset_extensions == ("png", "jpg", "jpeg", "svg", "webp", "gif", "pdf")
    assert config.check_html_asset_tags is True
    assert config.check_markdown_images is True
    assert config.check_srcset is True
    assert config.missing_asset_policy == "error"
    assert config.root_escape_policy == "error"
    assert config.document_id_field == "id"
    assert config.deprecated_references_file == ""
    assert config.documentation_naming == "off"
    assert config.documentation_naming_allow == ("README.md", "index.md")


def test_standalone_toml_loads_policy_options(tmp_path: Path):
    """
    [Unit] config: verifies standalone toml loads policy options.

    Scenario:
        Given a standalone doc_sentinel.toml setting several policy options
        When load_config reads the scan root
        Then the typed Config reflects each configured policy value.

    Boundaries:
        - Focus: standalone TOML policy loading
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the loaded option values
        - The _load_extra_options validation path
        - Recent changes to the standalone loader
    """
    (tmp_path / "doc_sentinel.toml").write_text(
        'multiple_h1_policy = "warn"\n'
        "first_heading_level = 2\n"
        "require_fence_languages = true\n"
        'allowed_fence_languages = ["python", "toml"]\n'
        'navigation_indexes = ["docs/index.md"]\n'
        'documentation_naming = "kebab"\n',
        encoding="utf-8",
    )

    config = load_config(tmp_path)
    assert config.multiple_h1_policy == "warn"
    assert config.first_heading_level == 2
    assert config.require_fence_languages is True
    assert config.allowed_fence_languages == ("python", "toml")
    assert config.navigation_indexes == ("docs/index.md",)
    assert config.documentation_naming == "kebab"


def test_pyproject_table_loads_policy_options(tmp_path: Path):
    """
    [Unit] config: verifies pyproject table loads policy options.

    Scenario:
        Given a [tool.doc_sentinel] table setting several policy options
        When load_config reads the scan root
        Then the typed Config reflects each configured policy value.

    Boundaries:
        - Focus: pyproject table policy loading
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the loaded option values
        - The pyproject unwrapping in _load_toml_table
        - Recent changes to the pyproject loader
    """
    (tmp_path / "pyproject.toml").write_text(
        "[tool.doc_sentinel]\n"
        'root_escape_policy = "warn"\n'
        "document_id_case_sensitive = false\n"
        'deprecated_references_file = "docs/deprecated.toml"\n',
        encoding="utf-8",
    )

    config = load_config(tmp_path)
    assert config.root_escape_policy == "warn"
    assert config.document_id_case_sensitive is False
    assert config.deprecated_references_file == "docs/deprecated.toml"


def test_ds113_asset_options_load_from_standalone_and_pyproject(tmp_path: Path):
    """
    [Unit] config: verifies DS113 asset options load from standalone and pyproject TOML.

    Scenario:
        Given a standalone doc_sentinel.toml and, separately, a [tool.doc_sentinel] pyproject table each
            setting the DS113 asset options (asset_extensions, the three check_* toggles, and
            missing_asset_policy)
        When load_config reads each scan root
        Then the typed Config reflects the configured DS113 values from both sources.

    Boundaries:
        - Focus: DS113 config options are typed, validated, and selectable from both TOML sources
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Whether missing_asset_policy joined _ENUM_OPTIONS and the check_* flags joined _BOOL_OPTIONS
        - Whether asset_extensions is in _STR_LIST_OPTIONS and _CONFIG_OPTIONS
    """
    standalone_root = tmp_path / "standalone"
    standalone_root.mkdir()
    (standalone_root / "doc_sentinel.toml").write_text(
        'asset_extensions = ["pdf", "png"]\n'
        "check_html_asset_tags = false\n"
        "check_markdown_images = false\n"
        "check_srcset = false\n"
        'missing_asset_policy = "warn"\n',
        encoding="utf-8",
    )
    standalone = load_config(standalone_root)
    assert standalone.asset_extensions == ("pdf", "png")
    assert standalone.check_html_asset_tags is False
    assert standalone.check_markdown_images is False
    assert standalone.check_srcset is False
    assert standalone.missing_asset_policy == "warn"

    pyproject_root = tmp_path / "pyproject"
    pyproject_root.mkdir()
    (pyproject_root / "pyproject.toml").write_text(
        '[tool.doc_sentinel]\nmissing_asset_policy = "off"\nasset_extensions = ["svg"]\n',
        encoding="utf-8",
    )
    pyproject = load_config(pyproject_root)
    assert pyproject.missing_asset_policy == "off"
    assert pyproject.asset_extensions == ("svg",)


def test_injected_config_wins_over_discovered_file(tmp_path: Path):
    """
    [Unit] config: verifies injected config wins over discovered file.

    Scenario:
        Given an on-disk doc_sentinel.toml selecting the standard profile
        When scan runs with a library-supplied fast-profile Config
        Then the injected Config is used and the result profile is fast.

    Boundaries:
        - Focus: library Config precedence over file defaults
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the effective profile
        - The config-selection branch in engine.scan
        - Recent changes to load_config invocation
    """
    (tmp_path / "doc_sentinel.toml").write_text('profile = "standard"\n', encoding="utf-8")
    (tmp_path / "README.md").write_text("# Title\n\nBody.\n", encoding="utf-8")

    result = scan(tmp_path, config=Config(profile="fast"))
    assert result.profile == "fast"


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("anchor_renderer", '"gitlab"', "anchor_renderer must be one of: github"),
        ("multiple_h1_policy", '"deny"', "multiple_h1_policy must be one of:"),
        ("fence_dialect", '"commonmark"', "fence_dialect must be one of: gfm-subset"),
        ("missing_asset_policy", '"silent"', "missing_asset_policy must be one of:"),
        ("documentation_naming", '"camel"', "documentation_naming must be one of:"),
    ],
)
def test_invalid_enum_option_raises(tmp_path: Path, option: str, value: str, message: str):
    """
    [Unit] config: verifies invalid enum option raises.

    Scenario:
        Given a TOML file with an out-of-vocabulary enum value
        When load_config validates the option
        Then a ConfigError with a vocabulary message is raised.

    Boundaries:
        - Focus: enum vocabulary validation
        - Fixtures/params: tmp_path, option/value/message (parametrized, 4 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the raised error message
        - The _require_enum helper and _ENUM_OPTIONS map
        - Recent changes to enum allowlists
    """
    (tmp_path / "doc_sentinel.toml").write_text(f"{option} = {value}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        load_config(tmp_path)


@pytest.mark.parametrize("value", ['"true"', "1", "0", '["x"]', "1.0"])
def test_invalid_bool_option_raises(tmp_path: Path, value: str):
    """
    [Unit] config: verifies invalid bool option raises.

    Scenario:
        Given a TOML file with a non-boolean value for a boolean option
        When load_config validates the option
        Then a ConfigError is raised.

    Boundaries:
        - Focus: boolean option validation
        - Fixtures/params: tmp_path, value (parametrized, 5 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the raised error message
        - The _require_bool helper
        - Recent changes to _BOOL_OPTIONS
    """
    (tmp_path / "doc_sentinel.toml").write_text(f"table_enable = {value}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="table_enable must be true or false"):
        load_config(tmp_path)


@pytest.mark.parametrize("value", ["0", "7", "true", '"1"', "1.5"])
def test_first_heading_level_out_of_range_raises(tmp_path: Path, value: str):
    """
    [Unit] config: verifies first heading level out of range raises.

    Scenario:
        Given a TOML file with first_heading_level outside 1..6 or non-integer
        When load_config validates the option
        Then a ConfigError about the 1..6 range is raised.

    Boundaries:
        - Focus: integer-range validation
        - Fixtures/params: tmp_path, value (parametrized, 5 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the raised error message
        - The first_heading_level branch in _load_extra_options
        - Recent changes to range validation
    """
    (tmp_path / "doc_sentinel.toml").write_text(f"first_heading_level = {value}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="first_heading_level must be an integer between 1 and 6"):
        load_config(tmp_path)


@pytest.mark.parametrize("value", ["-1", "true", "1.0", '"3"'])
def test_empty_section_min_text_chars_negative_raises(tmp_path: Path, value: str):
    """
    [Unit] config: verifies empty section min text chars negative raises.

    Scenario:
        Given a TOML file with a negative or non-integer min-text-chars value
        When load_config validates the option
        Then a ConfigError about a non-negative integer is raised.

    Boundaries:
        - Focus: non-negative integer validation
        - Fixtures/params: tmp_path, value (parametrized, 4 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the raised error message
        - The empty_section_min_text_chars branch in _load_extra_options
        - Recent changes to range validation
    """
    (tmp_path / "doc_sentinel.toml").write_text(f"empty_section_min_text_chars = {value}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="empty_section_min_text_chars must be a non-negative integer"):
        load_config(tmp_path)


@pytest.mark.parametrize("value", ['"python"', "123", '[""]', "[1]", "{}"])
def test_invalid_string_list_option_raises(tmp_path: Path, value: str):
    """
    [Unit] config: verifies invalid string list option raises.

    Scenario:
        Given a TOML file with a malformed string-list value
        When load_config validates the option
        Then a ConfigError about a list of nonempty strings is raised.

    Boundaries:
        - Focus: string-list validation
        - Fixtures/params: tmp_path, value (parametrized, 5 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the raised error message
        - The _require_str_list helper
        - Recent changes to _STR_LIST_OPTIONS
    """
    (tmp_path / "doc_sentinel.toml").write_text(f"allowed_fence_languages = {value}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="allowed_fence_languages must be a list of nonempty strings"):
        load_config(tmp_path)


@pytest.mark.parametrize("entry", ['"python bash"', '" python"', '"py\\tx"'])
def test_allowed_fence_language_with_whitespace_raises(tmp_path: Path, entry: str):
    """
    [Unit] config: verifies allowlist entries containing whitespace are rejected.

    Scenario:
        Given a TOML file whose allowed_fence_languages lists an entry with internal, leading or
        tab whitespace
        When load_config validates the option
        Then a ConfigError about single-token entries is raised, because a fence language is the
        first whitespace-delimited token and such an entry could never match one.

    Boundaries:
        - Focus: the dedicated single-token check for allowed_fence_languages only
        - Fixtures/params: tmp_path, entry (parametrized, 3 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - The _require_fence_language_list whitespace guard
        - That other string-list options still use the plain _require_str_list validator
    """
    (tmp_path / "doc_sentinel.toml").write_text(f"allowed_fence_languages = [{entry}]\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="allowed_fence_languages entries must be single tokens without whitespace"):
        load_config(tmp_path)


@pytest.mark.parametrize("entry", ["c++", "objective-c", "f#", "html.erb"])
def test_allowed_fence_language_punctuation_tokens_accepted(tmp_path: Path, entry: str):
    """
    [Unit] config: verifies punctuation-bearing single-token languages stay valid.

    Scenario:
        Given a TOML file whose allowed_fence_languages lists a whitespace-free token that contains
        punctuation such as c++, objective-c, f# or html.erb
        When load_config validates the option
        Then the token is accepted unchanged, because only whitespace (not punctuation) is rejected.

    Boundaries:
        - Focus: the whitespace guard does not over-reject ordinary punctuation tokens
        - Fixtures/params: tmp_path, entry (parametrized, 4 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - That _require_fence_language_list rejects only whitespace, not every non-word character
        - That the accepted token round-trips into Config.allowed_fence_languages
    """
    (tmp_path / "doc_sentinel.toml").write_text(f'allowed_fence_languages = ["{entry}"]\n', encoding="utf-8")
    assert load_config(tmp_path).allowed_fence_languages == (entry,)


@pytest.mark.parametrize("value", ['["../outside.md"]', '["/abs/index.md"]', r'["a\\b.md"]'])
def test_navigation_index_outside_root_raises(tmp_path: Path, value: str):
    """
    [Unit] config: verifies navigation index outside root raises.

    Scenario:
        Given a TOML file with a navigation path that escapes the scan root
        When load_config validates the option
        Then a ConfigError naming the navigation option is raised.

    Boundaries:
        - Focus: root-containment validation for path lists
        - Fixtures/params: tmp_path, value (parametrized, 3 cases)
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the raised error message
        - The _is_within_root and _require_root_path_list helpers
        - Recent changes to _ROOT_PATH_LIST_OPTIONS
    """
    (tmp_path / "doc_sentinel.toml").write_text(f"navigation_indexes = {value}\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="navigation_indexes"):
        load_config(tmp_path)


def test_deprecated_references_file_outside_root_raises(tmp_path: Path):
    """
    [Unit] config: verifies deprecated references file outside root raises.

    Scenario:
        Given a TOML file whose deprecated mapping path escapes the scan root
        When load_config validates the option
        Then a ConfigError about staying within the scan root is raised.

    Boundaries:
        - Focus: root-containment validation for a single path option
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the raised error message
        - The deprecated_references_file branch in _load_extra_options
        - Recent changes to _is_within_root
    """
    (tmp_path / "doc_sentinel.toml").write_text('deprecated_references_file = "../secrets.toml"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="deprecated_references_file must stay within the scan root"):
        load_config(tmp_path)


def test_document_id_field_must_be_nonempty(tmp_path: Path):
    """
    [Unit] config: verifies document id field must be nonempty.

    Scenario:
        Given a TOML file with an empty document_id_field
        When load_config validates the option
        Then a ConfigError about a nonempty string is raised.

    Boundaries:
        - Focus: nonempty-string validation
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the raised error message
        - The document_id_field branch in _load_extra_options
        - Recent changes to nonempty-string validation
    """
    (tmp_path / "doc_sentinel.toml").write_text('document_id_field = ""\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="document_id_field must be a nonempty string"):
        load_config(tmp_path)


def test_document_id_field_must_be_a_simple_key_name(tmp_path: Path):
    """
    [Unit] config: verifies document id field must be a simple identifier-like key name.

    Scenario:
        Given a TOML file whose document_id_field contains a space (not a simple key name)
        When load_config validates the option
        Then a ConfigError about a simple key name is raised, while a plain identifier-like value
            such as "slug" is accepted.

    Boundaries:
        - Focus: identifier-like, bounded validation of document_id_field
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - The _DOCUMENT_ID_FIELD_PATTERN check in _load_extra_options
        - Whether a valid custom field name still loads
    """
    (tmp_path / "doc_sentinel.toml").write_text('document_id_field = "not a key"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="document_id_field must be a simple key name"):
        load_config(tmp_path)

    (tmp_path / "doc_sentinel.toml").write_text('document_id_field = "slug"\n', encoding="utf-8")
    assert load_config(tmp_path).document_id_field == "slug"


def test_unknown_policy_key_still_rejected(tmp_path: Path):
    """
    [Unit] config: verifies unknown policy key still rejected.

    Scenario:
        Given a TOML file with a mistyped policy option name
        When load_config validates known options
        Then a ConfigError listing the unknown option is raised.

    Boundaries:
        - Focus: strict unknown-key validation
        - Fixtures/params: tmp_path
        - Scope: assertions and setup in this test case only

    On failure, first check:
        - Assertion details tied to the raised error message
        - The _CONFIG_OPTIONS allowlist and _load_toml_table
        - Recent changes to the known-options set
    """
    (tmp_path / "doc_sentinel.toml").write_text("navigation_index = []\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Unknown config options: navigation_index"):
        load_config(tmp_path)
