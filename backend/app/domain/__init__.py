"""
Pure-logic domain modules for the automation catalog: manifest/workspace
validation and packaging. Deliberately free of DB/network dependencies so they
can be unit-tested in isolation and reused identically by both the GitHub
import path and the manual ZIP upload path.
"""
