#!/bin/bash
# Shared host/container validation. No Python or credential reads on the host.

c3_solution_path() {
    local requested=$1 assessment=$2 solution=$3 ancestor suffix="" resolved
    if [[ -z "$requested" || "$requested" == *$'\n'* || "$requested" == *$'\r'* ]]; then
        echo "Docker grader: output paths must be non-empty single-line paths under solution/." >&2
        return 2
    fi
    if [[ "$requested" != /* ]]; then requested="$assessment/$requested"; fi
    if [[ "$requested/" == *"/../"* ]]; then
        echo "Docker grader: output paths must not contain parent traversal." >&2
        return 2
    fi
    ancestor=${requested%/}
    while [[ ! -d "$ancestor" ]]; do
        suffix="/${ancestor##*/}$suffix"
        ancestor=${ancestor%/*}
        if [[ -z "$ancestor" ]]; then ancestor=/; fi
    done
    resolved=$(CDPATH= cd -- "$ancestor" && pwd -P) || return 2
    resolved="${resolved%/}$suffix"
    if [[ "$resolved" != "$solution" && "$resolved" != "$solution/"* ]]; then
        echo "Docker grader: all new outputs must resolve under solution/." >&2
        return 2
    fi
    printf '%s\n' "$resolved"
}

c3_validate_grader_paths() {
    local assessment=$1 solution=$2 option value
    shift 2
    C3_VALIDATED_ARGS=()
    while [[ $# -gt 0 ]]; do
        option=$1
        shift
        case "$option" in
            --out|--tmp)
                if [[ $# -eq 0 || "$1" == --* ]]; then
                    echo "Docker grader: $option requires a path under solution/." >&2
                    return 2
                fi
                value=$(c3_solution_path "$1" "$assessment" "$solution") || return 2
                C3_VALIDATED_ARGS+=("$option" "$value")
                shift
                ;;
            --out=*|--tmp=*)
                value=$(c3_solution_path "${option#*=}" "$assessment" "$solution") || return 2
                C3_VALIDATED_ARGS+=("${option%%=*}=$value")
                ;;
            *) C3_VALIDATED_ARGS+=("$option");;
        esac
    done
}
