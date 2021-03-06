# -*- coding: utf-8 -*-
"""Bintray Package info update

This Conan hook reads your recipe and updates its Bintray package info using the attributes.

It's necessary pass Bintray login by environment variables:
  - BINTRAY_LOGIN_USERNAME: Bintray login username
  - BINTRAY_PASSWORD: Bintray API KEY

The hook is automatically called when upload command is executed:

    $ conan upload -r bintray-repo package/0.1.0@user/channel
    Uploading package/0.1.0@user/channel to remote 'bintray-repo'
    [HOOK - bintray-update] post_upload(): Reading package info form Bintray...
    [HOOK - bintray-update] post_upload(): Inspecting recipe info ...
    [HOOK - bintray-update] post_upload(): Bintray is outdated. Updating Bintray package info ...

"""

import os
import re
import subprocess
import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
from conans.client import conan_api


__version__ = '0.1.0'
__license__ = 'MIT'
__author__  = 'Conan.io <https://github.com/conan-io>'


def post_upload_recipe(output, conanfile_path, reference, remote, **kwargs):
    """
    Update Bintray package info after upload Conan recipe
    :param output: Conan stream output
    :param conanfile_path: Conan exported recipe file path
    :param reference: Conan package reference
    :param remote: Conan remote object
    :param kwargs: Extra arguments
    """
    try:
        package_url = _get_bintray_package_url(remote=remote, reference=reference)
        output.info("Reading package info form Bintray...")
        remote_info = _get_package_info_from_bintray(package_url=package_url)
        output.info("Inspecting recipe info ...")
        recipe_info = _get_package_info_from_recipe(conanfile_path=conanfile_path)
        updated_info = _update_package_info(recipe_info=recipe_info, remote_info=remote_info)
        if updated_info:
            output.info("Bintray is outdated. Updating Bintray package info: {}".format(" ".join(updated_info.keys())))
            _patch_bintray_package_info(package_url=package_url, package_info=updated_info, remote=remote)
        else:
            output.info("Bintray package info is up-to-date.")
    except Exception as error:
        output.error(str(error))


def _extract_user_repo(remote):
    """
    Extract username and repository name from remote URL
    :param remote: Conan remote object
    :return: username, repository name
    """
    pattern = r'https?:\/\/api.bintray.com\/conan\/(.*)\/(.*)'
    match = re.match(pattern=pattern, string=remote.url)
    if not match:
        raise ValueError("The remote {} is not a Bintray repository." % remote.name)
    return match.group(1), match.group(2)


def _get_bintray_package_url(remote, reference):
    """
    Retrieve Bintray package repository URL
    :param remote: Conan remote object
    :param reference: Conan reference object
    :return: Bintray URL
    """
    user, repo = _extract_user_repo(remote)
    package = "{}%3A{}".format(reference.name, reference.user)
    url = os.getenv('BINTRAY_API_URL', 'https://api.bintray.com')
    return "{}/packages/{}/{}/{}".format(url, user, repo, package)


def _get_package_info_from_bintray(package_url):
    """
    Read package info from Bintray repository
    :param package_url: Bintray package URL
    :return: Package data from Bintray
    """
    response = requests.get(url=package_url)
    if not response.ok:
        raise HTTPError("Could not request package info: {} ({})".format(response.text, response.status_code))
    return response.json()


def _get_package_info_from_recipe(conanfile_path):
    """
    Inspect Conan recipe using Conan API
    :param conanfile_path: Conan recipe path
    :return: All attributes from the recipe
    """
    conan_instance, _, _ = conan_api.Conan.factory()
    return conan_instance.inspect(path=conanfile_path, attributes=None)


