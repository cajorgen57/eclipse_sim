from eclipse_ai.models.economy import Economy


def test_max_additional_actions_basic():
    # bank 6, income 4, fixed upkeep 3, 0 discs => budget over action track = 7
    econ = Economy(orange_bank=6, orange_income=4, orange_upkeep_fixed=3, action_slots_filled=0)
    # With 7 budget we can afford up to the slot where cumulative upkeep reaches 7 (k = 6)
    assert econ.max_additional_actions() == 6


def test_prefix_affordable_progression():
    econ = Economy(orange_bank=3, orange_income=3, orange_upkeep_fixed=0, action_slots_filled=1)
    # base cum at 1 = 1; budget=6; remaining=5
    # k=2 need=1 -> ok, k=3 need=2 -> ok, k=4 need=3 -> ok, k=5 need=4 -> ok, k=6 need=6 -> fails
    assert econ.prefix_affordable(4) is True
    assert econ.prefix_affordable(5) is False
