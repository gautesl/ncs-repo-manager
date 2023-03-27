from github import Github, GithubException
from github.NamedUser import NamedUser
from typing import Tuple, List, Dict, Union
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

    def __init__(self, access_token):
        requests_cache.install_cache("github_cache")

        self._g = Github(access_token)
        self._repos = [self._g.get_repo(repo) for repo in REPOSITORIES]

    def _list_user_repo_access(self, user : NamedUser) -> List[Tuple[str, Union[bool, str]]]:
        repos = []
        for repo in self._repos:
            access = repo.has_in_collaborators(user)
            if user in repo.get_collaborators(affiliation="outside"):
                access = "outside"
            elif not access and user in [invite.invitee for invite in repo.get_pending_invitations()]:
                access = "pending"
            repos.append((repo.name, access))
        return repos

    def list_repo_access(self, username : str) -> List[Tuple[str, Union[bool, str]]]:
        try:
            user = self._g.get_user(username)
        except GithubException:
            return None

        return self._list_user_repo_access(user)

    def list_users(self, usernames : str) -> Dict[str, List[Tuple[str, Union[bool, str]]]]:
        return {user: self.list_repo_access(user) for user in usernames}
    
    def add_user(self, username : str) -> Tuple[bool, str]:
        try:
            user = self._g.get_user(username)
        except GithubException:
            return False, "Username not found"

        access_list = self._list_user_repo_access(user)
        for repo_name, access in access_list:
            if access is True:
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
        return {username: self.add_user(username) for username in usernames}

    # def list_outside_collaborators(self):
    #     all_outside_collaborators = []
    #     all_repos = {}
    #     for repo in self._repos:
    #         all_repos[repo.name] = {
    #             "all_collaborators": repo.get_collaborators(),
    #             "outside_collaborators": repo.get_collaborators(affiliation="outside"),
    #             "pending_invites": [inv.invitee for inv in repo.get_pending_invitations()],
    #         }
    #         all_outside_collaborators += list()


    #     cols = {}
    #     for repo_name, repo_map in all_repos.items():
    #         for outside_collaborator in repo_map["outside_collaborators"]:
    #             if not outside_collaborator in cols:
    #                 cols[outside_collaborator] = {repo.name: False for repo in self._repos}
    #             cols[outside_collaborator][repo_name] = "outside"




    # def list_outside_collaborators(self) -> Dict[str, List[Tuple[str, Union[bool, str]]]]:
    #     print("Getting organizations")
    #     orgs = [self._g.get_organization("nrfconnect"), self._g.get_organization("NordicSemiconductor")]
    #     collaborators = set()

    #     print("Getting outside collaborators")
    #     try:
    #         for org in orgs:
    #             collaborators.update(list(org.get_outside_collaborators()))
    #     except GithubException as e:
    #         print("Exception received:")
    #         print(e)
    #         return None
 
    #     print("Constructing return list")
    #     res = {}
    #     for collaborator in collaborators:
    #         print("Checking user", collaborator.login)
    #         access_tuple_list = self._list_user_repo_access(collaborator)
    #         _, access_list = zip(*access_tuple_list)
    #         if any(access_list):
    #             print("User has at least access to one repository")
    #             res[collaborator.login] = access_tuple_list
        
    #     print("Finished list_outside_collaborators() successfully")
    #     return res


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
                continue

            for repo, access in repos:
                prefix = "No access       "
                if access == "outside":
                    prefix = "Outside col     "
                elif access == "pending":
                    prefix = "Invite pending  "
                elif access is True:
                    prefix = "Org access      "
                print(f"{prefix} {repo}")

        elif choice == "2":
            users = input("Space separated list of login names\n> ").split()
            lst = manager.list_users(users)
            for user in lst:
                print("\n" + user)
                for repo, access in lst[user]:
                    print(f"{'X' if access else ' '} {repo}")

        elif choice == "3":
            print(manager.list_outside_collaborators())

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
