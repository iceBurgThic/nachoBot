# ~/.zshrc.d/async.zsh

# Initialize zsh-async
async_init() {
    zmodload zsh/zpty
    zmodload zsh/datetime

    typeset -g ASYNC_ZPTY_RETURNS_FD=0
    if [[ -o interactive ]] && [[ -o zle ]]; then
        typeset -h REPLY
        zpty _async_test :
        (( REPLY )) && ASYNC_ZPTY_RETURNS_FD=1
        zpty -d _async_test
    fi
}

# Start async worker
async_start_worker my_worker

# Fetch Git status asynchronously
fetch_git_status() {
    git_prompt_info() {
        local branch=$(git symbolic-ref --short HEAD 2>/dev/null)
        [[ -n $branch ]] && echo "[$branch]"
    }

    async_job my_worker git_prompt_info
}

# Update prompt after fetching Git status
update_prompt_with_git_status() {
    local job=$1 ret=$2 output=$3 duration=$4
    PROMPT='%F{cyan}%n@%m%f:%F{blue}%~%f %F{green}'"${output}"'%f%(!.#.>) '
    RPROMPT='%F{magenta}%*%f'
}

# Register the callback
async_register_callback my_worker update_prompt_with_git_status

# Trigger async Git status fetch before each prompt
precmd() {
    fetch_git_status
}
autoload -Uz add-zsh-hook
add-zsh-hook precmd precmd
