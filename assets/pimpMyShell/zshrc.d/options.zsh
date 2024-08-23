# ~/.zshrc.d/options.zsh

# General shell options
setopt AUTO_CD                # Automatically change to a directory when you type its name
setopt HIST_IGNORE_DUPS       # Don't record duplicate entries in history
setopt HIST_FIND_NO_DUPS      # Don't show duplicates in history search
setopt SHARE_HISTORY          # Share history across terminals
setopt INC_APPEND_HISTORY     # Append history incrementally, rather than overwriting
setopt HIST_IGNORE_SPACE      # Ignore commands that start with a space
setopt NO_BG_NICE             # Prevent background jobs from reducing priority

# Default editor
export EDITOR='vim'
