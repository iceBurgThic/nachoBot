# ~/.zshrc.d/cleanup.zsh

# Clean up async jobs after they finish
cleanup_async_jobs() {
    async_flush_jobs my_worker
}

# Add cleanup hook on shell exit
add-zsh-hook zshexit cleanup_async_jobs

# Command execution time display
human_time() {
    local total_seconds=$1
    local days=$(( total_seconds / 60 / 60 / 24 ))
    local hours=$(( total_seconds / 60 / 60 % 24 ))
    local minutes=$(( total_seconds / 60 % 60 ))
    local seconds=$(( total_seconds % 60 ))
    local human_time_str=""

    (( days > 0 )) && human_time_str+="${days}d "
    (( hours > 0 )) && human_time_str+="${hours}h "
    (( minutes > 0 )) && human_time_str+="${minutes}m "
    human_time_str+="${seconds}s"

    echo $human_time_str
}

# Record and display command execution time if it exceeds 5 seconds
preexec() { cmd_timestamp=$EPOCHSECONDS; }
precmd() {
    local elapsed=$(( EPOCHSECONDS - ${cmd_timestamp:-$EPOCHSECONDS} ))
    if [[ $elapsed -gt 5 ]]; then
        cmd_exec_time=$(human_time $elapsed)
        echo -e "\nCommand took $cmd_exec_time to complete."
    fi
}
add-zsh-hook preexec preexec
add-zsh-hook precmd precmd
