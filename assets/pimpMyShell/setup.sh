#!/bin/bash

# Set destination for .zshrc and config files
DEST_DIR="$HOME"
ZSHRC="$DEST_DIR/.zshrc"
ZSHRC_D="$DEST_DIR/.zshrc.d"

# Create .zshrc.d directory if it doesn't exist
if [ ! -d "$ZSHRC_D" ]; then
    echo "Creating directory: $ZSHRC_D"
    mkdir -p "$ZSHRC_D"
fi

# Copy configuration files
echo "Copying configuration files..."
cp -r zshrc.d/* "$ZSHRC_D/"

# Create or overwrite .zshrc to source the configuration files
echo "Setting up .zshrc..."
cat <<EOL > "$ZSHRC"
# Source the modular Zsh configuration
source ~/.zshrc.d/options.zsh
source ~/.zshrc.d/history.zsh
source ~/.zshrc.d/aliases.zsh
source ~/.zshrc.d/prompt.zsh
source ~/.zshrc.d/syntax.zsh
source ~/.zshrc.d/async.zsh
source ~/.zshrc.d/cleanup.zsh
EOL

# Success message
echo "Zsh configuration has been set up successfully!"
echo "Please restart your terminal or run 'source ~/.zshrc' to apply changes."
