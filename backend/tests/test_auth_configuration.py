import asyncio
import hashlib
import hmac
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import pytest
from starlette.requests import Request

from app.config import ProviderConfig, Settings
from app.providers import FacebookProvider


def test_toml_configuration_and_environment_precedence(tmp_path, monkeypatch):
    config = tmp_path / 'tracker.toml'
    config.write_text('''password_enabled = false
oidc_name = "From TOML"
[[providers]]
id = "work"
name = "Work SSO"
issuer = "https://identity.example.com"
client_id = "tracker"
client_secret_env = "WORK_CLIENT_SECRET"
''')
    monkeypatch.setenv('TRACKER_CONFIG', str(config))
    monkeypatch.setenv('WORK_CLIENT_SECRET', 'test-client-secret')
    settings = Settings(_env_file=None)
    assert settings.oidc_name == 'From TOML'
    assert settings.configured_providers()[0].client_secret == 'test-client-secret'
    monkeypatch.setenv('OIDC_NAME', 'From environment')
    assert Settings(_env_file=None).oidc_name == 'From environment'
    monkeypatch.delenv('TRACKER_CONFIG')
    dotenv = tmp_path / '.env'
    dotenv.write_text(f'TRACKER_CONFIG={config}\n')
    assert Settings(_env_file=dotenv).configured_providers()[0].id == 'work'


def test_configuration_rejects_duplicate_ids_and_incomplete_local_mail():
    provider = ProviderConfig(id='work', name='Work', issuer='https://identity.example.com', client_id='tracker')
    with pytest.raises(ValueError):
        Settings(_env_file=None, password_enabled=False, providers=[provider, provider])
    with pytest.raises(ValueError):
        Settings(_env_file=None, password_enabled=True, smtp_host='', smtp_from='', mail_encryption_key='')
    with pytest.raises(ValueError):
        ProviderConfig(id='password', name='Reserved', issuer='https://identity.example.com', client_id='tracker')


@pytest.mark.parametrize('failure', [None, 'state', 'missing_id', 'graph_error'])
def test_facebook_oauth_state_identity_and_app_binding(failure):
    async def scenario():
        settings = Settings(_env_file=None, password_enabled=False, api_base_url='https://tracker.example.com')
        config = ProviderConfig(id='facebook', name='Facebook', type='facebook', client_id='test-app', client_secret='test-secret')
        provider = FacebookProvider(settings, config)
        def transport(request):
            if request.url.path.endswith('/oauth/access_token'):
                params = parse_qs(request.content.decode())
                assert params['client_id'] == ['test-app'] and params['client_secret'] == ['test-secret']
                assert params['redirect_uri'] == ['https://tracker.example.com/api/v1/auth/facebook/callback']
                return httpx.Response(200, json={'access_token': 'test-access', 'token_type': 'Bearer'})
            assert request.url.path.endswith('/me')
            assert request.url.params['appsecret_proof'] == hmac.new(b'test-secret', b'test-access', hashlib.sha256).hexdigest()
            if failure == 'graph_error':
                return httpx.Response(400, json={'error': 'invalid'})
            return httpx.Response(200, json={'name': 'Facebook person', **({} if failure == 'missing_id' else {'id': 'app-scoped-user'})})
        provider.client.client_kwargs['transport'] = httpx.MockTransport(transport)
        session = {}
        def request(query=''):
            return Request({'type': 'http', 'method': 'GET', 'scheme': 'https', 'path': '/callback',
                            'query_string': query.encode(), 'headers': [], 'server': ('tracker.example.com', 443), 'session': session})
        redirect = await provider.authorize(request())
        params = parse_qs(urlparse(redirect.headers['location']).query)
        state = 'forged' if failure == 'state' else params['state'][0]
        callback = request(urlencode({'code': 'test-code', 'state': state}))
        if failure:
            with pytest.raises(Exception):
                await provider.identity(callback)
        else:
            identity = await provider.identity(callback)
            assert identity.issuer == 'https://www.facebook.com/test-app'
            assert identity.subject == 'app-scoped-user' and identity.email == ''
    asyncio.run(scenario())
