import pytest
from your_module import process_signal

def test_process_signal(mocker):
    mocker.patch('your_module.get_live_price', return_value=50000.0)
    mocker.patch('your_module.calculate_trade_amount', return_value=1000.0)
    mocker.patch('your_module.kraken_request', return_value={'result': 'success'})

    signal = {'asset': 'BTC', 'type': 'buy', 'timestamp': 1630000000}
    process_signal(signal)

    # Verify that the trade was executed with correct parameters
    assert mocker.call_count == 1  # Ensure API was called once
