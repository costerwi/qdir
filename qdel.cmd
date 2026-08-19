@echo off
rem Windows script to run qdir
rem This script and qdir should be located together in a PATH directory

rem Run using system installed python3
python3 "%~dp0\qdir.py" -d %*
