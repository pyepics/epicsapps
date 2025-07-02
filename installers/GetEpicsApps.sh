#!/bin/sh
##
## script to install Eoics Apps on Linux or MacOS
## using a Miniforge environment and installing
## all required packages with conda or pip

prefix=$HOME/epicsapps
larchurl='xraylarch[larix,epics]'

uname=`uname`
condaurl="https://github.com/conda-forge/miniforge/releases/latest/download"

condafile="Miniforge3-$uname-x86_64.sh"

logfile=GetEpicsApps.log

## set list of conda packages to install from conda-forge
cforge_pkgs="python>=3.13.1 numpy>=2.1.0 scipy>=1.14 matplotlib>=3.8 h5py>=3.10 wxpython>=4.2.1 "

unset CONDA_EXE CONDA_PYTHON_EXE CONDA_PREFIX PROJ_LIB

## get command line options
for opt ; do
  option=''
  case "$opt" in
    -*=*)
        optarg=`echo "$opt" | sed 's/[-_a-zA-Z0-9]*=//'`
        option=`echo "$opt" | sed 's/=.*//' | sed 's/-*//'`
        ;;
    *)
        option=`echo "$opt" | sed 's/^-*//'`
        optarg=
        ;;
  esac
  case "$option" in
    prefix)        prefix=$optarg ;;
    -h | h | -help | --help | help) cat<<EOF
Usage: GetEpicsApps.sh [options]
Options:
  --prefix=PREFIX             base directory for installation [$prefix]
EOF
    exit 0
    ;;

   *)
       echo " unknown option "  $opt
       exit 1
       ;;
  esac
done

## test for prefix already existing
if [ -d $prefix ] ; then
   echo "##Error: $prefix exists."
   exit 0
fi

echo "##############  " | tee $logfile
echo "##  This script will install Epics Apps for $uname to $prefix" | tee -a $logfile
echo "##  " | tee -a $logfile
echo "##  The following packages will be taken from conda-forge:" | tee -a $logfile
echo "##        $cforge_pkgs " | tee -a $logfile
echo "##  " | tee -a $logfile
echo "##  See GetEpicApps.log for complete log and error messages" | tee -a $logfile
echo "##############  " | tee -a $logfile


## download miniconda installer if needed
if [ ! -f $condafile ] ; then
    echo "## Downloading Miniconda installer for $uname" | tee -a $logfile
    echo "#>  /usr/bin/curl -L $condaurl/miniconda/$condafile -O " | tee -a $logfile
    /usr/bin/curl -L $condaurl/$condafile -O | tee -a $logfile
fi

# install and update miniconda
export PATH=$prefix/bin:$PATH

echo "##  Installing Miniconda for $uname to $prefix" | tee -a $logfile
echo "#>  sh ./$condafile -b -p $prefix " | tee -a $logfile
bash ./$condafile -b -p $prefix  | tee -a $logfile


echo "##  Installing packages from conda-forge"  | tee -a $logfile
echo "#> $prefix/bin/conda install -yc conda-forge $cforge_pkgs " | tee -a $logfile
$prefix/bin/conda install -y -c conda-forge $cforge_pkgs
$prefix/bin/conda list

echo "##Installing xraylarch and epicsapps from PyPI"  | tee -a $logfile
echo "#> $prefix/bin/pip install \"$larchurl\""| tee -a $logfile
$prefix/bin/pip install "$larchurl" | tee -a $logfile
echo "#> $prefix/bin/pip install epicsapps"| tee -a $logfile
$prefix/bin/pip install "epicsapps" | tee -a $logfile

## create desktop shortcuts
echo "## Creating desktop shortcuts"
$prefix/bin/epicsapps -m

echo "##############  " | tee -a $logfile
echo "##  EpicsApps Installation to $prefix done." | tee -a $logfile
echo "##  Applications can be run from the EpicsApps folder on your Desktop." | tee -a $logfile
echo "##  "| tee -a $logfile
echo "##  To use from a terminal, you may want to add:"  | tee -a $logfile
echo "        export PATH=$prefix/bin:\$PATH"  | tee -a $logfile
echo "##  to your $SHELL startup script."  | tee -a $logfile
echo "##  "| tee -a $logfile
echo "##  See GetEpicsApps.log for complete log and error messages" | tee -a $logfile
echo "##############  " | tee -a $logfile
