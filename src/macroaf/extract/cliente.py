"""Cliente HTTP das extrações: timeout explícito e retentativas com espera exponencial."""

from __future__ import annotations

import time

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

TIMEOUT = httpx.Timeout(60.0, connect=15.0)
TENTATIVAS = 5
USER_AGENT = "macroaf (https://github.com/marcelo7bastos/macroeconomia-agricultura-familiar)"


class ErroFonte(RuntimeError):
    """A fonte respondeu algo que não dá para usar (erro definitivo, sem retentativa)."""


def _vale_tentar_de_novo(erro: BaseException) -> bool:
    if isinstance(erro, httpx.TransportError):
        return True
    if isinstance(erro, httpx.HTTPStatusError):
        status = erro.response.status_code
        return status == 429 or status >= 500
    return False


class Cliente:
    """Envolve `httpx.Client` com retentativas e uma pausa mínima entre requisições."""

    def __init__(
        self,
        cliente: httpx.Client | None = None,
        pausa: float = 0.5,
        espera_minima: float = 2.0,
        espera_maxima: float = 60.0,
    ) -> None:
        self._cliente = cliente or httpx.Client(
            timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}, follow_redirects=True
        )
        self._pausa = pausa
        self._ultima = 0.0
        self.obter = retry(
            retry=retry_if_exception(_vale_tentar_de_novo),
            wait=wait_exponential(multiplier=espera_minima, max=espera_maxima),
            stop=stop_after_attempt(TENTATIVAS),
            reraise=True,
        )(self._obter)

    def _obter(self, url: str) -> bytes:
        espera = self._pausa - (time.monotonic() - self._ultima)
        if espera > 0:
            time.sleep(espera)
        self._ultima = time.monotonic()
        resposta = self._cliente.get(url)
        if resposta.status_code == 400:
            # A API SIDRA devolve 400 com a explicação no corpo (ex.: limite de valores excedido).
            raise ErroFonte(f"{url}: {resposta.text[:300]}")
        resposta.raise_for_status()
        return resposta.content

    def fechar(self) -> None:
        self._cliente.close()

    def __enter__(self) -> Cliente:
        return self

    def __exit__(self, *_: object) -> None:
        self.fechar()
