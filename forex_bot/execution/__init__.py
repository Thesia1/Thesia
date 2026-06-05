"""Execution provider adapters.

Execution providers are separate from market-data providers. A provider in this
package may eventually place or reconcile orders, but scaffolds must fail closed
until the full execution safety path exists.
"""
