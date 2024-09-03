import pytest
from your_module import calculate_trade_amount

def test_calculate_trade_amount(mocker):
    mocker.patch('your_module.get_account_balance', return_value=10000.0)
    trade_amount = calculate_trade_amount({})
    assert trade_amount == 1000.0  # 10% of 10000
