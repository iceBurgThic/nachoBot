# ~/.zshrc.d/prompt.zsh

# Prompt configuration
PROMPT='%F{cyan}%n@%m%f:%F{blue}%~%f$(git_prompt_info)%(!.#.>) '
RPROMPT='%F{magenta}%*%f'

# Function to display Git branch in the prompt
git_prompt_info() {
    local branch=$(git symbolic-ref --short HEAD 2>/dev/null)
    [[ -n $branch ]] && echo " %F{green}[$branch]%f"
}
