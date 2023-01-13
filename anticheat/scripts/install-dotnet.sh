#!/bin/bash

# Get the ubuntu version

if ! [[ "$(lsb_release -sr)" = @("18.04"|"20.04"|"22.04") ]]; then
    echo "Incorrect Ubuntu version ("$(lsb_release -sr)"). Supported versions are 18.04, 20.04 and 22.04."
    echo "If you need dotnet for a different Ubuntu version or distribution,"
    echo "please check https://learn.microsoft.com/en-us/dotnet/core/install/linux"
    exit
fi

echo "install"
exit

# Add the microsoft package feed
wget https://packages.microsoft.com/config/ubuntu/$1.04/packages-microsoft-prod.deb -O packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
rm packages-microsoft-prod.deb

# Install the dotnet SDK
sudo apt-get update
sudo apt-get install -y dotnet-sdk-7.0