#!/usr/bin/env python
import boto3, base64, tarfile, shutil, os, json

from github3 import login
from datetime import datetime
from git import Repo

# Github Details
organisation = 'Navex Global'
# This is, a github access token with appropriatly minimal permissions, that has been encrypted against our specific AWS KMS ARN.  It's therefore safe to make public
github_encrypted_token = ''

# AWS Details
bucket_name = 'navexgitbackup'

# Trivia
timestring = datetime.now().strftime('%Y%m%d')

def get_github_key_from_secrets_manager():
    secret_name = "sk-navex-github-backup"

    client = boto3.client(service_name='secretsmanager')
    get_secret_value_response = client.get_secret_value(  SecretId=secret_name  )
    return get_secret_value_response['SecretString']


def decrypt_token(token):
    client = boto3.client('kms')
    token = base64.decodestring(token)
    response = client.decrypt(CiphertextBlob=token)
    return response['Plaintext']


def get_github3_client(token):
    gh = login(token=token)
    return gh


def backup_github(gh,github_token):
    org = gh.organization(organisation)
    repos = list(org.iter_repos(type="all"))  # Or type="private"

    s3 = boto3.resource('s3')

    for repo in repos:

        r = str(repo)
        print "Archiving: " + r

        # Mirror Clone
        #from_url = "git@github.com:" + r + ".git"
        from_url = "https://" + github_token + "github.com/tnwinc" + r + ".git"
        dst_path = r + "-" + timestring + ".git"
        Repo.clone_from(from_url, dst_path, mirror=True)

        # Archive to file
        tar_filename = os.path.basename(r) + "-" + timestring + ".tar.gz"
        tar = tarfile.open(tar_filename, "w:gz")
        tar.add(dst_path)
        tar.close()

        # Stream to a file in an S3 bucket
        data = open(tar_filename, 'rb')
        s3.Bucket(bucket_name).put_object(Key=tar_filename, Body=data)

        # Cleanup
        shutil.rmtree(dst_path, ignore_errors=True)
        os.remove(tar_filename)

def handler(event, context):
    git_encrypted_key = get_github_key_from_secrets_manager()
    github_token = decrypt_token(git_encrypted_key)
    gh = get_github3_client(github_token)
    backup_github(gh)


def main():
    #boto3.setup_default_session(profile_name='cognito')
    boto3.setup_default_session(region_name='us-west-2')
    git_encrypted_key = get_github_key_from_secrets_manager()
    github_token = decrypt_token(git_encrypted_key)
    gh = get_github3_client(github_token)
    backup_github(gh,github_token)

if __name__ == "__main__":
    main()
