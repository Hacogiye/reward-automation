import pytest

from rewards_bot.core import security


@pytest.mark.parametrize("raw, want", [
    ("", ""),
    (None, ""),
    ("1.2.3.4:8080", "http://1.2.3.4:8080"),
    (" SOCKS5://proxy.example.com:1080/ ", "socks5://proxy.example.com:1080"),
    ("https://[2001:db8::1]:443", "https://[2001:db8::1]:443"),
])
def test_validate_proxy_ok(raw, want):
    assert security.validate_proxy(raw) == want


@pytest.mark.parametrize("raw", [
    "ftp://1.2.3.4:21",             # scheme lạ
    "http://user:pass@1.2.3.4:80",  # có mật khẩu
    "1.2.3.4",                      # thiếu cổng
    "1.2.3.4:99999",
    "http://a b:80",
    "http://1.2.3.4:80;direct://",  # chèn thêm luật proxy
    "http://x:80 --remote-debugging-address=0.0.0.0",
])
def test_validate_proxy_rejects(raw):
    with pytest.raises(ValueError):
        security.validate_proxy(raw)


def test_browser_args_with_own_proxy_replaces_no_proxy():
    args = security.browser_args({"bypass_proxy": True}, "socks5://1.2.3.4:1080")
    assert "--proxy-server=socks5://1.2.3.4:1080" in args
    assert "--no-proxy-server" not in args
    assert "--force-webrtc-ip-handling-policy=disable_non_proxied_udp" in args


def test_browser_args_without_proxy_unchanged():
    assert security.browser_args({"bypass_proxy": True}) == ["--no-proxy-server"]
    assert security.browser_args({"bypass_proxy": False}) == []
