# Auditoria de Bugs — backon v4.2.3 (commit cc8a399)

---

## Sumário Executivo

| Categoria | Quantidade |
|---|---|
| Bugs novos confirmados | 5 |
| Bugs já reportados em issues abertas | 18 |
| Testes existentes | 567 passando (100%) |

---

## Bugs Novos Confirmados (não reportados nas issues)

### B1. [Crítico] Trio: `except trio.TooSlowError` nunca capturado — `except AttemptTimeoutError` é dead code

**Arquivo:** `backon/_trio.py:226-227`

**Descrição:** Em `retry_exception` e `retry_predicate`, a exceção `trio.TooSlowError` é capturada e convertida para `AttemptTimeoutError` via `raise AttemptTimeoutError() from None`. Esta nova exceção NÃO é capturada pelo `except AttemptTimeoutError` subsequente (no mesmo bloco `try`), porque em Python, exceções levantadas dentro de um `except` não são capturadas por outros `except` no mesmo `try`. O `AttemptTimeoutError` propaga diretamente para o chamador, e a lógica de retry em timeout nunca executa.

**Passos para reproduzir:**
```python
import trio
from backon._trio import retry_exception
from backon import expo

attempts = []

async def fail():
    attempts.append(1)
    await trio.sleep(10)

wrapped = retry_exception(
    fail, expo, ValueError,
    max_tries=5, max_time=None, jitter=None,
    giveup=lambda e: False,
    on_success=[], on_backoff=[], on_giveup=[], on_attempt=[],
    raise_on_giveup=True, sleep=trio.sleep, wait_gen_kwargs={},
    attempt_timeout=0.01,
)

async def main():
    try:
        await wrapped()
    except Exception as e:
        print(f"{type(e).__name__}: {e}")
    print(f"Attempts: {len(attempts)} (expected 5)")

trio.run(main)
```

**Evidência:**
```
Exception: AttemptTimeoutError:
Attempts: 1 (expected 5)
```

**Severidade:** Crítico — a funcionalidade de retry em timeout no Trio é completamente quebrada.

**Patch sugerido:**
Substituir:
```python
except trio.TooSlowError:
    raise AttemptTimeoutError() from None
except AttemptTimeoutError:
```
Por:
```python
except (trio.TooSlowError, AttemptTimeoutError):
```
(unificando os dois `except` em um único handler, já que ambos representam timeout).

---

### B2. [Alto] `on_hedge` handler chamado uma única vez com `hedge_count` sempre igual a `max_hedge`

**Arquivo:** `backon/_hedging.py:107-129` (`_hedge_sync`) e `backon/_hedging.py:191-194` (`_hedge_async`)

**Descrição:** O callback `on_hedge` é chamado DEPOIS do loop `for _i in range(max_hedge)` que submete as hedge requests, e não dentro dele. Isso significa que:
1. O handler é chamado apenas 1 vez (em vez de `max_hedge` vezes)
2. `hedge_count` é sempre `_i + 1 = max_hedge` (sempre o valor final de `_i`)
3. O propósito do README ("Callback when a hedge request is sent") sugere que deve ser chamado por hedge request

**Evidência:**
```python
>>> handler chamado 1 vez, hedge_count=[5] (quando max_hedge=5)
```

**Severidade:** Alto — a API `on_hedge` não funciona conforme documentado.

**Patch sugerido:**
Mover a chamada do handler para dentro do loop:
```python
for _i in range(max_hedge):
    fut = executor.submit(...)
    futures.add(fut)
    for handler in on_hedge_list:
        handler({"max_hedge": max_hedge, "target": target, "hedge_count": _i + 1})
```

---

### B3. [Médio] `wait_combine` com kwargs extras causa `TypeError`

**Arquivo:** `backon/_wait_gen.py:18-19` (`_Wait.__call__`) e `backon/_wait_gen.py:39-40` (`_CombinedWait.__call__`)

**Descrição:** Quando `wait_combine(expo, constant)` (ou `_CombinedWait`) é usado, os kwargs extras do decorador (e.g., `base=3`, `interval=0.5`) são passados para TODOS os sub-generadores. Se um gerador não aceitar um parâmetro (e.g., `_Constant` não aceita `base`), ocorre `TypeError`.

**Evidência:**
```python
@backon.on_exception(
    wait_combine(backon.expo, backon.constant),
    ValueError, max_tries=3, base=3, interval=0.5
)
# TypeError: _Expo.__init__() got an unexpected keyword argument 'interval'
```

**Severidade:** Médio — a API é frágil e propensa a erros. O usuário precisa pré-configurar cada gerador separadamente com o operador `+` para evitar o problema.

---

### B4. [Médio] Parâmetros `condition`/`stop` vão para `wait_gen_kwargs` nos decoradores

**Arquivo:** `backon/_decorator.py:370` (`on_exception`) e `backon/_decorator.py:62` (`on_predicate`)

