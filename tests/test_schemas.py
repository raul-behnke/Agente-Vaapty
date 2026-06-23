from vaapty_agent.agent.schemas import (
    StateUpdate,
    compute_missing,
    is_in_radius,
    is_qualified,
    merge_into_state,
)


def test_merge_fill_only_and_tristate():
    state = {"collected": {"nome": "Ana"}, "counters": {}}
    upd = StateUpdate.model_validate(
        {"collected": {"nome": "OUTRO", "veiculo_modelo": "Onix", "quer_vender": False}}
    )
    merge_into_state(state, upd)
    assert state["collected"]["nome"] == "Ana"           # fill-only não regride
    assert state["collected"]["veiculo_modelo"] == "Onix"
    assert state["collected"]["quer_vender"] is False     # tri-state aceita False


def test_compute_missing_priority_order():
    missing = compute_missing({"nome": "Ana"})
    assert missing[0] == "localizacao"


def test_radius():
    assert is_in_radius("Guarulhos")
    assert is_in_radius("guarulhos - sp")
    assert not is_in_radius("Manaus")
    assert not is_in_radius(None)


def test_qualified_requires_radius_and_car():
    s = {"collected": {"localizacao": "Guarulhos", "veiculo_modelo": "Onix"}}
    assert is_qualified(s)
    s2 = {"collected": {"localizacao": "Manaus", "veiculo_modelo": "Onix"}}
    assert not is_qualified(s2)
    s3 = {"collected": {"localizacao": "Guarulhos"}}
    assert not is_qualified(s3)
    s4 = {"collected": {"localizacao": "Guarulhos", "veiculo_modelo": "Onix", "quer_vender": False}}
    assert not is_qualified(s4)
