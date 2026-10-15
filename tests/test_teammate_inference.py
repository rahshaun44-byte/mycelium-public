import asyncio
import httpx
import pytest
from mcp_layer.qf_bot import teammates

@pytest.mark.parametrize('failure', ['http', 'timeout'])
def test_failure_is_reported_honestly(monkeypatch, failure):
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            if failure == 'timeout': raise httpx.ReadTimeout('test')
            return httpx.Response(404, json={'error': 'model missing'})
    monkeypatch.setattr(teammates.httpx, 'AsyncClient', Client)
    result = asyncio.run(teammates.AriaTeammate().generate_response('hello'))
    assert 'unavailable' in result.lower()
    assert 'verified' not in result.lower()
    assert 'equilibrium' not in result.lower()

def test_model_can_use_installed_configuration(monkeypatch):
    monkeypatch.setenv('QF_BOT_MODEL', 'gemma3:4b')
    assert teammates.AriaTeammate().model == 'gemma3:4b'

def test_athena_dispatch_uses_rag_answer_and_string_sources(monkeypatch):
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "mcp_layer"))
    from mcp_layer.qf_bot import orchestrator
    monkeypatch.setattr(orchestrator, 'log_memory', lambda *a: None)
    bot = orchestrator.QFBotOrchestrator()
    monkeypatch.setattr(bot.athena, 'query_vector_store', lambda *a, **k: {'answer': 'Grounded answer', 'chunks': ['guide.md'], 'sources': ['guide.md']})
    result = asyncio.run(bot._dispatch_single_bot(bot.athena, 'question'))
    assert result['response'] == 'Grounded answer'
