#!/bin/bash
set -euo pipefail

key="gibberish"

PRIVATE=0
while getopts "p" opt; do
  case "$opt" in
    p) PRIVATE=1 ;;
    *) echo "Usage: $0 [-p] <commit message>" >&2; exit 1 ;;
  esac
done
shift $((OPTIND - 1))

# Function to find the nearest Git repository
find_git_repo() {
  local dir="$1"
  
  while [[ "$dir" != "/home/bogfootlj/" ]]; do
    if [[ -d "$dir/.git" ]]; then
      echo "$dir"
      return 0
    else
      dir=$(dirname "$dir")
    fi
  done
  return 1
}

# Function to move to the Git repository directory
move_to_git_repo() {
	echo "Moving up"
  local repo_path="$1"
  pushd "$repo_path" >/dev/null || exit 1
}

# Function to move back to the original directory
move_back() {
	echo "Moving back"
  popd >/dev/null || exit 1
}

# Save the current directory
original_dir="$(pwd)"

# Find the nearest Git repository
repo_path=$(find_git_repo "$original_dir")

if [[ -z "$repo_path" ]]; then
  echo "No Git repository found."
  exit 1
fi

# Move to the Git repository directorw
move_to_git_repo "$repo_path"

repo_path=$(basename "$PWD")

# Prompt for a commit message

if [[ "$#" -eq 0 ]]; then
	echo "No commit message added. Please add it now: "
	read -p "Enter commit message: " commit_message
else
	echo "Commit message is: $@"
	commit_message="$@"
fi
[ -n "$commit_message" ] || { echo "Commit message required" >&2; exit 1; }

git add -A
git commit -m "$commit_message"

if (( PRIVATE )); then
  git push -f "https://${key}@github.com/Bogfoot/${repo_path}.git"
else
  git push -u origin main
fi

# Add anw other Git commands you'd like to execute

# Move back to the original directory
move_back

echo "Git commands executed successfully in $repo_path."
