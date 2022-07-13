#!/bin/bash

# Script configurations
SCRIPT="KiBot"

# Arguments and their default values
CONFIG=""
BOARD=""
SCHEMA=""
SKIP=""
DIR=""
VARIANT=""
TARGETS=""
QUICKSTART="NO"

# Exit error code
EXIT_ERROR=1

function msg_example {
    echo -e "example: $SCRIPT '-d docs' '-b example.kicad_pcb' '-e example.sch' '-c docs.kibot.yaml'"
}

function msg_usage {
    echo -e "usage: $SCRIPT [OPTIONS]..."
}

function msg_disclaimer {
    echo -e "This is free software: you are free to change and redistribute it"
    echo -e "There is NO WARRANTY, to the extent permitted by law.\n"
    echo -e "See <https://github.com/INTI-CMNB/KiBot>."
}

function msg_illegal_arg {
    echo -e "$SCRIPT: illegal option $@"
}

function msg_help {
    echo -e "\nOptional control arguments:"
    echo -e "  '-c FILE' .kibot.yaml config file"
    echo -e "  '-d DIR' output path. Default: current dir, will be used as prefix of dir configured in config file"
    echo -e "  '-b FILE' .kicad_pcb board file. Use __SCAN__ to get the first board file found in current folder."
    echo -e "  '-e FILE' .sch schematic file.  Use __SCAN__ to get the first schematic file found in current folder."
    echo -e "  '-q YES' generate configs and outputs automagically (-b, -e, -s, -V, -c are ignored)."
    echo -e "  '-s PRES' skip preflights, comma separated or 'all'"
    echo -e "  '-t TARGETS' list of targets to generate separated by spaces. To only run preflights use __NONE__."
    echo -e "  '-V VARIANT' global variant"

    echo -e "\nMiscellaneous:"
    echo -e "  '-v LEVEL' annotate program execution"
    echo -e "  -h display this message and exit"
}

function msg_more_info {
    echo -e "Try '$SCRIPT -h' for more information."
}

function help {
    msg_usage
    echo ""
    msg_help
    echo ""
    msg_example
    echo ""
    msg_disclaimer
}

function illegal_arg {
    msg_illegal_arg "$@"
    echo ""
    msg_usage
    echo ""
    msg_example
    echo ""
    msg_more_info
}

function usage {
    msg_usage
    echo ""
    msg_more_info
}


function args_process {
    while [ "$1" != "" ];
    do
       ARG="$1"
       VAL=${ARG:3:10000}
       case ${ARG:0:2} in
           -c) if [ "$VAL" == "__SCAN__" ]; then
                   CONFIG=""
               else
                   CONFIG="-c '$VAL'"
               fi
               ;;
           -b) if [ "$VAL" == "__SCAN__" ]; then
                   BOARD=""
               else
                   BOARD="-b '$VAL'"
               fi
               ;;
           -e) if [ "$VAL" == "__SCAN__" ]; then
                   SCHEMA=""
               else
                   SCHEMA="-e '$VAL'"
               fi
               ;;
           -t) if [ "$VAL" == "__NONE__" ]; then
                   TARGETS="-i"
               elif [ "$VAL" == "__ALL__" ]; then
                   TARGETS=""
               else
                   TARGETS="$VAL"
               fi
               ;;
           -V) if [ "$VAL" == "__NONE__" ]; then
                   VARIANT=""
               else
                   VARIANT="-g variant=$VAL"
               fi
               ;;
           -d) DIR="-d '$VAL'"
               ;;
           -q) QUICKSTART="$VAL"
               ;;
           -s) if [ "$VAL" == "__NONE__" ]; then
                   SKIP=""
               else
                   SKIP="-s $VAL"
               fi
               ;;
           -v) if [ "$VAL" == "0" ]; then
                   VERBOSE=""
               elif [ "$VAL" == "1" ]; then
                   VERBOSE="-v"
               elif [ "$VAL" == "2" ]; then
                   VERBOSE="-vv"
               elif [ "$VAL" == "3" ]; then
                   VERBOSE="-vvv"
               else
                   VERBOSE="-vvvv"
               fi
               ;;
           -h) help
               exit
               ;;
           *)  illegal_arg "$@"
               exit $EXIT_ERROR
               ;;
        esac
        shift
    done
}

function run {
    if [ -d .git ]; then
        /usr/bin/kicad-git-filters.py
    fi

    if [ $QUICKSTART == "YES" ]; then
        echo Quick-start options: $VERBOSE --quick-start
        /bin/bash -c "kibot $VERBOSE --quick-start"
    else
        echo Options: $CONFIG $DIR $BOARD $SCHEMA $SKIP $VERBOSE $VARIANT $TARGETS
        /bin/bash -c "kibot $CONFIG $DIR $BOARD $SCHEMA $SKIP $VERBOSE $VARIANT $TARGETS"
    fi
}

function main {
    args_process "$@"

    run
}

echo "*****************************************************************************************"
echo "*****************************************************************************************"
echo
echo
echo "KiBot GitHub Action v2 for KiCad 6 (Fixed version)"
echo
echo
kibot --version
dpkg -l kicad | grep kicad
echo Debian: `cat /etc/debian_version`
pcbnew_do --version
kicost --version
pcbdraw --version
echo "iBoM:" `INTERACTIVE_HTML_BOM_NO_DISPLAY=True generate_interactive_bom.py --version 2> /dev/null | grep "^v"`
echo
echo
echo "*****************************************************************************************"
echo "*****************************************************************************************"

main "$@"
