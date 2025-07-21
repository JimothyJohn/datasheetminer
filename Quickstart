#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail
set -e

if [[ "${TRACE-0}" == "1" ]]; then
    set -o xtrace
fi

# Function to display help
help_function() {
    cat <<EOF

Usage: $(basename "$0") [-h] [--lib-dir LIB_DIR]

Options:
  -h, --help       Display this help message and exit
  --lib-dir        Optional path to the lib/ directory
  -f, --function   Name of the lambda function

EOF
}

# Function to check if a command exists
command_exists() {
    echo "Checking if command '$1' exists..."
    if command -v "$1" >/dev/null 2>&1; then
        echo "Command '$1' found."
        return 0
    else
        echo "Command '$1' not found."
        return 1
    fi
}

# Check required dependencies
check_dependencies() {
    if ! command_exists docker; then
        cat <<EOF

Docker is not installed. Install it using:

curl -fsSL https://get.docker.com -o get-docker.sh && \\
    sudo sh get-docker.sh

EOF
        exit 1
    fi

    if ! command_exists sam; then
        cat <<EOF

AWS SAM CLI is not installed or not in your PATH. Install it with:

Linux:

wget https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip && \\
    unzip aws-sam-cli-linux-x86_64.zip -d sam-installation && \\
    sudo ./sam-installation/install && \\
    rm -rf aws-sam-cli-linux-x86_64.zip sam-installation

macOS:

brew tap aws/tap && \\
    brew install aws-sam-cli

EOF
        exit 1
    fi

    if ! command_exists pip; then
        cat <<EOF

Pip is not installed. Install it with:

Linux:

sudo apt install python3-pip

macOS:

brew install python3

EOF
        exit 1
    fi
}

# Main function of the script
main() {
    local FUNCTION="cerebro"

    # Parse arguments
    while [[ "$#" -gt 0 ]]; do
        case "$1" in
            -h|--help)
                help_function
                exit 0
                ;;
            -f|--function)
                FUNCTION="$2"
                shift 2
                ;;
            *)
                echo "Unknown parameter passed: $1"
                help_function
                exit 1
                ;;
        esac
    done

    echo "Current PATH: $PATH"
    echo "Checking if 'sam' is available..."
    which sam || echo "'sam' not found in PATH"

    # Check for required dependencies
    echo "Checking dependencies..."
    check_dependencies

    # Install virtual environment
    echo "Activating environment..."
    # In Quickstart.sh, under "Activating environment..."
    echo "Activating environment..."
    if [ ! -d "venv" ]; then
        echo "Virtual environment not found. Creating one..."
        python3 -m venv venv && \
            source venv/bin/activate && \
            pip install -q --upgrade pip && \
            pip install -q -r requirements.txt
    fi

    source venv/bin/activate

    # Deploy updates to AWS
    echo "Updating endpoint..."
    black -q cerebro/ && \
        sam validate --lint && \
        sam build && \
        PYTHONPATH="$(pwd)"/cerebro pytest -q tests/unit && \
        PYTHONPATH="$(pwd)"/cerebro pytest -q tests/integration && \
        deactivate

    sam sync --stack-name cerebro-reverse-proxy --watch
}

main "$@"
