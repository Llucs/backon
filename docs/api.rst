API Reference
=============

Decorators
----------

.. autofunction:: backon.on_exception
.. autofunction:: backon.on_predicate
.. autofunction:: backon.on_hedge

Functional API
--------------

.. autofunction:: backon.retry
.. autofunction:: backon.hedge
.. autofunction:: backon.sleep_using_event

Context Manager
---------------

.. autoclass:: backon.Retrying
   :members:
.. autoclass:: backon.AsyncRetryingCaller
   :members:
.. autoclass:: backon.RetryingCaller
   :members:

Circuit Breaker
---------------

.. autoclass:: backon.CircuitBreaker
   :members:
.. autoclass:: backon.BreakerRetrying
   :members:
.. autoexception:: backon.CircuitOpenError

Hedging
-------

.. autoclass:: backon.HedgingRetrying
   :members:
.. autoexception:: backon.HedgeError

Wait Generators
---------------

.. autofunction:: backon.expo
.. autofunction:: backon.constant
.. autofunction:: backon.fibo
.. autofunction:: backon.runtime
.. autofunction:: backon.decay
.. autofunction:: backon.wait_random_exponential
.. autofunction:: backon.wait_incrementing
.. autofunction:: backon.wait_chain
.. autofunction:: backon.wait_combine
.. autofunction:: backon.wait_exception
.. autofunction:: backon.wait_random
.. autofunction:: backon.wait_exponential_jitter
.. autofunction:: backon.wait_none

Jitter
------

.. autofunction:: backon.full_jitter
.. autofunction:: backon.random_jitter

Stop Conditions
---------------

.. autoclass:: backon.Stop
.. autofunction:: backon.stop_after_attempt
.. autofunction:: backon.stop_after_delay
.. autofunction:: backon.stop_before_delay
.. autofunction:: backon.stop_all
.. autofunction:: backon.stop_any
.. autofunction:: backon.stop_never
.. autofunction:: backon.stop_when_event_set

Retry Conditions
----------------

.. autoclass:: backon.RetryCondition
.. autofunction:: backon.retry_if_exception_type
.. autofunction:: backon.retry_if_exception
.. autofunction:: backon.retry_if_exception_message
.. autofunction:: backon.retry_if_result
.. autofunction:: backon.retry_if_not_result
.. autofunction:: backon.retry_if_exception_cause_type
.. autofunction:: backon.retry_if_not_exception_type
.. autofunction:: backon.retry_if_not_exception_message
.. autofunction:: backon.retry_unless_exception_type
.. autofunction:: backon.retry_all
.. autofunction:: backon.retry_any
.. autofunction:: backon.retry_always
.. autofunction:: backon.retry_never

Rate Limiter
------------

.. autoclass:: backon.RateLimiter
   :members:
.. autoexception:: backon.RateLimitError

State & Exceptions
------------------

.. autoclass:: backon.RetryState
   :members:
.. autoclass:: backon.RetryCallState
   :members:
.. autoexception:: backon.RetryError
.. autoexception:: backon.AttemptTimeoutError
.. autoexception:: backon.TryAgain

Context Inspection
------------------

.. autofunction:: backon.is_retrying
.. autofunction:: backon.get_attempt_number

Global Toggle
-------------

.. autofunction:: backon.disable
.. autofunction:: backon.enable

Testing Utilities
-----------------

.. autoclass:: backon.test_config
.. autofunction:: backon.disable_retries
.. autofunction:: backon.enable_retries
.. autofunction:: backon.limit_retries
.. autofunction:: backon.remove_backoff
.. autofunction:: backon.assert_retried
.. autofunction:: backon.assert_not_retried

Metrics
-------

.. autoclass:: backon.MetricsCollector
.. autoclass:: backon.PrometheusMetrics
.. autoclass:: backon.OTelMetrics
.. autoclass:: backon.StructlogMetrics
.. autofunction:: backon.set_metrics_collector
.. autofunction:: backon.get_metrics_collector

Types
-----

.. autoclass:: backon.Details