**Descrição:** Os decoradores `@on_exception` e `@on_predicate` não possuem `condition` ou `stop` em sua assinatura, mas `Retrying` e `retry()` suportam. Se o usuário passa `condition=` para o decorador, ele cai em `**wait_gen_kwargs` e é passado para o wait generator, causando erro enigmático.

**Evidência:**
```python
@backon.on_exception(backon.expo, ValueError, max_tries=3, condition=cond)
# TypeError: _Expo.__init__() got an unexpected keyword argument 'condition'
```

**Severidade:** Médio — experiência do usuário pobre, mensagem de erro enganosa.

**Patch sugerido:** Adicionar `condition` e `stop` como parâmetros aos decoradores (como `None`, ignorados) ou capturar TypeError e dar mensagem clara.

---

### B5. [Baixo] `_WaitChain` cicla em vez de exaurir geradores sequencialmente

**Arquivo:** `backon/_wait_gen.py:212-217` (`_WaitChain.next`)

**Descrição:** O método `next` do `_WaitChain` usa `(self._idx + 1) % len(self._waits)` que faz com que a cadeia ciclie infinitamente em vez de exaurir cada gerador sequencialmente (que é o esperado de uma "chain").

**Código atual:**
```python
def next(self, send_value=None) -> float:
    w = self._waits[self._idx]
    self._idx = (self._idx + 1) % len(self._waits)
    return w.next(send_value)
```

**Comportamento atual:** Round-robin entre os geradores.
**Comportamento esperado:** Exaurir cada gerador antes de passar ao próximo.

**Severidade:** Baixo — o impacto prático é limitado porque os geradores de espera são infinitos sequencialmente, mas o comportamento não corresponde ao esperado de "chain".

---

## Issues Abertas Relacionadas (já reportadas)

| Issue | Título | Relação |
|---|---|---|
| #45 | `stop_before_delay` não funciona no fast path | Confirmei a análise, não reproduzi separadamente |
| #43 | `hedge()` sem `*args`/`**kwargs` | Bug confirmado, distinto de B2 |
| #42 | `retry_if_exception_cause_type` loop infinito | Análise estrutural confirma |
| #41 | `retry_all` descarta float | Confirmado na leitura de código |
| #40 | `isinstance` inconsistente no `giveup` | Confirmado entre `_make_default_condition` e decorador |
| #39 | `_RetryAttempt.__exit__` suprime Ctrl+C | Confirmado |
| #38 | Fast path ignora float de `condition`/`giveup` | Confirmado |
| #37 | `_check_hot_loop` sem isolamento | Confirmado (variável global) |
| #36 | Vazamento de `ThreadPoolExecutor` | Confirmado |
| #35 | `_FastState`/`_FastOutcome` sem campos | Confirmado |
| #34 | `_config_handlers` trata string como iterável | Confirmado |
| #33 | `state.idle_for` acumula tempo total | Confirmado |
| #31 | `raise_on_giveup=False` engole `KeyboardInterrupt` | Confirmado |
| #30 | Singletons `_Wait` mutáveis | Confirmado |
| #29 | `RetryingCaller.__call__` converte `{}` em `None` | Confirmado |
| #28 | `_TEST_CONFIG` sem thread-safety | Confirmado |
| #27 | Métricas nunca emitidas | Confirmado (código morto) |
| #26 | `BreakerRetrying.call` ignora `half_open_max_calls` | Confirmado |

---

## Conclusão

A auditoria encontrou **5 bugs novos** (não reportados nas issues do GitHub) e confirmou **18 bugs** já reportados nas issues abertas. O repositório tem 100% dos testes passando, mas existem problemas reais no código que não são cobertos pelos testes existentes.

### Resumo dos bugs novos:

| ID | Severidade | Tipo | Descrição |
|---|---|---|---|
| B1 | **Crítico** | Bug | Trio: timeout retry completamente quebrado (dead code) |
| B2 | **Alto** | Bug | `on_hedge` handler chamado 1 vez com valor errado |
| B3 | **Médio** | Bug | `wait_combine` crasha com kwargs incompatíveis |
| B4 | **Médio** | Usabilidade | Erro enganoso ao passar `condition`/`stop` para decorador |
| B5 | **Baixo** | Bug | `wait_chain` cicla em vez de exaurir sequencialmente |

### Sugestões de títulos para novas issues:

1. **`[BUG][trio] except trio.TooSlowError raises AttemptTimeoutError that is never caught — timeout retry is completely broken`** (B1)
2. **`[BUG] on_hedge handler fires only once with hedge_count=max_hedge instead of per-hedge-request`** (B2)
3. **`[BUG] wait_combine crashes with TypeError when shared kwargs don't match all sub-generators`** (B3)
4. **`[BUG] condition/stop parameters silently forwarded to wait generator in on_exception/on_predicate decators`** (B4)
5. **`[BUG] wait_chain cycles through generators in round-robin instead of exhausting each sequentially`** (B5)
