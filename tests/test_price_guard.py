from vaapty_agent.tools.price_guard import DEFLECTION, has_price, scrub_bubbles


def test_detects_currency():
    assert has_price("fica R$ 35.000")
    assert has_price("uns 30 mil")
    assert has_price("por 25k")
    assert has_price("comissão de 5%")
    assert has_price("vale em torno de tanto")


def test_ignores_clean_text():
    assert not has_price("Qual o modelo do seu carro?")
    assert not has_price("Você é de Guarulhos?")
    # ano não deve disparar
    assert not has_price("é 2015")


def test_scrub_replaces_price_bubble_with_deflection():
    out = scrub_bubbles(["Seu carro vale R$ 40.000", "posso seguir?"])
    assert DEFLECTION in out
    assert all("R$" not in b for b in out)
