from github import Github, GithubException
from github.NamedUser import NamedUser
from github.PaginatedList import PaginatedList
from typing import Tuple, List, Dict, Union
from enum import Enum
import requests_cache
import argparse
import os
import sys

REPOSITORIES = [
    "nrfconnect/sdk-nrf-next",
    "nrfconnect/sdk-ic-next",
    "nrfconnect/sdk-zephyr-next",
    "nrfconnect/sdk-secdom",
    "nrfconnect/sdk-sysctrl",
    "nrfconnect/nrf-regtool",
    "nrfconnect/nrfs",
    "nrfconnect/sdk-hal_nordic-next",
    "nrfconnect/sdk-nrfxlib-next",
    "nrfconnect/sdk-connectedhomeip-next",
    "NordicSemiconductor/nrfutil-package-index-external-confidential",
]

LIST_USER_CACHE_THRESHOLD = 3

class Access(Enum):
    MEMBER = "✔️"
    OUTSIDE = "✔️🚪"
    PENDING = "❌📧"
    NO_ACCESS = "❌"

    def __str__(self) -> str:
        return self.value


class RepoManager:
    """Repository access manager for onboarding.

    The following repositories are used:
    - https://github.com/nrfconnect/sdk-nrf-next
    - https://github.com/nrfconnect/sdk-ic-next
    - https://github.com/nrfconnect/sdk-zephyr-next
    - https://github.com/nrfconnect/sdk-secdom
    - https://github.com/nrfconnect/sdk-sysctrl
    - https://github.com/nrfconnect/nrf-regtool
    - https://github.com/nrfconnect/nrfs
    - https://github.com/nrfconnect/sdk-hal_nordic-next
    - https://github.com/nrfconnect/sdk-nrfxlib-next
    - https://github.com/nrfconnect/sdk-connectedhomeip-next
    - https://github.com/NordicSemiconductor/nrfutil-package-index-external-confidential
    """

    def __init__(self, access_token, id="common"):
        requests_cache.install_cache(f"github_cache_{id}")

        self._g = Github(access_token, per_page=100)
        self._repos = [self._g.get_repo(repo) for repo in REPOSITORIES]

    def _list_user_repo_access(self, user : NamedUser, collaborators : Dict[str, PaginatedList]) -> Dict[str, Access]:
        """
        API calls: 2 * repos + pagination
        """

        repos = {}
        for repo in self._repos:
            if collaborators:
                access = user in collaborators[repo.name]
            else:
                access = repo.has_in_collaborators(user)

            if access:
                repos[repo.name] = Access.MEMBER
            else:
                repos[repo.name] = Access.NO_ACCESS

            if access and user in repo.get_collaborators(affiliation="outside"):
                repos[repo.name] = Access.OUTSIDE
            elif not access and user in [invite.invitee for invite in repo.get_pending_invitations()]:
                repos[repo.name] = Access.PENDING
        return repos

    def list_repo_access(self, username : str, collaborators : Dict[str, PaginatedList] = None) -> Dict[str, Access]:
        """
        API calls: 2 * repos + pagination
        """

        try:
            user = self._g.get_user(username)
        except GithubException:
            return None

        return self._list_user_repo_access(user, collaborators)

    def list_users(self, usernames : List[str]) -> Dict[str, Dict[str, Access]]:
        """
        API calls: (2 * repos + pagination) * users
        """

        collaborators = {}
        if len(usernames) >= LIST_USER_CACHE_THRESHOLD:
            for repo in self._repos:
                collaborators[repo.name] = repo.get_collaborators()

        return {user: self.list_repo_access(user, collaborators) for user in usernames}
    
    def add_user(self, username : str) -> Tuple[bool, str]:
        """
        API calls: (2 * repos + pagination) + repos
        """

        try:
            user = self._g.get_user(username)
        except GithubException:
            return False, "Username not found"

        access_list = self._list_user_repo_access(user)
        for repo_name, access in access_list:
            if access == Access.MEMBER:
                return False, f"User is already an organization member of {repo_name}"
        
        try:
            for repo in self._repos:
                repo.add_to_collaborators(user, permission="pull")
        except GithubException as e:
            if "message" in e:
                return True, e["message"]
            return True, f"Something went wrong while adding to collaborators for {repo.name}"

        return True, ""

    def add_users(self, usernames : str) -> Dict[str, Tuple[bool, str]]:
        """
        API calls: ((2 * repos + pagination) + repos) * users
        """

        return {username: self.add_user(username) for username in usernames}

    def list_outside_collaborators(self) -> Dict[str, Dict[str, Access]]:
        """
        API calls: 3 * repo + pagination
        """
        all_outside_collaborators = []
        all_repos = {}
        for repo in self._repos:
            all_repos[repo.name] = {
                "all_collaborators": repo.get_collaborators(),
                "outside_collaborators": repo.get_collaborators(affiliation="outside"),
                "pending_invites": [inv.invitee for inv in repo.get_pending_invitations()],
            }
            all_outside_collaborators += all_repos[repo.name]["outside_collaborators"]


        collaborator_access_map = {}
        for collaborator in all_outside_collaborators:
            access_map = {repo.name: Access.NO_ACCESS for repo in self._repos}
            collaborator_access_map[collaborator.login] = access_map
            for repo_name, repo_map in all_repos.items():
                if collaborator in repo_map["outside_collaborators"]:
                    access_map[repo_name] = Access.OUTSIDE
                elif collaborator in repo_map["all_collaborators"]:
                    access_map[repo_name] = Access.MEMBER
                elif collaborator in repo_map["pending_invites"]:
                    access_map[repo_name] = Access.PENDING
        
        return collaborator_access_map

    def clear_cache(self):
        requests_cache.clear()

    def test(self):
        pass


