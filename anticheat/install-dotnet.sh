#!/bin/bash

# Get the ubuntu version from the first argument
if [ $# -eq 0 ]
  then
    echo "Please specify the Ubuntu version (18, 20, 22) as a parameter."
    exit
fi

if ! [[ $1 = @("18"|"20"|"22") ]];
  then
    echo "Incorrect Ubuntu version. Supported versions are 18, 20 and 22."
    echo "If you need dotnet for a different Ubuntu version or distribution,"
    echo "please check https://learn.microsoft.com/en-us/dotnet/core/install/linux"
    exit
fi

# Add the microsoft package feed
wget https://packages.microsoft.com/config/ubuntu/$1.04/packages-microsoft-prod.deb -O packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
rm packages-microsoft-prod.deb

# Install the dotnet SDK
sudo apt-get update
sudo apt-get install -y dotnet-sdk-7.0