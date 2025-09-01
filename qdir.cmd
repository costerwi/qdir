@echo off
rem Windows script to run qdir
rem This script and qdir should be located together in a PATH directory

rem Uncomment the following line to use python from Abaqus >=2024
rem abaqus python %~dp0\qdir %*

rem Run using system installed python3
python3 %~dp0\qdir %*