def _update_package_info(recipe_info, remote_info):
    """
    Merge recipe data info remote data
    :param recipe_info: Data collected from Conan recipe
    :param remote_info: Data collected from Bintray repository
    :return: is it outdated, updated bintray info
    """
    updated_info = {}
    description = recipe_info['description']
    if description:
        if remote_info['desc'] != description:
            updated_info['desc'] = description

    topics = recipe_info['topics']
    if topics:
        if remote_info['labels'] != topics:
            updated_info['labels'] = topics

    licenses = recipe_info['license']
    if licenses:
        if isinstance(licenses, str):
            licenses = [licenses]
        if not bool(set(licenses).intersection(remote_info['licenses'])):
            updated_info['licenses'] = licenses

    url = recipe_info['url']
    if url:
        updated_info['vcs_url'] = url

    issue_tracker_url = "{}/community/issues".format(url[:url.rfind('/')]) if url else ""
    issue_tracker_url = os.getenv("BINTRAY_ISSUE_TRACKER_URL", issue_tracker_url)

    if issue_tracker_url:
        if remote_info['issue_tracker_url'] != issue_tracker_url:
            updated_info['issue_tracker_url'] = issue_tracker_url

    if _is_stable_branch(_get_branch()):
        if 'maturity' not in remote_info or remote_info['maturity'] != "Stable":
            updated_info['maturity'] = "Stable"

    homepage = recipe_info['homepage']
    if homepage:
        if remote_info['website_url'] != homepage:
            updated_info['website_url'] = homepage

    return updated_info


def _patch_bintray_package_info(package_url, package_info, remote):
    if 'https' not in package_url:
        raise ValueError("Bad package URL: Only HTTPS is allowed, Bintray API uses Basic Auth")
    username, password = _get_credentials(remote)
    response = requests.patch(
        url=package_url, json=package_info, auth=HTTPBasicAuth(username, password))
    if not response.ok:
        raise HTTPError("Could not patch package info: {}".format(response.text))
    return response.json()


def _get_credentials(remote):
    """
    Get Bintray user name and password from environment variables
    :param remote: Conan remote name
    :return: username, password
    """
    remote_name = str(remote.name).upper()
    for var in [("BINTRAY_LOGIN_USERNAME_%s" % remote_name), "BINTRAY_LOGIN_USERNAME", "BINTRAY_USERNAME"]:
        username = os.getenv(var)
        if username: break

    if not username:
        raise ValueError("Could not update Bintray info: username not found")
    password = os.getenv("BINTRAY_PASSWORD_%s" % remote_name, os.getenv("BINTRAY_PASSWORD"))
    if not password:
        raise Exception("Could not update Bintray info: password not found")
    return username, password


def _get_branch():
    """
    Read current branch name
    :return: git branch name
    """
    ci_manager = {
        "TRAVIS": "TRAVIS_BRANCH",
        "APPVEYOR": "APPVEYOR_REPO_BRANCH",
        "bamboo_buildNumber": "bamboo_planRepository_branch",
        "JENKINS_URL": "BRANCH_NAME",
        "GITLAB_CI": "CI_BUILD_REF_NAME",
        "CIRCLECI": "CIRCLE_BRANCH"
    }

    for ci, branch in ci_manager.items():
        if os.getenv(ci) and os.getenv(branch):
            return os.getenv(branch)

    try:
        for line in subprocess.check_output("git branch --no-color", shell=True).decode().splitlines():
            line = line.strip()
            if line.startswith("*") and " (HEAD detached" not in line:
                return line.replace("*", "", 1).strip()
        return None
    except Exception:
        pass
    return None


def _is_stable_branch(branch):
    """
    Detect if current branch is stable one
    :param branch: Current Git branch name
    :return: True if current branch is Stable. Otherwise, False.
    """
    stable_branch_pattern = os.getenv("CONAN_STABLE_BRANCH_PATTERN")
    if stable_branch_pattern:
        stable_patterns = [stable_branch_pattern]
    else:
        stable_patterns = ["master$", "release*", "stable*"]

    for pattern in stable_patterns:
        prog = re.compile(pattern)

        if branch and prog.match(branch):
            return True
    return False
