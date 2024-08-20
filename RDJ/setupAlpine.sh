#!/bin/sh

# Update and upgrade the system
echo "Updating Alpine packages..."
apk update && apk upgrade

# Install common and useful terminal tools
echo "Installing essential terminal tools..."
apk add --no-cache \
    bash \
    curl \
    wget \
    vim \
    nano \
    htop \
    tmux \
    openssh \
    git \
    zip \
    unzip \
    rsync \
    sudo \
    ca-certificates \
    openssl \
    bash-completion \
    man-db \
    less \
    file

# Install Python and pip
echo "Installing Python and pip..."
apk add --no-cache \
    python3 \
    py3-pip

# Set up bash as the default shell
echo "Setting bash as default shell..."
sed -i -e "s:/bin/ash:/bin/bash:" /etc/passwd

# Configure bash completion
echo "Setting up bash completion..."
echo "source /etc/profile.d/bash_completion.sh" >> ~/.bashrc

# Install additional tools that might be useful
echo "Installing additional utilities..."
apk add --no-cache \
    jq \
    ncdu \
    git-lfs

# Clean up to reduce image size
echo "Cleaning up..."
rm -rf /var/cache/apk/*

# Verify installation
echo "Verifying installations..."
python3 --version
pip3 --version
git --version
htop --version
curl --version

echo "Setup complete! Please restart your terminal session."
