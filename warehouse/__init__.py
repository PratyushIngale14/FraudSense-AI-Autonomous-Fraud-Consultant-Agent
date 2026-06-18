"""Warehouse Assurance module for FraudSense.

Reads a company's actual data-warehouse schema and reports which fraud
scenarios their real data can and cannot detect — grounded in the data,
not interviews.

Architecture: a fixed canonical ontology + a fixed pattern library + an AI
layer that maps any messy warehouse schema onto the canonical model. The
same patterns then run on any warehouse with zero code changes.
"""
