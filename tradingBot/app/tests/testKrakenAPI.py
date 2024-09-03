import pytest
from your_module import get_live_price, get_account_balance

def test_get_live_price(mocker):
    mocker.patch('your_module.kraken_request', return_value={'result': {'BTCUSD': {'c': ['50000.0']}}})
    price = get_live_price('BTC')
    assert price == 50000.0

def test_get_account_balance(mocker):
    mocker.patch('your_module.kraken_request', return_value={'result': {'ZUSD': '10000.0'}})
    balance = get_account_balance()
    assert balance == 10000.0
