#!/bin/sh

if [ $# -eq 1 ]; then
    if [ "$1" == "debug" ]; then
        echo "Running anticheat in Debug configuration."
        dotnet run --configuration Debug
        exit
    fi
fi

dotnet run --configuration Release