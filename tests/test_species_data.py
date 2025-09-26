from eclipse_ai import all_species, get_species, SpeciesConfig


def test_loads_species_registry() -> None:
    registry = all_species()
    assert "terrans" in registry
    assert "octantis_autonomy" in registry
    assert isinstance(registry["terrans"], SpeciesConfig)


def test_octantis_evolution_note_present() -> None:
    octantis = get_species("octantis_autonomy")
    notes = " ".join(octantis.get("notes", []))
    assert "Evolution" in notes
    assert "Colony Ships" in notes


def test_rho_indi_trade_rate_override() -> None:
    rho = get_species("rho_indi")
    trade_rate = rho.trade_rate
    assert trade_rate == {"goods": 3, "resources": 2}


def test_two_player_balance_note() -> None:
    planta_notes = " ".join(get_species("planta").get("notes", []))
    draco_notes = " ".join(get_species("draco").get("notes", []))
    assert "two-player" in planta_notes.lower()
    assert "two-player" in draco_notes.lower()