def cli_help():
    print("\n0: Show this list of commands")
    print("1: List repository access for a user")
    print("2: List repository access for a list of users")
    print("3: List repository access for all outside collaborators")
    print("8: Test")
    print("9: Clear cached results")
    print("exit: Exit the REPL")

def print_repo_access(access_map : Dict[str, Access]):
    repos = [repo.split("/")[1] for repo in REPOSITORIES]
    for repo in repos:
        access = access_map[repo]
        prefix = "No access"
        if access == Access.OUTSIDE:
            prefix = "Outside col"
        elif access == Access.PENDING:
            prefix = "Invite pending"
        elif access == Access.MEMBER:
            prefix = "Org access"
        print(f"{prefix : <16}\t{repo} {access}")


def main(access_token):
    manager = RepoManager(access_token)

    print("GitHub Repository Access Manager for nrfconnect")
    cli_help()
    while True:
        choice = input("\n> ").strip().lower()
        if not choice:
            continue

        if choice in ["0", "h", "-h", "--help", "help"]:
            cli_help()

        elif choice in ["exit", "exit()", "break", "quit", "quit()", "q"]:
            break

        elif choice == "1":
            name = input("login name: \n> ")
            repos = manager.list_repo_access(name)
            if repos is None:
                print("Could not fetch data for the requested user")
            else:
                print_repo_access(repos)

        elif choice == "2":
            users = input("Space separated list of login names\n> ").split()
            lst = manager.list_users(users)
            for user in lst:
                print()
                if user is None:
                    print(f"Could not fetch data for the requested user {user}")
                else:
                    print(user)
                    print_repo_access(lst[user])

        elif choice == "3":
            lst = manager.list_outside_collaborators()
            for user in lst:
                print("\n" + user)
                print_repo_access(lst[user])

        elif choice == "8":
            manager.test()

        elif choice == "9":
            manager.clear_cache()


if __name__ == "__main__":
    token = os.environ["ACCESS_TOKEN"]

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-t",
        "--access-token",
        default=token,
        type=str,
        help="GitHub access token. "
        "The environment variable ACCESS_TOKEN is used by default.",
    )

    args = parser.parse_args()
    if not args.access_token:
        sys.exit("ACCESS_TOKEN environment variable not set")

    main(args.access_token)
