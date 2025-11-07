"""
InstaWell Dash App - Interactive web interface for DSF data analysis.

A fully-featured Dash application that uses the tested InstaWell pipeline.
"""

from .app import create_app

__all__ = ["create_app"]
