"""Fact-check backends: the backend-independent protocol and, later, the network clients.

``protocol.py`` holds the contract that rule ``DS302`` and every backend are written against
(ADR 0007 Contract 4, Milestone 0010 plan contract C2). Backend modules such as ``lenz.py``
(Story 03.0) do network I/O, so they live in this package rather than in ``mining/`` or
``detectors/`` (plan contract C9). A module here may import only the standard library, ``httpx``
(backend modules only), ``docsentinel.log`` and other ``docsentinel.fact_check.*`` modules, and no
module here reads the environment: an API key arrives only through a backend's constructor.

This package imports nothing: ``import docsentinel.fact_check`` never pulls in ``httpx`` or a
backend module. Import the submodule you need.
"""
