# 🤖 AWS Manager
Manages AWS resources [ASG, RDS, EC2].

## 🌐 Requirements
Needs ```aws-cli``` installed (Please refer to the [Official documentation](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)).

## 🔧 Configuration
For configuring ```aws-cli``` you'll need a Secret Access Key. You can follow [this guide](https://aws.amazon.com/blogs/security/wheres-my-secret-access-key/) to obtain one yourself.
Type ```aws configure``` in your terminal and provide the asked details, i.e
- ```aws_access_key_id```
- ```aws_secret_access_key```
- ```region```

> (**FYI**: This configuration is stored in ```~/.aws/credentials```)