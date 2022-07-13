#!/bin/bash

# Script configurations
SCRIPT="KiBot"

# Mandatory arguments
margs=1

# Arguments and their default values
CONFIG=""
BOARD=""
SCHEMA=""
SKIP=""
DIR=""

# Exit error code
EXIT_ERROR=1

function msg_example {
    echo -e "example: $SCRIPT -d docs -b example.kicad_pcb -e example.sch -c docs.kibot.yaml"
}

function msg_usage {
    echo -e "usage: $SCRIPT [OPTIONS]... -c <yaml-config-file>"
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
	echo -e "Mandatory arguments:"
    echo -e "  -c, --config FILE .kibot.yaml config file"

	echo -e "\nOptional control arguments:"
    echo -e "  -d, --dir DIR output path. Default: current dir, will be used as prefix of dir configured in config file"
    echo -e "  -b, --board FILE .kicad_pcb board file. Default: first board file found in current folder."
    echo -e "  -e, --schema FILE .sch schematic file.  Default: first schematic file found in current folder."
    echo -e "  -s, --skip Skip preflights, comma separated or 'all'"

	echo -e "\nMiscellaneous:"
    echo -e "  -v, --verbose annotate program execution"
    echo -e "  -h, --help display this message and exit"
}

function msg_more_info {
    echo -e "Try '$SCRIPT --help' for more information."
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


# Ensures that the number of passed args are at least equals
# to the declared number of mandatory args.
# It also handles the special case of the -h or --help arg.
function margs_precheck {
	if [ "$1" -lt "$margs" ]; then
        if [ "$2" == "--help" ] || [ "$2" == "-h" ]; then
            help
        else
            usage
        fi
        exit $EXIT_ERROR
	fi
}

# Ensures that all the mandatory args are not empty
function margs_check {
	if [ "$#" -lt "$margs" ]; then
        usage
	    exit $EXIT_ERROR
	fi
}

function args_process {
    while [ "$1" != "" ];
    do
       case "$1" in
           -c | --config ) shift
               CONFIG="$1"
               ;;
           -b | --board ) shift
               BOARD="-b $1"
               ;;
           -e | --schematic ) shift
               SCHEMA="-e $1"
               ;;
           -d | --dir) shift
               DIR="-d $1"
               ;;
           -s | --skip) shift
               SKIP="-s $1"
               ;;
           -v | --verbose) shift
               if [ "$1" == "0" ]; then
                   VERBOSE=""
               elif [ "$1" == "1" ]; then
                   VERBOSE="-v"
               elif [ "$1" == "2" ]; then
                   VERBOSE="-vv"
               elif [ "$1" == "3" ]; then
                   VERBOSE="-vvv"
               else
                   VERBOSE="-vvvv"
               fi
               ;;
           -h  | --help )
               help
               exit
               ;;
           *)                     
               illegal_arg "$@"
               exit $EXIT_ERROR
               ;;
        esac
        shift
    done
}

function run {
    CONFIG="$(echo "$CONFIG" | tr -d '[:space:]')"

    if [ -d .git ]; then
        /usr/bin/kicad-git-filters.py
    fi

    if [ -f $CONFIG ]; then
        kibot -c $CONFIG $DIR $BOARD $SCHEMA $SKIP $VERBOSE
    else
        echo "config file '$CONFIG' not found!"
        exit $EXIT_ERROR
    fi 
}

function main {
    margs_precheck "$#" "$1"

    args_process "$@"

    run
}

echo "*****************************************************************************************"
echo "*****************************************************************************************"
echo
echo
echo KiBot GitHub Action v1 for KiCad 5
echo
echo "**********************************"
echo "*** Please switch to v2 action ***"
echo "**********************************"
echo
echo
kibot --version
dpkg -l kicad | grep kicad
echo Debian: `cat /etc/debian_version`
kicost --version
pcbdraw --version
echo "iBoM:" `INTERACTIVE_HTML_BOM_NO_DISPLAY=True generate_interactive_bom.py --version 2> /dev/null | grep "^v"`
echo
echo
echo "*****************************************************************************************"
echo "*****************************************************************************************"

# Removes quotes
args=$(xargs <<<"$@")

# Arguments as an array
IFS=' ' read -a args <<< "$args"

# Run main
main "${args[@]}"
