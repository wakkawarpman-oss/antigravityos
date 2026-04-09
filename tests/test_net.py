import pytest
import urllib.error
from unittest.mock import patch, MagicMock

@patch("net.REQUIRE_PROXY", False)
@patch("net.urllib.request.build_opener")
def test_proxy_aware_request_success(mock_build_opener):
    from net import proxy_aware_request
    
    # Mock the opener and the context manager returned by it
    mock_opener = MagicMock()
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.headers.items.return_value = [("Content-Type", "application/json")]
    mock_response.read.return_value = b'{"status": "ok"}'
    
    # Setup context manager mock
    mock_opener.open.return_value.__enter__.return_value = mock_response
    mock_build_opener.return_value = mock_opener

    status, headers, body = proxy_aware_request("http://example.com")
    assert status == 200
    assert "Content-Type" in headers
    assert body == '{"status": "ok"}'

@patch("net.REQUIRE_PROXY", False)
@patch("net.urllib.request.build_opener")
@patch("net.time.sleep")
def test_proxy_aware_request_retry_on_5xx(mock_sleep, mock_build_opener):
    from net import proxy_aware_request
    
    mock_opener = MagicMock()
    
    # Simulate HTTP 502 twice, then success for 3rd attempt
    error_response = urllib.error.HTTPError("http://example.com", 502, "Bad Gateway", {}, None)
    
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.headers.items.return_value = []
    mock_response.read.return_value = b"success"
    
    mock_opener.open.side_effect = [
        error_response,
        error_response,
        MagicMock(__enter__=MagicMock(return_value=mock_response))
    ]
    mock_build_opener.return_value = mock_opener

    status, headers, body = proxy_aware_request("http://example.com")
    assert status == 200
    assert body == "success"
    assert mock_opener.open.call_count == 3
    assert mock_sleep.call_count == 2

@patch("net.REQUIRE_PROXY", False)
@patch("net.urllib.request.build_opener")
@patch("net.time.sleep")
def test_proxy_aware_request_no_retry_on_4xx(mock_sleep, mock_build_opener):
    from net import proxy_aware_request
    
    mock_opener = MagicMock()
    
    # Simulate HTTP 404 (Not Found)
    error_response = urllib.error.HTTPError("http://example.com", 404, "Not Found", {}, None)
    mock_opener.open.side_effect = error_response
    mock_build_opener.return_value = mock_opener

    status, headers, body = proxy_aware_request("http://example.com")
    assert status == 404
    assert mock_opener.open.call_count == 1  # Should not retry 404
    assert mock_sleep.call_count == 0

@patch("net.REQUIRE_PROXY", True)
def test_proxy_aware_request_enforces_proxy():
    from net import proxy_aware_request
    
    with pytest.raises(RuntimeError, match="no proxy provided"):
        proxy_aware_request("http://example.com", proxy=None)
