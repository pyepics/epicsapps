@echo off

set prefix=%USERPROFILE%\epicsapps

set condaurl=https://github.com/conda-forsge/miniforge/releases/latest/download
set condafile=Miniforge3-Windows-x86_64.exe

if not exist %~dp0%condafile% (
    echo ## Downloading Miniconda from https://repo.anaconda.com/miniconda/, please wait...
    bitsadmin /transfer /download /priority normal %condaurl%/%condafile% %~dp0%condafile%
)

echo ## Installing miniconda environment to %prefix%, please wait...

%~dp0%condafile% /InstallationType=JustMe /RegisterPython=0 /S /D=%prefix%

echo ## basic conda installed, running updates

set PATH=%prefix%;%prefix%\bin;%prefix%\condabin;%prefix%\Scripts;%PATH%


echo ## Installing basic python scipy packages
call %prefix%\Scripts\conda install -yc conda-forge python>=3.13.1 numpy>=2.0.0 scipy matplotlib h5py wxpython>=4.2.1

echo ## Installing xraylarch, epicsapps and dependencies from PyPI
call %prefix%\Scripts\pip install xraylarch[larix,epics]
call %prefix%\Scripts\pip install epicsapps
echo ## Creating desktop shortcuts
call %prefix%\Scripts\epicsapps -m

echo ## Installation to %prefix% done!
echo ## Applications can be run from the Epics Apps folder on your Desktop.
echo ##
echo ## To use from a terminal or command-line, you may want to add
echo ##     %prefix%;%prefix%\bin;%prefix%\condabin;%prefix%\Scripts
echo ## to your PATH environment, such as
echo ##     set PATH=%prefix%;%prefix%\bin;%prefix%\condabin;%prefix%\Scripts;%PATH%
