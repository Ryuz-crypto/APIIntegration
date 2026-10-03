from ec_mcp import ssh_ecos


def test_keyboard_interactive_handler_replies_to_all_prompts():
    handler = ssh_ecos._keyboard_interactive_handler("secret")
    assert handler("title", "instructions", [("Password:", False), ("OTP:", False)]) == ["secret", "secret"]


def test_keyboard_interactive_connection_uses_paramiko(monkeypatch):
    class FakeChannel:
        def get_pty(self, **_kwargs):
            return None

        def invoke_shell(self):
            return None

        def recv_ready(self):
            return False

        def close(self):
            return None

    class FakeTransport:
        last_auth = None

        def __init__(self, _sock):
            self.channel = FakeChannel()

        def start_client(self, timeout):
            assert timeout == 30

        def auth_interactive(self, username, handler):
            self.__class__.last_auth = (username, handler("", "", [("Password:", False)]))

        def is_authenticated(self):
            return True

        def open_session(self):
            return self.channel

        def close(self):
            return None

    class FakeParamiko:
        Transport = FakeTransport

    monkeypatch.setattr(ssh_ecos.socket, "create_connection", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(ssh_ecos, "paramiko", FakeParamiko)

    credential = "secret"
    session = ssh_ecos.ApplianceSession(
        host="192.0.2.10",
        username="admin",
        password=credential,
        auth_method="keyboard-interactive",
    )
    try:
        assert FakeTransport.last_auth == ("admin", ["secret"])
    finally:
        session.close()


def test_invalid_ssh_auth_method_is_rejected():
    try:
        credential = "secret"
        ssh_ecos.ApplianceSession(
            host="192.0.2.10",
            username="admin",
            password=credential,
            auth_method="unsupported",
        )
        raise AssertionError("expected invalid auth method to be rejected")
    except ValueError as error:
        assert "EC_SSH_AUTH_METHOD" in str(error)

def test_keyboard_interactive_handler_accepts_confirmation_prompt():
    handler = ssh_ecos._keyboard_interactive_handler("secret")
    assert handler("title", "instructions", [("Accept certificate? (yes/no)", False)]) == ["yes"]
