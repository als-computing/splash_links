#!/usr/bin/env python3
"""
Script to update the tree snippet in README.md with a directory tree that hyper-links each file
and directory to its location in the repository.

Prerequisites:
  - If not using repository hyperlinks, the 'tree' command must be installed and available in your PATH.
  - Your README.md must contain the following markers:
      <!-- TREE START -->
      ... (existing tree snippet) ...
      <!-- TREE END -->

Usage:
  # Update the tree snippet in README.md (using the current directory as target)
  python scripts/update_readme_tree.py

  # Optionally, specify a different README file or target directory:
  python scripts/update_readme_tree.py --readme README.md --dir .

  # To generate tree entries as hyperlinks, provide your repository's base URL and (optionally) branch:
  python scripts/update_readme_tree.py --repo-url "https://github.com/youruser/yourrepo" --branch main
"""

import argparse
import subprocess
import re
import sys
import logging
import shutil
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def get_tree_output(target_dir: str = ".") -> str:
    """
    Run the 'tree' command on the specified directory and return its output.

    Args:
        target_dir (str): The directory to generate the tree from (default: current directory).

    Returns:
        str: The output from the tree command.

    Raises:
        EnvironmentError: If the 'tree' command is not available.
        subprocess.CalledProcessError: If the 'tree' command fails.
    """
    if shutil.which("tree") is None:
        raise EnvironmentError("The 'tree' command is not available. Please install it.")

    try:
        result = subprocess.run(
            ["tree", target_dir],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logging.error("Error running 'tree' command: %s", e)
        raise


def generate_tree_with_links(current_dir: str, base_path: str, repo_url: str, branch: str, prefix: str = "") -> list[str]:
    """
    Recursively generate a tree with HTML hyperlinks for each file and directory.

    For files, the link points to:
       {repo_url}/blob/{branch}/{relative_path}
    For directories, the link points to:
       {repo_url}/tree/{branch}/{relative_path}

    The entry is rendered as an HTML anchor tag so that when wrapped in an HTML block,
    the link is clickable.

    Args:
        current_dir (str): The current directory being processed.
        base_path (str): The root directory used to compute relative paths.
        repo_url (str): The base URL of the repository (e.g., https://github.com/user/repo).
        branch (str): The branch name (e.g., main).
        prefix (str): The prefix string for the current tree level (used for indentation).

    Returns:
        list[str]: A list of strings representing the tree lines with HTML hyperlinks.
    """
    tree_lines = []
    try:
        # List non-hidden entries
        entries = [entry for entry in os.listdir(current_dir) if not entry.startswith('.')]
    except OSError as e:
        raise OSError(f"Unable to list directory '{current_dir}': {e.strerror}") from e

    entries.sort()
    count = len(entries)
    for i, entry in enumerate(entries):
        full_path = os.path.join(current_dir, entry)
        is_last = (i == count - 1)
        branch_symbol = "└── " if is_last else "├── "

        # Compute the relative path for hyperlinking
        rel_path = os.path.relpath(full_path, start=base_path)
        # Normalize the relative path for URL use
        rel_path_url = rel_path.lstrip("./")
        if os.path.isdir(full_path):
            url = f"{repo_url}/tree/{branch}/{rel_path_url}"
        else:
            url = f"{repo_url}/blob/{branch}/{rel_path_url}"

        # Create an HTML hyperlink for the entry (using an HTML <a> tag)
        link = f'<a href="{url}">{entry}</a>'
        tree_lines.append(prefix + branch_symbol + link)

        if os.path.isdir(full_path):
            extension = "    " if is_last else "│   "
            tree_lines.extend(generate_tree_with_links(full_path, base_path, repo_url, branch, prefix + extension))
    return tree_lines


def update_readme_tree(readme_path: str, tree_output: str) -> None:
    """
    Update the README.md file by replacing the tree snippet between the designated markers.

    The file must contain the following markers:
        <!-- TREE START -->
        ... (existing tree snippet) ...
        <!-- TREE END -->

    This function replaces everything between these markers with an HTML block
    that preserves spacing (using a <pre> element) and renders clickable links.

    Args:
        readme_path (str): Path to the README.md file.
        tree_output (str): New tree output to insert.

    Raises:
        FileNotFoundError: If the README.md file does not exist.
        ValueError: If the required markers are not found in the file.
    """
    if not os.path.isfile(readme_path):
        raise FileNotFoundError(f"README.md file not found at '{readme_path}'.")

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Regex pattern to match the tree snippet between markers (using DOTALL mode)
    pattern = re.compile(
        r"(<!--\s*TREE START\s*-->)(.*?)(<!--\s*TREE END\s*-->)",
        re.DOTALL
    )

    # Wrap the tree output in a <pre> block (GitHub preserves whitespace in <pre> and renders HTML)
    new_tree_block = (
        "<!-- TREE START -->\n"
        "<pre>\n"
        f"{tree_output}\n"
        "</pre>\n"
        "<!-- TREE END -->"
    )
    updated_content, count = pattern.subn(new_tree_block, content)

    if count == 0:
        raise ValueError(
            "Markers <!-- TREE START --> and <!-- TREE END --> not found in README.md. "
            "Please add these markers to indicate where the tree should be updated."
        )

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(updated_content)

    logging.info("Successfully updated '%s' with the new tree output.", readme_path)


def parse_arguments() -> argparse.Namespace:
    """
    Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed arguments containing the README path, target directory, repository URL, and branch.
    """
    parser = argparse.ArgumentParser(
        description="Update the README.md tree snippet using a directory tree with hyperlinks."
    )
    parser.add_argument(
        "--readme",
        type=str,
        default="README.md",
        help="Path to the README.md file (default: README.md)"
    )
    parser.add_argument(
        "--dir",
        type=str,
        default=".",
        help="Target directory to generate the tree output from (default: current directory)"
    )
    parser.add_argument(
        "--repo-url",
        type=str,
        default="",
        help="Base URL of the repository (e.g., https://github.com/user/repo). If provided, tree entries will be hyperlinked."
    )
    parser.add_argument(
        "--branch",
        type=str,
        default="main",
        help="Repository branch to link to (default: main)"
    )
    return parser.parse_args()


def main() -> None:
    """
    Main function: generate the tree output and update the README.md file.
    """
    args = parse_arguments()
    target_dir = args.dir

    # If a repository URL is provided, generate the tree with HTML hyperlinks;
    # otherwise, fall back to the system's 'tree' command output.
    if args.repo_url:
        base_path = os.path.abspath(target_dir)
        tree_lines = ["."]  # Root line
        tree_lines.extend(generate_tree_with_links(base_path, base_path, args.repo_url.rstrip("/"), args.branch))
        tree_output = "\n".join(tree_lines)
    else:
        try:
            tree_output = get_tree_output(target_dir)
        except Exception as e:
            logging.error("Failed to get tree output: %s", e)
            sys.exit(1)

    try:
        update_readme_tree(args.readme, tree_output)
    except Exception as e:
        logging.error("Failed to update README.md: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
