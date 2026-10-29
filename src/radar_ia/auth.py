"""Verificação de autenticação sem solicitar geração de tokens."""
import httpx


def check_openrouter_auth(api_key: str, client=None) -> None:
    if not api_key.strip():
        raise ValueError("Configure OPENROUTER_API_KEY no .env")
    def check(session):
        response = session.get("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {api_key}"})
        if response.status_code == 401:
            raise ValueError("OpenRouter recusou a chave (401). Confira a chave de API de inferência no .env; ela pode estar incorreta, expirada ou desativada.")
        if response.status_code != 200:
            raise ValueError(f"Verificação de autenticação retornou HTTP {response.status_code}; nenhuma geração solicitada.")
    if client is not None:
        check(client)
    else:
        with httpx.Client(timeout=20, follow_redirects=False) as session:
            check(session)
