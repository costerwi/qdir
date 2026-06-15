@echo off
rem Windows script to run qdir
rem This script and qdir should be located together in a PATH directory

rem Run in background using system installed python3
start /b python3 "%~dp0\qdir" %*
